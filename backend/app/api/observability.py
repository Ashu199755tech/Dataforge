from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import Optional

from backend.app.core.database import get_db
from backend.app.api.deps import get_current_user
from backend.app.models.user import User
from backend.app.models.workspace import Project
from backend.app.schemas.observability import (
    ObservabilityOverview,
    CopyDataPerformanceMetrics,
    RuntimeFleetOverview,
    FailureDiagnosticsResponse,
    OtelTraceResponse
)
from backend.app.services.observability_service import ObservabilityService

router = APIRouter(prefix="/observability", tags=["Observability & Metrics"])


def _resolve_project_id(project_id: Optional[str], db: Session) -> str:
    """Helper to resolve or fallback to first available project."""
    if project_id:
        return project_id
    first_project = db.query(Project).first()
    if not first_project:
        raise HTTPException(status_code=400, detail="No projects found in workspace.")
    return first_project.id


@router.get("/overview", response_model=ObservabilityOverview)
def get_observability_overview(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns high-level platform observability, performance metrics, fleet health, and failure clustering."""
    pid = _resolve_project_id(project_id, db)
    return ObservabilityService.get_observability_overview(db, pid)


@router.get("/copy-performance", response_model=CopyDataPerformanceMetrics)
def get_copy_data_performance(
    project_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=10, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns detailed throughput MB/s, volume transferred, and transfer duration trends for Copy Data activities."""
    pid = _resolve_project_id(project_id, db)
    return ObservabilityService.get_copy_data_performance(db, pid, limit)


@router.get("/fleet-health", response_model=RuntimeFleetOverview)
def get_runtime_fleet_health(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns fleet-wide capacity, CPU/RAM telemetry, active tasks, and online status across all Integration Runtimes."""
    pid = _resolve_project_id(project_id, db)
    return ObservabilityService.get_runtime_fleet_overview(db, pid)


@router.get("/failure-diagnostics", response_model=FailureDiagnosticsResponse)
def get_failure_diagnostics(
    project_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Analyzes and clusters failed runs to provide root cause categories and remediation steps."""
    pid = _resolve_project_id(project_id, db)
    return ObservabilityService.get_failure_clustering(db, pid, days)


@router.get("/traces/{pipeline_run_id}", response_model=OtelTraceResponse)
def get_opentelemetry_trace(
    pipeline_run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns an OpenTelemetry-compatible distributed trace for a specific pipeline execution."""
    try:
        return ObservabilityService.export_opentelemetry_trace(db, pipeline_run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/metrics")
def get_prometheus_metrics(
    db: Session = Depends(get_db)
):
    """Prometheus metrics endpoint returning plain text metrics format for scraper agents."""
    metrics_text = ObservabilityService.export_prometheus_metrics(db)
    return Response(content=metrics_text, media_type="text/plain; version=0.0.4; charset=utf-8")
