import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.execution import PipelineRun, ActivityRun, ExecutionLog
from backend.app.models.pipeline import Pipeline
from backend.app.models.runtime import IntegrationRuntime
from backend.app.services.runtime_manager import RuntimeManagerService
from backend.app.execution.dag_engine import PipelineDAG, DAGValidationError
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.factory import get_activity_instance
from backend.app.execution.event_bus import event_bus
from backend.app.execution.expressions import ExpressionEvaluator
from backend.app.monitoring.diagnostics import get_worker_telemetry, classify_error, extract_stack_trace
from backend.app.monitoring.metrics import build_metrics_summary
from backend.app.monitoring.alert_engine import AlertEngine
from backend.app.services.metering_service import UsageMeteringEngine


class PipelineRunner:
    """
    Core Execution Orchestrator.
    Manages DAG resolution, activity lifecycles, retries, checkpointing,
    and database state synchronization.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id

    def execute_sync(self):
        """Synchronous entrypoint designed to run inside worker thread or background task."""
        db: Session = SessionLocal()
        try:
            pipeline_run = db.query(PipelineRun).filter(PipelineRun.id == self.run_id).first()
            if not pipeline_run:
                print(f"[ERROR] PipelineRun '{self.run_id}' not found.")
                return

            pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_run.pipeline_id).first()
            if not pipeline:
                pipeline_run.status = "Failed"
                pipeline_run.error_summary = "Pipeline definition missing"
                db.commit()
                return

            pipeline_def = pipeline.definition_json or {}
            activities_list = pipeline_def.get("activities", [])

            worker_meta = get_worker_telemetry()
            pipeline_run.status = "Running"
            pipeline_run.started_at = datetime.now(timezone.utc)
            pipeline_run.total_activities = len(activities_list)
            pipeline_run.worker_info = worker_meta
            db.commit()

            if not activities_list:
                pipeline_run.status = "Succeeded"
                pipeline_run.ended_at = datetime.now(timezone.utc)
                db.commit()
                return

            # Parse and validate DAG
            try:
                dag = PipelineDAG(activities_list)
            except DAGValidationError as ve:
                pipeline_run.status = "Failed"
                pipeline_run.error_summary = f"Invalid pipeline DAG: {str(ve)}"
                pipeline_run.ended_at = datetime.now(timezone.utc)
                db.commit()
                return

            completed_activities: Dict[str, str] = {}  # act_id -> status
            pending_activities = set(dag.activity_map.keys())
            total_read = 0
            total_written = 0
            total_bytes = 0
            succeeded_count = 0
            failed_count = 0
            pipeline_vars = pipeline_def.get("variables", {}).copy()
            activity_outputs: Dict[str, Any] = {}

            # Create initial ActivityRun records in DB
            for act_id, act_cfg in dag.activity_map.items():
                existing = db.query(ActivityRun).filter(
                    ActivityRun.pipeline_run_id == self.run_id,
                    ActivityRun.activity_id == act_id
                ).first()
                if not existing:
                    act_run = ActivityRun(
                        pipeline_run_id=self.run_id,
                        activity_id=act_id,
                        activity_name=act_cfg.get("name", act_id),
                        activity_type=act_cfg.get("type", "Unknown"),
                        status="Pending",
                        worker_info=worker_meta
                    )
                    db.add(act_run)
            db.commit()

            start_clock = time.time()

            # Main execution loop
            while pending_activities:
                # 1. Detect dead activities whose conditions cannot be satisfied and mark them Skipped
                dead_activities = [
                    act_id for act_id in pending_activities
                    if dag.is_activity_dead(act_id, completed_activities)
                ]
                if dead_activities:
                    for act_id in dead_activities:
                        completed_activities[act_id] = "Skipped"
                        pending_activities.remove(act_id)
                        act_run = db.query(ActivityRun).filter(
                            ActivityRun.pipeline_run_id == self.run_id,
                            ActivityRun.activity_id == act_id
                        ).first()
                        if act_run:
                            act_run.status = "Skipped"
                            act_run.ended_at = datetime.now(timezone.utc)
                            print(f"[INFO] Activity '{act_id}' skipped due to upstream conditions.")
                    db.commit()
                    continue

                # 2. Find runnable activities whose dependencies are satisfied
                runnable = [
                    act_id for act_id in pending_activities 
                    if dag.is_activity_ready(act_id, completed_activities)
                ]

                if not runnable:
                    # Deadlock or unsatisfied dependencies -> mark remaining as Skipped
                    for act_id in pending_activities:
                        completed_activities[act_id] = "Skipped"
                        act_run = db.query(ActivityRun).filter(
                            ActivityRun.pipeline_run_id == self.run_id,
                            ActivityRun.activity_id == act_id
                        ).first()
                        if act_run:
                            act_run.status = "Skipped"
                            act_run.ended_at = datetime.now(timezone.utc)
                    break

                for act_id in runnable:
                    act_cfg = dag.activity_map[act_id]
                    act_run = db.query(ActivityRun).filter(
                        ActivityRun.pipeline_run_id == self.run_id,
                        ActivityRun.activity_id == act_id
                    ).first()

                    # Check if activity itself is deactivated
                    if act_cfg.get("state") in ("Inactive", "Deactivated", "Disabled"):
                        act_run.status = "Skipped"
                        act_run.ended_at = datetime.now(timezone.utc)
                        completed_activities[act_id] = "Skipped"
                        pending_activities.remove(act_id)
                        db.commit()
                        print(f"[INFO] Activity '{act_id}' skipped because it is deactivated.")
                        continue

                    act_start_clock = time.time()
                    act_run.status = "Running"
                    act_run.started_at = datetime.now(timezone.utc)
                    db.commit()

                    retry_policy = act_cfg.get("retry_policy", {})
                    max_retries = int(retry_policy.get("max_retries", 0))
                    retry_interval = int(retry_policy.get("retry_interval_seconds", 2))

                    attempt = 0
                    success = False
                    last_error = None
                    last_stack = None
                    res = None
                    retry_attempts_log: List[Dict[str, Any]] = []
                    runtime_worker_meta = worker_meta

                    while attempt <= max_retries:
                        attempt_start = time.time()
                        act_run.retry_attempt = attempt
                        db.commit()
                        try:
                            # Dynamically evaluate expressions inside activity config
                            pipeline_info = {
                                "RunId": self.run_id,
                                "Pipeline": pipeline.name if pipeline else "Pipeline",
                                "PipelineId": pipeline.id if pipeline else "",
                                "WorkspaceId": getattr(pipeline, "workspace_id", getattr(getattr(pipeline, "project", None), "workspace_id", "")) if pipeline else "",
                                "TriggerType": getattr(pipeline_run, "trigger_type", "Manual") or "Manual",
                                "TriggerTime": pipeline_run.started_at.isoformat() if pipeline_run.started_at else datetime.now(timezone.utc).isoformat()
                            }
                            global_params = pipeline_def.get("global_parameters", {})
                            evaluator = ExpressionEvaluator(
                                parameters=pipeline_run.parameters or {},
                                global_parameters=global_params,
                                variables=pipeline_vars,
                                activity_outputs=activity_outputs,
                                pipeline_info=pipeline_info
                            )
                            resolved_config = evaluator.evaluate(act_cfg.get("config", {}))

                            # 1. Resolve Integration Runtime (Activity override > Config override > Pipeline default > AutoResolve fallback)
                            target_runtime_id = (
                                act_cfg.get("runtime_id")
                                or (resolved_config.get("runtime_id") if isinstance(resolved_config, dict) else None)
                                or getattr(pipeline, "runtime_id", None)
                            )
                            runtime = None
                            if target_runtime_id:
                                runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == target_runtime_id).first()
                            if not runtime:
                                runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.name == "AutoResolveIntegrationRuntime").first()

                            if runtime and (not runtime.is_enabled or runtime.status == "Disabled"):
                                raise RuntimeError(f"Integration Runtime '{runtime.name}' is disabled.")

                            # Update act_run worker telemetry with assigned runtime info
                            runtime_worker_meta = {
                                **worker_meta,
                                "runtime_id": runtime.id if runtime else None,
                                "runtime_name": runtime.name if runtime else "AutoResolveIntegrationRuntime",
                                "runtime_type": getattr(runtime, "runtime_type", "Cloud")
                            }
                            if runtime and runtime.runtime_type == "SelfHosted":
                                runtime_worker_meta["agent_host"] = runtime.host_name
                                runtime_worker_meta["agent_os"] = runtime.agent_os
                                runtime_worker_meta["agent_version"] = runtime.agent_version
                            act_run.worker_info = runtime_worker_meta

                            if runtime and runtime.runtime_type == "SelfHosted":
                                if runtime.status != "Online":
                                    raise RuntimeError(f"Self-Hosted Integration Runtime '{runtime.name}' is currently {runtime.status}. Cannot dispatch activity.")

                                task_payload = {
                                    "activity_id": act_id,
                                    "activity_name": act_cfg.get("name", act_id),
                                    "activity_type": act_cfg.get("type", "CopyData"),
                                    "config": resolved_config,
                                    "pipeline_parameters": pipeline_run.parameters or {},
                                    "pipeline_variables": pipeline_vars,
                                    "activity_outputs": activity_outputs
                                }
                                timeout_sec = int(act_cfg.get("timeout_seconds") or 300)
                                rt_task = RuntimeManagerService.enqueue_task(
                                    db=db,
                                    runtime_id=runtime.id,
                                    task_type=act_cfg.get("type", "CopyData"),
                                    payload=task_payload,
                                    pipeline_run_id=self.run_id,
                                    activity_run_id=act_run.id,
                                    timeout_seconds=timeout_sec
                                )

                                poll_start = time.time()
                                while True:
                                    db.refresh(rt_task)
                                    if rt_task.status == "Completed":
                                        t_res = rt_task.task_result or {}
                                        class _AgentResult:
                                            def __init__(self, d):
                                                self.status = "Succeeded"
                                                self.rows_read = int(d.get("rows_read", 0))
                                                self.rows_written = int(d.get("rows_written", 0))
                                                self.bytes_processed = int(d.get("bytes_processed", 0))
                                                self.metrics = d.get("metrics") or {}
                                                self.output_variables = d.get("output_variables") or {}
                                                self.error_message = None
                                                self.error_stack_trace = None
                                        res = _AgentResult(t_res)
                                        break
                                    elif rt_task.status in ("Failed", "Cancelled"):
                                        t_res = rt_task.task_result or {}
                                        raise RuntimeError(t_res.get("error_message") or f"Task execution failed on agent '{runtime.name}'")

                                    if time.time() - poll_start > timeout_sec:
                                        rt_task.status = "Failed"
                                        rt_task.task_result = {"error_message": f"Task timed out after {timeout_sec}s on runtime '{runtime.name}'"}
                                        db.commit()
                                        raise TimeoutError(rt_task.task_result["error_message"])

                                    time.sleep(1.0)
                            else:
                                context = ActivityExecutionContext(
                                    pipeline_run_id=self.run_id,
                                    activity_id=act_id,
                                    activity_name=act_cfg.get("name", act_id),
                                    activity_type=act_cfg.get("type", "CopyData"),
                                    config=resolved_config,
                                    pipeline_parameters=pipeline_run.parameters or {},
                                    pipeline_variables=pipeline_vars,
                                    activity_outputs=activity_outputs
                                )
                                executor = get_activity_instance(context, db)
                                executor.activity_run_id = act_run.id
                                res = executor.execute()

                            attempt_duration_ms = max(int((time.time() - attempt_start) * 1000), 1)

                            if res.status == "Succeeded":
                                success = True
                                retry_attempts_log.append({
                                    "attempt": attempt,
                                    "status": "Succeeded",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "duration_ms": attempt_duration_ms
                                })
                                break
                            else:
                                last_error = res.error_message or "Activity returned Failed status"
                                last_stack = getattr(res, "error_stack_trace", None)
                                retry_attempts_log.append({
                                    "attempt": attempt,
                                    "status": "Failed",
                                    "error": last_error[:250] if last_error else "Failed",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "duration_ms": attempt_duration_ms
                                })
                        except Exception as e:
                            last_error = str(e)
                            last_stack = f"{str(e)}\n{traceback.format_exc()}"
                            attempt_duration_ms = max(int((time.time() - attempt_start) * 1000), 1)
                            retry_attempts_log.append({
                                "attempt": attempt,
                                "status": "Failed",
                                "error": str(e)[:250],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "duration_ms": attempt_duration_ms
                            })
                            executor = getattr(locals(), 'executor', None)
                            if executor:
                                executor.log("ERROR", f"Attempt {attempt + 1} failed: {str(e)}")

                        attempt += 1
                        if attempt <= max_retries:
                            time.sleep(retry_interval)

                    act_run.ended_at = datetime.now(timezone.utc)
                    act_run.duration_seconds = max(int(time.time() - act_start_clock), 0)
                    act_run.retry_history = retry_attempts_log
                    act_run.worker_info = runtime_worker_meta

                    if success and res:
                        act_run.status = "Succeeded"
                        act_run.rows_read = res.rows_read
                        act_run.rows_written = res.rows_written
                        act_run.bytes_processed = res.bytes_processed
                        act_run.metrics = res.metrics
                        act_run.output_variables = res.output_variables or {}
                        total_read += res.rows_read
                        total_written += res.rows_written
                        total_bytes += res.bytes_processed
                        succeeded_count += 1
                        completed_activities[act_id] = "Succeeded"
                        pipeline_vars.update(res.output_variables)
                        activity_outputs[act_id] = res.output_variables
                    else:
                        act_run.status = "Failed"
                        act_run.error_message = last_error
                        act_run.error_classification = classify_error(last_error or last_stack)
                        act_run.error_stack_trace = last_stack or last_error
                        failed_count += 1
                        completed_activities[act_id] = "Failed"

                    db.commit()
                    pending_activities.remove(act_id)

            # Update final pipeline run record
            pipeline_run.ended_at = datetime.now(timezone.utc)
            pipeline_run.duration_seconds = max(int(time.time() - start_clock), 0)
            pipeline_run.total_rows_read = total_read
            pipeline_run.total_rows_written = total_written
            pipeline_run.total_bytes_processed = total_bytes
            pipeline_run.succeeded_activities = succeeded_count
            pipeline_run.failed_activities = failed_count

            # Determine if any failures were unhandled
            unhandled_failures = []
            for failed_act_id in [a for a, s in completed_activities.items() if s == "Failed"]:
                downstream_edges = dag.graph.get(failed_act_id, [])
                failure_handlers = [e["activity_id"] for e in downstream_edges if e.get("condition") == "Failed"]
                if not failure_handlers or not any(completed_activities.get(h) == "Succeeded" for h in failure_handlers):
                    unhandled_failures.append(failed_act_id)

            if unhandled_failures:
                pipeline_run.status = "Failed"
                pipeline_run.error_summary = f"{len(unhandled_failures)} unhandled activity failure(s): {', '.join(unhandled_failures)}"
            elif failed_count > 0:
                pipeline_run.status = "Succeeded"
                pipeline_run.error_summary = f"{failed_count} activity failure(s) handled by On Failure branch."
            else:
                pipeline_run.status = "Succeeded"

            # Compute execution metrics summary
            metrics = build_metrics_summary(pipeline_run)
            metrics["output_variables"] = pipeline_vars
            pipeline_run.execution_metrics = metrics
            db.commit()

            # Trigger alert engine
            try:
                AlertEngine.evaluate_pipeline_run(pipeline_run, db)
            except Exception as alert_err:
                print(f"[WARN] Alert engine evaluation error: {alert_err}")

            # Record metered usage in immutable billing ledger
            try:
                UsageMeteringEngine.record_pipeline_execution(db, pipeline_run.id)
            except Exception as meter_err:
                print(f"[WARN] Usage metering recording error: {meter_err}")

        except Exception as global_ex:
            pipeline_run = db.query(PipelineRun).filter(PipelineRun.id == self.run_id).first()
            if pipeline_run:
                pipeline_run.status = "Failed"
                pipeline_run.error_summary = f"Fatal engine error: {str(global_ex)}\n{traceback.format_exc()}"
                pipeline_run.ended_at = datetime.now(timezone.utc)
                db.commit()
                try:
                    AlertEngine.evaluate_pipeline_run(pipeline_run, db)
                except Exception:
                    pass
                try:
                    UsageMeteringEngine.record_pipeline_execution(db, pipeline_run.id)
                except Exception as meter_err:
                    print(f"[WARN] Usage metering recording error: {meter_err}")
        finally:
            db.close()
