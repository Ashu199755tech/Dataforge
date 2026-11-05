from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.models.execution import PipelineRun, ActivityRun, ExecutionLog
from backend.app.schemas.execution import PipelineRunResponse, ActivityRunResponse, LogResponse
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

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


@router.get("/{run_id}/activities/{activity_id}/logs", response_model=List[LogResponse])
def get_activity_logs(run_id: str, activity_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    act_run = db.query(ActivityRun).filter(
        ActivityRun.pipeline_run_id == run_id,
        ActivityRun.activity_id == activity_id
    ).first()
    if not act_run:
        raise HTTPException(status_code=404, detail="Activity run not found")
    return db.query(ExecutionLog).filter(ExecutionLog.activity_run_id == act_run.id).order_by(ExecutionLog.timestamp.asc()).all()
