import io
import csv
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.models.execution import PipelineRun, ActivityRun


def build_timeline(pipeline_run: PipelineRun) -> List[Dict[str, Any]]:
    """
    Constructs high-resolution timeline/Gantt telemetry for a pipeline run
    and its constituent activities.
    """
    if not pipeline_run.started_at:
        return []

    base_time = pipeline_run.started_at
    total_duration = max(pipeline_run.duration_seconds, 1)

    timeline = []
    # Sort activities by started_at or id
    activities = sorted(
        pipeline_run.activity_runs or [],
        key=lambda a: (a.started_at or base_time, a.id)
    )

    for act in activities:
        act_start = act.started_at or base_time
        offset_seconds = max(0, int((act_start - base_time).total_seconds()))
        duration = act.duration_seconds
        
        # Calculate percentage position on timeline
        start_pct = round(min(100.0, (offset_seconds / total_duration) * 100), 2)
        width_pct = round(max(1.0, min(100.0 - start_pct, (duration / total_duration) * 100)), 2)

        timeline.append({
            "activity_id": act.activity_id,
            "activity_name": act.activity_name,
            "activity_type": act.activity_type,
            "status": act.status,
            "started_at": act.started_at.isoformat() if act.started_at else None,
            "ended_at": act.ended_at.isoformat() if act.ended_at else None,
            "duration_seconds": duration,
            "offset_seconds": offset_seconds,
            "start_percentage": start_pct,
            "width_percentage": width_pct,
            "retry_attempt": act.retry_attempt,
            "rows_read": act.rows_read,
            "rows_written": act.rows_written,
            "bytes_processed": act.bytes_processed,
            "error_classification": act.error_classification,
            "error_message": act.error_message,
            "worker_info": act.worker_info or {}
        })

    return timeline


def build_metrics_summary(pipeline_run: PipelineRun) -> Dict[str, Any]:
    """Calculates comprehensive observability and throughput metrics for an execution."""
    duration = max(pipeline_run.duration_seconds, 1)
    rows_read = pipeline_run.total_rows_read
    rows_written = pipeline_run.total_rows_written
    bytes_processed = getattr(pipeline_run, "total_bytes_processed", 0)

    # If total_bytes_processed is 0, sum from activity_runs
    if bytes_processed == 0 and pipeline_run.activity_runs:
        bytes_processed = sum(a.bytes_processed for a in pipeline_run.activity_runs)

    rows_read_per_sec = round(rows_read / duration, 2)
    rows_written_per_sec = round(rows_written / duration, 2)
    mb_processed = round(bytes_processed / (1024 * 1024), 2)
    mb_per_sec = round(mb_processed / duration, 4)

    status_counts = {
        "Total": pipeline_run.total_activities,
        "Succeeded": pipeline_run.succeeded_activities,
        "Failed": pipeline_run.failed_activities,
        "Skipped": 0,
        "Running": 0,
        "Pending": 0
    }
    total_retries = 0

    if pipeline_run.activity_runs:
        for act in pipeline_run.activity_runs:
            total_retries += act.retry_attempt
            if act.status in status_counts:
                if act.status not in ("Succeeded", "Failed"):
                    status_counts[act.status] += 1
            else:
                status_counts[act.status] = 1

    success_rate = (
        round((pipeline_run.succeeded_activities / max(pipeline_run.total_activities, 1)) * 100, 1)
        if pipeline_run.total_activities > 0 else 0.0
    )

    return {
        "pipeline_run_id": pipeline_run.id,
        "status": pipeline_run.status,
        "duration_seconds": pipeline_run.duration_seconds,
        "started_at": pipeline_run.started_at.isoformat() if pipeline_run.started_at else None,
        "ended_at": pipeline_run.ended_at.isoformat() if pipeline_run.ended_at else None,
        "data_movement": {
            "total_rows_read": rows_read,
            "total_rows_written": rows_written,
            "total_bytes_processed": bytes_processed,
            "total_mb_processed": mb_processed,
            "read_throughput_rows_sec": rows_read_per_sec,
            "write_throughput_rows_sec": rows_written_per_sec,
            "throughput_mb_sec": mb_per_sec
        },
        "activity_summary": {
            "counts": status_counts,
            "success_rate_percentage": success_rate,
            "total_retry_attempts": total_retries
        },
        "worker_info": pipeline_run.worker_info or {},
        "error_summary": pipeline_run.error_summary
    }


