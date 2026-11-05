import re
import math
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.models.runtime import IntegrationRuntime, RuntimeTask
from backend.app.models.pipeline import Pipeline
from backend.app.schemas.observability import (
    CopyDataPerformanceMetrics,
    RuntimeFleetOverview,
    ErrorCluster,
    FailureDiagnosticsResponse,
    ObservabilityOverview,
    OtelSpan,
    OtelTraceResponse
)


class ObservabilityService:
    """
    Enterprise Observability, Copy Data Analytics, Fleet Telemetry,
    Failure Diagnostics, and Prometheus / OpenTelemetry Export Engine.
    """

    @classmethod
    def get_copy_data_performance(
        cls,
        db: Session,
        project_id: Optional[str] = None,
        limit: int = 100
    ) -> CopyDataPerformanceMetrics:
        """Aggregates throughput, transfer volume, and performance trends for Copy Data activities."""
        query = db.query(ActivityRun).filter(ActivityRun.activity_type == "CopyData")
        if project_id:
            query = query.join(PipelineRun, ActivityRun.pipeline_run_id == PipelineRun.id)\
                         .join(Pipeline, PipelineRun.pipeline_id == Pipeline.id)\
                         .filter(Pipeline.project_id == project_id)

        copy_runs = query.order_by(ActivityRun.started_at.desc()).limit(limit).all()

        total_runs = len(copy_runs)
        total_rows = sum((r.rows_written or 0) for r in copy_runs)
        
        # Calculate bytes and throughput
        total_bytes = 0
        throughputs = []
        rejected_rows = 0
        durations = []
        recent_transfers = []
        trend_map: Dict[str, Dict[str, Any]] = {}

        for r in copy_runs:
            metrics = r.metrics or {}
            dur = r.duration_seconds or 0.1
            durations.append(dur)

            # Estimate or extract transferred bytes
            bytes_trans = metrics.get("bytes_transferred") or metrics.get("total_bytes") or (r.rows_written or 0) * 256
            total_bytes += bytes_trans

            # Throughput in MB/s
            mb_sec = metrics.get("throughput_mb_sec") or metrics.get("throughput_mb_s")
            if not mb_sec and dur > 0:
                mb_sec = round((bytes_trans / (1024 * 1024)) / dur, 3)
            mb_sec = float(mb_sec or 0.0)
            throughputs.append(mb_sec)

            rej = metrics.get("rejected_rows") or metrics.get("error_count") or 0
            rejected_rows += int(rej)

            # Hour bucket for trend
            if r.started_at:
                bucket = r.started_at.strftime("%Y-%m-%d %H:00")
                if bucket not in trend_map:
                    trend_map[bucket] = {"time": bucket, "total_mb": 0.0, "total_rows": 0, "count": 0}
                trend_map[bucket]["total_mb"] += bytes_trans / (1024 * 1024)
                trend_map[bucket]["total_rows"] += r.rows_written or 0
                trend_map[bucket]["count"] += 1

            if len(recent_transfers) < 10:
                recent_transfers.append({
                    "activity_run_id": r.id,
                    "activity_name": r.activity_name,
                    "status": r.status,
                    "rows_written": r.rows_written or 0,
                    "bytes_transferred": bytes_trans,
                    "throughput_mb_sec": mb_sec,
                    "duration_seconds": round(dur, 2),
                    "started_at": r.started_at.isoformat() if r.started_at else None
                })

        avg_throughput = round(sum(throughputs) / len(throughputs), 2) if throughputs else 0.0
        peak_throughput = round(max(throughputs), 2) if throughputs else 0.0
        avg_dur = round(sum(durations) / len(durations), 2) if durations else 0.0

        trend_list = []
        for k in sorted(trend_map.keys())[-12:]:
            item = trend_map[k]
            trend_list.append({
                "time": item["time"],
                "throughput_mb_sec": round(item["total_mb"] / max(1, item["count"]), 2),
                "rows_transferred": item["total_rows"]
            })

        return CopyDataPerformanceMetrics(
            total_copy_activities=total_runs,
            total_rows_transferred=total_rows,
            total_bytes_transferred=total_bytes,
            average_throughput_mb_sec=avg_throughput,
            peak_throughput_mb_sec=peak_throughput,
            total_rejected_rows=rejected_rows,
            average_duration_seconds=avg_dur,
            throughput_trend=trend_list,
            recent_transfers=recent_transfers
        )

    @classmethod
    def get_runtime_fleet_overview(
        cls,
        db: Session,
        project_id: Optional[str] = None
    ) -> RuntimeFleetOverview:
        """Aggregates fleet-wide health, CPU/RAM utilization, and queue depths across all Integration Runtimes."""
        query = db.query(IntegrationRuntime)
        if project_id:
            query = query.filter((IntegrationRuntime.project_id == project_id) | (IntegrationRuntime.project_id == None))

        runtimes = query.all()

        total = len(runtimes)
        online = sum(1 for r in runtimes if r.status == "Online")
        offline = sum(1 for r in runtimes if r.status != "Online")

        total_cpu = sum((r.cpu_usage_pct or 0.0) for r in runtimes)
        avg_cpu = round(total_cpu / max(1, total), 1)

        total_mem = sum((r.memory_total_bytes or 8589934592) for r in runtimes)
        used_mem = sum((r.memory_used_bytes or 0) for r in runtimes)
        mem_pct = round((used_mem / max(1, total_mem)) * 100.0, 1)

        active_tasks = sum((r.active_task_count or 0) for r in runtimes)
        concurrency = sum((r.concurrency_limit or 4) for r in runtimes)

        runtime_cards = []
        for r in runtimes:
            runtime_cards.append({
                "id": r.id,
                "name": r.name,
                "runtime_type": r.runtime_type,
                "status": r.status,
                "cpu_cores": r.cpu_cores,
                "cpu_usage_pct": r.cpu_usage_pct,
                "memory_total_bytes": r.memory_total_bytes,
                "memory_used_bytes": r.memory_used_bytes,
                "active_task_count": r.active_task_count,
                "concurrency_limit": r.concurrency_limit,
                "agent_os": r.agent_os,
                "agent_version": r.agent_version,
                "last_heartbeat_at": r.last_heartbeat_at.isoformat() if r.last_heartbeat_at else None
            })

        return RuntimeFleetOverview(
            total_runtimes=total,
            online_count=online,
            offline_count=offline,
            fleet_cpu_usage_pct=avg_cpu,
            fleet_memory_total_bytes=total_mem,
            fleet_memory_used_bytes=used_mem,
            fleet_memory_usage_pct=mem_pct,
            active_tasks=active_tasks,
            total_concurrency_capacity=concurrency,
            runtimes=runtime_cards
        )

    @classmethod
    def get_failure_clustering(
        cls,
        db: Session,
        project_id: Optional[str] = None,
        days: int = 7
    ) -> FailureDiagnosticsResponse:
        """
        Analyzes failed pipeline and activity executions, clusters recurring error patterns,
        and produces root cause diagnostics and remediation guidance.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        pipe_query = db.query(PipelineRun).filter(
            PipelineRun.status == "Failed",
            PipelineRun.started_at >= cutoff
        )
        if project_id:
            pipe_query = pipe_query.join(Pipeline, PipelineRun.pipeline_id == Pipeline.id)\
                                   .filter(Pipeline.project_id == project_id)
        failed_pipes = pipe_query.all()

        act_query = db.query(ActivityRun).filter(
            ActivityRun.status == "Failed",
            ActivityRun.started_at >= cutoff
        )
        failed_acts = act_query.all()

        total_runs = db.query(PipelineRun).filter(PipelineRun.started_at >= cutoff).count()
        total_failures = len(failed_pipes)
        fail_rate = round((total_failures / max(1, total_runs)) * 100.0, 1)

        # Clustering dictionary: category -> details
        clusters: Dict[str, Dict[str, Any]] = {}

        def categorize_error(raw_err: str) -> Tuple[str, str, str]:
            err = (raw_err or "").lower()
            if "timeout" in err or "timed out" in err or "connection refused" in err:
                return (
                    "Network & Connection Timeout",
                    "Target database or storage endpoint was unreachable or timed out during transfer.",
                    "Verify target firewall rules, VPC peering, and connection pool timeouts."
                )
            elif "permission" in err or "access denied" in err or "unauthorized" in err or "403" in err or "auth" in err:
                return (
                    "Authentication & Access Denied",
                    "Credentials expired or lack sufficient IAM / RBAC permissions for the target resource.",
                    "Rotate access keys, refresh Service Principal secrets, or verify IAM role policies."
                )
            elif "not found" in err or "no such" in err or "does not exist" in err or "404" in err:
                return (
                    "Resource Not Found (Table/File/Bucket)",
                    "Referenced table, file path, or cloud storage container does not exist at execution time.",
                    "Verify upstream extraction paths, table naming conventions, and file arrival triggers."
                )
            elif "schema" in err or "column" in err or "type mismatch" in err or "datatype" in err:
                return (
                    "Schema Drift & Column Mismatch",
                    "Source dataset schema altered without corresponding pipeline mapping update.",
                    "Run 'Detect Schema Drift' on the dataset or enable schema drift tolerance in Copy Data."
                )
            elif "memory" in err or "oom" in err or "killed" in err or "heap" in err:
                return (
                    "Resource Exhaustion & OOM",
                    "Activity payload exceeded worker agent memory limits.",
                    "Increase chunk batch size, allocate more RAM to the Self-Hosted agent, or switch to Cloud Runtime."
                )
            else:
                return (
                    "Execution Runtime Failure",
                    raw_err[:120] if raw_err else "Uncategorized execution exception occurred.",
                    "Inspect full activity execution logs for detailed traceback diagnostics."
                )

        # Process failed activities
        for a in failed_acts:
            raw_msg = a.error_message or "Activity execution failed without explicit error trace"
            cat, desc, remed = categorize_error(raw_msg)
            
            if cat not in clusters:
                clusters[cat] = {
                    "cluster_id": str(uuid.uuid4())[:8],
                    "category": cat,
                    "representative_message": raw_msg[:200],
                    "count": 0,
                    "first_seen": a.started_at or datetime.now(timezone.utc),
                    "last_seen": a.started_at or datetime.now(timezone.utc),
                    "pipelines": set(),
                    "activities": set(),
                    "remediation": remed
                }

            c = clusters[cat]
            c["count"] += 1
            if a.started_at:
                if a.started_at < c["first_seen"]:
                    c["first_seen"] = a.started_at
                if a.started_at > c["last_seen"]:
                    c["last_seen"] = a.started_at
            if a.activity_name:
                c["activities"].add(a.activity_name)

        # Process failed pipelines
        for p in failed_pipes:
            raw_msg = p.error_summary or "Pipeline run failed"
            cat, desc, remed = categorize_error(raw_msg)
            if cat in clusters:
                clusters[cat]["pipelines"].add(p.pipeline_id)

        cluster_models = []
        for k, v in sorted(clusters.items(), key=lambda item: item[1]["count"], reverse=True):
            cluster_models.append(ErrorCluster(
                cluster_id=v["cluster_id"],
                error_category=v["category"],
                representative_message=v["representative_message"],
                occurrence_count=v["count"],
                first_seen_at=v["first_seen"],
                last_seen_at=v["last_seen"],
                affected_pipelines=list(v["pipelines"])[:5],
                affected_activities=list(v["activities"])[:5],
                suggested_remediation=v["remediation"]
            ))

        return FailureDiagnosticsResponse(
            total_failures=total_failures,
            failure_rate_pct=fail_rate,
            clusters=cluster_models
        )

    @classmethod
    def get_observability_overview(
        cls,
        db: Session,
        project_id: Optional[str] = None
    ) -> ObservabilityOverview:
        """Assembles high-level enterprise observability metrics for dashboard rendering."""
        pid = project_id or "default-project"
        
        runs_query = db.query(PipelineRun)
        if project_id:
            runs_query = runs_query.join(Pipeline, PipelineRun.pipeline_id == Pipeline.id)\
                                   .filter(Pipeline.project_id == project_id)

        total_runs = runs_query.count()
        active_runs = runs_query.filter(PipelineRun.status.in_(["Running", "Queued"])).count()
        succeeded_runs = runs_query.filter(PipelineRun.status == "Succeeded").count()
        success_rate = round((succeeded_runs / max(1, total_runs)) * 100.0, 1) if total_runs > 0 else 100.0

        copy_perf = cls.get_copy_data_performance(db, project_id)
        fleet = cls.get_runtime_fleet_overview(db, project_id)
        diagnostics = cls.get_failure_clustering(db, project_id)

        return ObservabilityOverview(
            project_id=pid,
            total_pipeline_runs=total_runs,
            active_runs=active_runs,
            success_rate_pct=success_rate,
            copy_performance=copy_perf,
            fleet_overview=fleet,
            failure_diagnostics=diagnostics
        )

    @classmethod
    def export_prometheus_metrics(cls, db: Session) -> str:
        """
        Generates standard Prometheus text-format metrics covering pipelines,
        activities, Copy Data throughput, and runtime fleet telemetry.
        """
        lines: List[str] = [
            "# HELP dataforge_pipeline_runs_total Total count of pipeline executions partitioned by status",
            "# TYPE dataforge_pipeline_runs_total counter"
        ]

        # Pipeline run statuses
        status_counts = db.query(PipelineRun.status, func.count(PipelineRun.id)).group_by(PipelineRun.status).all()
        for s, cnt in status_counts:
            lines.append(f'dataforge_pipeline_runs_total{{status="{s}"}} {cnt}')

        # Pipeline durations
        lines.append("# HELP dataforge_pipeline_duration_seconds Average pipeline run duration in seconds")
        lines.append("# TYPE dataforge_pipeline_duration_seconds gauge")
        avg_dur = db.query(func.avg(PipelineRun.duration_seconds)).scalar() or 0.0
        lines.append(f'dataforge_pipeline_duration_seconds{{scope="global"}} {round(float(avg_dur), 2)}')

        # Copy Data Metrics
        lines.append("# HELP dataforge_copy_data_throughput_mb_sec Average throughput for Copy Data movement in MB/sec")
        lines.append("# TYPE dataforge_copy_data_throughput_mb_sec gauge")
        perf = cls.get_copy_data_performance(db)
        lines.append(f'dataforge_copy_data_throughput_mb_sec {perf.average_throughput_mb_sec}')
        lines.append(f'dataforge_copy_data_peak_throughput_mb_sec {perf.peak_throughput_mb_sec}')
        lines.append(f'dataforge_copy_data_rows_transferred_total {perf.total_rows_transferred}')
        lines.append(f'dataforge_copy_data_bytes_transferred_total {perf.total_bytes_transferred}')

        # Runtime Fleet Telemetry
        fleet = cls.get_runtime_fleet_overview(db)
        lines.append("# HELP dataforge_runtime_fleet_agents_total Total number of integration runtime agents")
        lines.append("# TYPE dataforge_runtime_fleet_agents_total gauge")
        lines.append(f'dataforge_runtime_fleet_agents_total{{status="online"}} {fleet.online_count}')
        lines.append(f'dataforge_runtime_fleet_agents_total{{status="offline"}} {fleet.offline_count}')
        lines.append(f'dataforge_runtime_fleet_cpu_usage_pct {fleet.fleet_cpu_usage_pct}')
        lines.append(f'dataforge_runtime_fleet_memory_usage_pct {fleet.fleet_memory_usage_pct}')
        lines.append(f'dataforge_runtime_fleet_active_tasks {fleet.active_tasks}')
        lines.append(f'dataforge_runtime_fleet_concurrency_capacity {fleet.total_concurrency_capacity}')

        for r in fleet.runtimes:
            safe_name = r["name"].replace('"', '')
            lines.append(f'dataforge_runtime_cpu_pct{{runtime="{safe_name}",type="{r["runtime_type"]}"}} {r["cpu_usage_pct"]}')
            lines.append(f'dataforge_runtime_tasks{{runtime="{safe_name}"}} {r["active_task_count"]}')

        return "\n".join(lines) + "\n"

    @classmethod
    def export_opentelemetry_trace(
        cls,
        db: Session,
        pipeline_run_id: str
    ) -> OtelTraceResponse:
        """
        Constructs an OpenTelemetry-compatible distributed trace representation for a pipeline run.
        The root span models the pipeline, and child spans model activity executions.
        """
        run = db.query(PipelineRun).filter(PipelineRun.id == pipeline_run_id).first()
        if not run:
            raise ValueError(f"Pipeline run '{pipeline_run_id}' not found.")

        pipe = db.query(Pipeline).filter(Pipeline.id == run.pipeline_id).first()
        pipe_name = pipe.name if pipe else "PipelineExecution"

        # Deterministic trace ID from pipeline run ID
        trace_id = run.id.replace("-", "").ljust(32, "0")[:32]
        root_span_id = str(uuid.uuid4()).replace("-", "")[:16]

        start_time = run.started_at or datetime.now(timezone.utc)
        end_time = run.ended_at or (start_time + timedelta(seconds=run.duration_seconds or 1))
        
        start_nano = int(start_time.timestamp() * 1e9)
        end_nano = int(end_time.timestamp() * 1e9)

        root_span = OtelSpan(
            trace_id=trace_id,
            span_id=root_span_id,
            parent_span_id=None,
            name=f"Pipeline: {pipe_name}",
            kind="SERVER",
            start_time_unix_nano=start_nano,
            end_time_unix_nano=end_nano,
            attributes={
                "dataforge.pipeline.id": run.pipeline_id,
                "dataforge.pipeline.name": pipe_name,
                "dataforge.run.id": run.id,
                "dataforge.run.status": run.status,
                "dataforge.run.duration_seconds": run.duration_seconds or 0.0,
                "dataforge.run.rows_written": run.total_rows_written or 0
            },
            status={
                "code": "STATUS_CODE_OK" if run.status == "Succeeded" else "STATUS_CODE_ERROR",
                "message": run.error_summary or ""
            }
        )

        spans: List[OtelSpan] = [root_span]

        # Activity Runs child spans
        activities = db.query(ActivityRun).filter(ActivityRun.pipeline_run_id == run.id).all()
        for act in activities:
            child_span_id = str(uuid.uuid4()).replace("-", "")[:16]
            act_start = act.started_at or start_time
            act_end = act.ended_at or (act_start + timedelta(seconds=act.duration_seconds or 0.5))
            
            act_start_nano = int(act_start.timestamp() * 1e9)
            act_end_nano = int(act_end.timestamp() * 1e9)

            spans.append(OtelSpan(
                trace_id=trace_id,
                span_id=child_span_id,
                parent_span_id=root_span_id,
                name=f"Activity: {act.activity_name}",
                kind="INTERNAL",
                start_time_unix_nano=act_start_nano,
                end_time_unix_nano=act_end_nano,
                attributes={
                    "dataforge.activity.name": act.activity_name,
                    "dataforge.activity.type": act.activity_type,
                    "dataforge.activity.status": act.status,
                    "dataforge.activity.duration_seconds": act.duration_seconds or 0.0,
                    "dataforge.activity.rows_read": act.rows_read or 0,
                    "dataforge.activity.rows_written": act.rows_written or 0,
                    **(act.metrics or {})
                },
                status={
                    "code": "STATUS_CODE_OK" if act.status == "Succeeded" else "STATUS_CODE_ERROR",
                    "message": act.error_message or ""
                }
            ))

        return OtelTraceResponse(trace_id=trace_id, spans=spans)
