from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.models.connection import Connection
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total_pipelines = db.query(Pipeline).count()
    active_pipelines = db.query(Pipeline).filter(Pipeline.status.in_(["Published", "Draft"])).count()

    total_runs = db.query(PipelineRun).count()
    successful_runs = db.query(PipelineRun).filter(PipelineRun.status == "Succeeded").count()
    failed_runs = db.query(PipelineRun).filter(PipelineRun.status == "Failed").count()
    running_runs = db.query(PipelineRun).filter(PipelineRun.status == "Running").count()

    success_rate = round((successful_runs / total_runs) * 100.0, 1) if total_runs > 0 else 100.0

    total_rows_read = db.query(func.coalesce(func.sum(PipelineRun.total_rows_read), 0)).scalar()
    total_rows_written = db.query(func.coalesce(func.sum(PipelineRun.total_rows_written), 0)).scalar()

    total_connections = db.query(Connection).count()
    active_connections = db.query(Connection).filter(Connection.status == "Active").count()
    failed_connections = db.query(Connection).filter(Connection.status == "Failed").count()

    recent_runs = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(10).all()

    return {
        "pipelines": {
            "total": total_pipelines,
            "active": active_pipelines
        },
        "runs": {
            "total": total_runs,
            "successful": successful_runs,
            "failed": failed_runs,
            "running": running_runs,
            "success_rate_percent": success_rate
        },
        "volume": {
            "total_rows_read": total_rows_read,
            "total_rows_written": total_rows_written
        },
        "connections": {
            "total": total_connections,
            "active": active_connections,
            "failed": failed_connections
        },
        "recent_activity": [
            {
                "id": r.id,
                "pipeline_id": r.pipeline_id,
                "status": r.status,
                "run_type": r.run_type,
                "started_at": r.started_at,
                "duration_seconds": r.duration_seconds,
                "rows_written": r.total_rows_written
            }
            for r in recent_runs
        ]
    }
