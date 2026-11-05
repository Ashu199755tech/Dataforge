import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.execution import PipelineRun, ActivityRun, ExecutionLog
from backend.app.models.pipeline import Pipeline
from backend.app.execution.dag_engine import PipelineDAG, DAGValidationError
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.factory import get_activity_instance
from backend.app.execution.event_bus import event_bus
from backend.app.execution.expressions import ExpressionEvaluator


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

            pipeline_run.status = "Running"
            pipeline_run.started_at = datetime.now(timezone.utc)
            pipeline_run.total_activities = len(activities_list)
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
                        status="Pending"
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
                    res = None

                    while attempt <= max_retries:
                        act_run.retry_attempt = attempt
                        db.commit()
                        try:
                            # Dynamically evaluate expressions inside activity config
                            evaluator = ExpressionEvaluator(
                                parameters=pipeline_run.parameters or {},
                                variables=pipeline_vars,
                                activity_outputs=activity_outputs
                            )
                            resolved_config = evaluator.evaluate(act_cfg.get("config", {}))

                            context = ActivityExecutionContext(
                                pipeline_run_id=self.run_id,
                                activity_id=act_id,
                                activity_name=act_cfg.get("name", act_id),
                                activity_type=act_cfg.get("type", "CopyData"),
                                config=resolved_config,
                                pipeline_parameters=pipeline_run.parameters or {},
                                pipeline_variables=pipeline_vars
                            )
                            executor = get_activity_instance(context, db)
                            executor.activity_run_id = act_run.id
                            res = executor.execute()

                            if res.status == "Succeeded":
                                success = True
                                break
                            else:
                                last_error = res.error_message or "Activity returned Failed status"
                        except Exception as e:
                            last_error = f"{str(e)}\n{traceback.format_exc()}"
                            executor = getattr(locals(), 'executor', None)
                            if executor:
                                executor.log("ERROR", f"Attempt {attempt + 1} failed: {str(e)}")

                        attempt += 1
                        if attempt <= max_retries:
                            time.sleep(retry_interval)

                    act_run.ended_at = datetime.now(timezone.utc)
                    act_run.duration_seconds = max(int(time.time() - act_start_clock), 0)

                    if success and res:
                        act_run.status = "Succeeded"
                        act_run.rows_read = res.rows_read
                        act_run.rows_written = res.rows_written
                        act_run.bytes_processed = res.bytes_processed
                        act_run.metrics = res.metrics
                        total_read += res.rows_read
                        total_written += res.rows_written
                        succeeded_count += 1
                        completed_activities[act_id] = "Succeeded"
                        pipeline_vars.update(res.output_variables)
                        activity_outputs[act_id] = res.output_variables
                    else:
                        act_run.status = "Failed"
                        act_run.error_message = last_error
                        failed_count += 1
                        completed_activities[act_id] = "Failed"

                    db.commit()
                    pending_activities.remove(act_id)

            # Update final pipeline run record
            pipeline_run.ended_at = datetime.now(timezone.utc)
            pipeline_run.duration_seconds = int(time.time() - start_clock)
            pipeline_run.total_rows_read = total_read
            pipeline_run.total_rows_written = total_written
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

            db.commit()

        except Exception as global_ex:
            pipeline_run = db.query(PipelineRun).filter(PipelineRun.id == self.run_id).first()
            if pipeline_run:
                pipeline_run.status = "Failed"
                pipeline_run.error_summary = f"Fatal engine error: {str(global_ex)}\n{traceback.format_exc()}"
                pipeline_run.ended_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()
