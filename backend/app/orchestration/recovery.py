import os
from typing import Optional, Tuple
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.core.audit import record_audit


def enforce_concurrency_and_idempotency(
    pipeline: Pipeline,
    idempotency_key: Optional[str],
    db: Session
) -> Optional[PipelineRun]:
    """
    1. Idempotency Check: If an idempotency_key was submitted within the last 15 minutes,
       returns the existing PipelineRun to prevent duplicate execution.
    2. Concurrency Check: Counts active runs (Pending, Running). If active_count >= concurrency_limit,
       raises 429 Too Many Requests.
    """
    # 1. Idempotency check
    if idempotency_key:
        window_start = datetime.now(timezone.utc) - timedelta(minutes=15)
        existing_run = db.query(PipelineRun).filter(
            PipelineRun.pipeline_id == pipeline.id,
            PipelineRun.idempotency_key == idempotency_key,
            PipelineRun.started_at >= window_start
        ).order_by(PipelineRun.started_at.desc()).first()

        if existing_run:
            return existing_run

    # 2. Concurrency check
    concurrency_limit = pipeline.concurrency_limit or 5
    active_count = db.query(PipelineRun).filter(
        PipelineRun.pipeline_id == pipeline.id,
        PipelineRun.status.in_(["Pending", "Running"])
    ).count()

    if active_count >= concurrency_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Pipeline '{pipeline.name}' concurrency limit reached ({active_count}/{concurrency_limit} active runs)."
        )

    return None


def recover_orphaned_runs(db: Session, max_orphan_age_seconds: int = 1800) -> int:
    """
    Scans for orphaned runs in 'Running' status whose worker PID is no longer alive
    or whose execution has exceeded the maximum orphan age threshold.
    Transitions them cleanly to 'Failed' with diagnostic notes.
    """
    running_runs = db.query(PipelineRun).filter(PipelineRun.status == "Running").all()
    recovered_count = 0
    now = datetime.now(timezone.utc)

    for run in running_runs:
        is_orphaned = False
        reason = ""

        # Check age
        if run.started_at and (now - run.started_at.replace(tzinfo=timezone.utc)).total_seconds() > max_orphan_age_seconds:
            is_orphaned = True
            reason = f"Execution exceeded maximum run age threshold of {max_orphan_age_seconds}s without heartbeat."

        # Check worker process PID if on local host
        worker_info = run.worker_info or {}
        pid = worker_info.get("pid")
        if pid:
            try:
                # Signal 0 checks if process exists without sending a signal
                os.kill(int(pid), 0)
            except OSError:
                is_orphaned = True
                reason = f"Execution worker PID {pid} is no longer running on host."

        if is_orphaned:
            run.status = "Failed"
            run.ended_at = now
            run.error_summary = f"[ORPHAN_RECOVERY] {reason}"

            # Mark running activities as Failed
            for act in run.activity_runs or []:
                if act.status == "Running":
                    act.status = "Failed"
                    act.error_classification = "SystemError"
                    act.error_message = "[ORPHAN_RECOVERY] Worker process terminated unexpectedly."
                    act.ended_at = now

            recovered_count += 1
            record_audit(
                db=db,
                action="RUN_ORPHAN_RECOVERY",
                resource_type="PipelineRun",
                resource_id=run.id,
                details={"reason": reason}
            )

    if recovered_count > 0:
        db.commit()

    return recovered_count