def generate_execution_report(pipeline_run: PipelineRun, format: str = "json") -> Any:
    """Generates an executive downloadable execution report in JSON, CSV, or Text format."""
    metrics = build_metrics_summary(pipeline_run)
    timeline = build_timeline(pipeline_run)

    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        # Executive Header
        writer.writerow(["# DATAFLOW ENTERPRISE EXECUTION REPORT"])
        writer.writerow(["Run ID", pipeline_run.id])
        writer.writerow(["Pipeline ID", pipeline_run.pipeline_id])
        writer.writerow(["Status", pipeline_run.status])
        writer.writerow(["Started At", pipeline_run.started_at.isoformat() if pipeline_run.started_at else ""])
        writer.writerow(["Ended At", pipeline_run.ended_at.isoformat() if pipeline_run.ended_at else ""])
        writer.writerow(["Duration (seconds)", pipeline_run.duration_seconds])
        writer.writerow(["Total Rows Read", pipeline_run.total_rows_read])
        writer.writerow(["Total Rows Written", pipeline_run.total_rows_written])
        writer.writerow(["Total Bytes Processed", metrics["data_movement"]["total_bytes_processed"]])
        writer.writerow(["Throughput (Rows/Sec)", metrics["data_movement"]["write_throughput_rows_sec"]])
        writer.writerow([])

        # Activity Breakdown Table
        writer.writerow([
            "Activity ID", "Activity Name", "Type", "Status", "Duration (s)",
            "Rows Read", "Rows Written", "Bytes Processed", "Retries",
            "Error Classification", "Error Message"
        ])
        for act in pipeline_run.activity_runs or []:
            writer.writerow([
                act.activity_id,
                act.activity_name,
                act.activity_type,
                act.status,
                act.duration_seconds,
                act.rows_read,
                act.rows_written,
                act.bytes_processed,
                act.retry_attempt,
                act.error_classification or "",
                (act.error_message or "").replace("\n", " ")
            ])
        return output.getvalue()

    elif format.lower() == "text":
        lines = [
            "=" * 80,
            " DATAFLOW ENTERPRISE - PIPELINE EXECUTION LEDGER REPORT",
            "=" * 80,
            f"Run ID:            {pipeline_run.id}",
            f"Pipeline ID:       {pipeline_run.pipeline_id}",
            f"Status:            {pipeline_run.status.upper()}",
            f"Started At:        {pipeline_run.started_at.isoformat() if pipeline_run.started_at else 'N/A'}",
            f"Ended At:          {pipeline_run.ended_at.isoformat() if pipeline_run.ended_at else 'N/A'}",
            f"Duration:          {pipeline_run.duration_seconds}s",
            f"Ingestion Metrics: {pipeline_run.total_rows_written:,} rows written | {metrics['data_movement']['total_mb_processed']} MB ({metrics['data_movement']['throughput_mb_sec']} MB/s)",
            f"Activities:        {pipeline_run.succeeded_activities}/{pipeline_run.total_activities} Succeeded",
            "-" * 88,
            f"{'ACTIVITY (ID / NAME)':<36} {'TYPE':<16} {'STATUS':<10} {'TIME':<6} {'ROWS OUT':<10} {'RETRIES'}",
            "-" * 88
        ]
        for act in pipeline_run.activity_runs or []:
            name_and_id = f"{act.activity_id} ({act.activity_name})"[:34]
            lines.append(
                f"{name_and_id:<36} {act.activity_type[:14]:<16} {act.status:<10} {act.duration_seconds}s{' '*(5-len(str(act.duration_seconds)))} {act.rows_written:<10} {act.retry_attempt}"
            )
        lines.append("=" * 88)
        if pipeline_run.error_summary:
            lines.append(f"ERROR SUMMARY:\n{pipeline_run.error_summary}")
            lines.append("=" * 88)
        return "\n".join(lines)

    # Default: JSON
    return {
        "report_type": "DataFlow Pipeline Execution Summary",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": pipeline_run.id,
        "pipeline_id": pipeline_run.pipeline_id,
        "status": pipeline_run.status,
        "metrics": metrics,
        "timeline": timeline,
        "activities": [
            {
                "id": a.id,
                "activity_id": a.activity_id,
                "activity_name": a.activity_name,
                "activity_type": a.activity_type,
                "status": a.status,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "ended_at": a.ended_at.isoformat() if a.ended_at else None,
                "duration_seconds": a.duration_seconds,
                "rows_read": a.rows_read,
                "rows_written": a.rows_written,
                "bytes_processed": a.bytes_processed,
                "retry_attempt": a.retry_attempt,
                "error_classification": a.error_classification,
                "error_message": a.error_message,
                "worker_info": a.worker_info or {},
                "retry_history": a.retry_history or []
            }
            for a in pipeline_run.activity_runs or []
        ]
    }
