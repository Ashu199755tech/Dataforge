import io
from fastapi import APIRouter, Depends, HTTPException, Query, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from backend.app.core.database import get_db
from backend.app.models.execution import PipelineRun, ActivityRun, ExecutionLog
from backend.app.models.pipeline import Pipeline
from backend.app.schemas.execution import PipelineRunResponse, ActivityRunResponse, LogResponse
from backend.app.api.deps import get_current_user
from backend.app.models.user import User
from backend.app.monitoring.metrics import (
    build_timeline,
    build_metrics_summary,
    generate_execution_report
)
from backend.app.execution.runner import PipelineRunner

router = APIRouter(prefix="/runs", tags=["Pipeline Runs & Monitoring"])


@router.get("", response_model=List[PipelineRunResponse])
def list_runs(
    pipeline_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(PipelineRun).order_by(PipelineRun.started_at.desc())
    if pipeline_id:
        query = query.filter(PipelineRun.pipeline_id == pipeline_id)
    if status:
        query = query.filter(PipelineRun.status == status)
    return query.limit(limit).all()


@router.get("/{run_id}", response_model=PipelineRunResponse)
def get_run(run_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.get("/{run_id}/timeline")
def get_run_timeline(run_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns high-resolution timeline/Gantt telemetry for the pipeline run and its activities."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return {
        "pipeline_run_id": run.id,
        "status": run.status,
        "duration_seconds": run.duration_seconds,
        "timeline": build_timeline(run)
    }


@router.get("/{run_id}/metrics")
def get_run_metrics(run_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns comprehensive throughput, latency, and data movement metrics."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return build_metrics_summary(run)


@router.get("/{run_id}/report")
def get_execution_report(
    run_id: str,
    format: str = Query("json", pattern="^(json|csv|text)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Downloads an executive execution report in JSON, CSV, or Text format.
    Derived completely from actual execution and telemetry records.
    """
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    content = generate_execution_report(run, format=format)

    if format == "csv":
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="dataflow_run_{run_id[:8]}.csv"'}
        )
    elif format == "text":
        return PlainTextResponse(content=content)
    else:
        return content


@router.get("/{run_id}/activities/{activity_id}/diagnostics")
def get_activity_diagnostics(
    run_id: str,
    activity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns deep diagnostic observability for an activity: errors, classifications, stack traces, retries, and worker info."""
    act_run = db.query(ActivityRun).filter(
        ActivityRun.pipeline_run_id == run_id,
        ActivityRun.activity_id == activity_id
    ).first()
    if not act_run:
        raise HTTPException(status_code=404, detail="Activity run not found")

    return {
        "id": act_run.id,
        "activity_id": act_run.activity_id,
        "activity_name": act_run.activity_name,
        "activity_type": act_run.activity_type,
        "status": act_run.status,
        "duration_seconds": act_run.duration_seconds,
        "started_at": act_run.started_at.isoformat() if act_run.started_at else None,
        "ended_at": act_run.ended_at.isoformat() if act_run.ended_at else None,
        "rows_read": act_run.rows_read,
        "rows_written": act_run.rows_written,
        "bytes_processed": act_run.bytes_processed,
        "retry_attempt": act_run.retry_attempt,
        "retry_history": act_run.retry_history or [],
        "worker_info": act_run.worker_info or {},
        "error_classification": act_run.error_classification,
        "error_message": act_run.error_message,
        "error_stack_trace": act_run.error_stack_trace,
        "metrics": act_run.metrics or {},
        "output_variables": act_run.output_variables or {}
    }


@router.get("/{run_id}/activities/{activity_id}/logs", response_model=List[LogResponse])
def get_activity_logs(run_id: str, activity_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    act_run = db.query(ActivityRun).filter(
        ActivityRun.pipeline_run_id == run_id,
        ActivityRun.activity_id == activity_id
    ).first()
    if not act_run:
        raise HTTPException(status_code=404, detail="Activity run not found")
    return db.query(ExecutionLog).filter(ExecutionLog.activity_run_id == act_run.id).order_by(ExecutionLog.timestamp.asc()).all()


@router.post("/{run_id}/cancel")
def cancel_run(run_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Cancels an ongoing pipeline execution."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status in ("Succeeded", "Failed", "Cancelled"):
        return {"message": f"Run already in terminal state: {run.status}", "status": run.status}

    run.status = "Cancelled"
    run.ended_at = datetime.now(timezone.utc)
    run.error_summary = "Execution cancelled by user."
    db.commit()
    return {"message": "Run cancelled successfully", "status": "Cancelled"}


@router.post("/{run_id}/rerun", response_model=PipelineRunResponse)
def rerun_pipeline(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Triggers a new rerun of the pipeline based on the original parameters."""
    original_run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not original_run:
        raise HTTPException(status_code=404, detail="Original pipeline run not found")

    new_run = PipelineRun(
        pipeline_id=original_run.pipeline_id,
        run_type="Rerun",
        status="Pending",
        parameters=original_run.parameters or {}
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    runner = PipelineRunner(new_run.id)
    background_tasks.add_task(runner.execute_sync)
    return new_run
