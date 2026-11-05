from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.deployment import Deployment
from backend.app.models.workspace import Project
from backend.app.models.user import User
from backend.app.schemas.deployment import (
    DeploymentCreateRequest,
    DeploymentDryRunRequest,
    DeploymentDryRunResponse,
    DeploymentApprovalRequest,
    DeploymentResponse
)
from backend.app.services.cicd_service import CiCdService
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/deployments", tags=["CI/CD & Deployments"])


def _resolve_project_id(project_id: Optional[str], db: Session) -> str:
    if project_id:
        return project_id
    proj = db.query(Project).first()
    if not proj:
        raise HTTPException(status_code=404, detail="No active project found in workspace.")
    return proj.id


@router.post("/dry-run", response_model=DeploymentDryRunResponse)
def pre_validate_deployment(
    req: DeploymentDryRunRequest,
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Executes pre-validation and dry-run comparison between source and target environments."""
    pid = _resolve_project_id(project_id, db)
    return CiCdService.create_dry_run(db, pid, req)


@router.post("", response_model=DeploymentResponse)
def create_deployment_release(
    req: DeploymentCreateRequest,
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a deployment release bundle and schedules approval gates."""
    pid = _resolve_project_id(project_id, db)
    try:
        return CiCdService.create_deployment(db, pid, req, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[DeploymentResponse])
def list_deployments(
    target_environment: Optional[str] = None,
    status: Optional[str] = None,
    project_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists release deployments with optional target environment and status filters."""
    pid = _resolve_project_id(project_id, db)
    query = db.query(Deployment).filter(Deployment.project_id == pid)
    if target_environment:
        query = query.filter(Deployment.target_environment == target_environment)
    if status:
        query = query.filter(Deployment.status == status)
    return query.order_by(Deployment.created_at.desc()).limit(limit).all()


@router.get("/{deployment_id}", response_model=DeploymentResponse)
def get_deployment(
    deployment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves deployment details, asset manifests, and approval state."""
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment release not found.")
    return deployment


@router.post("/{deployment_id}/approve", response_model=DeploymentResponse)
def approve_deployment(
    deployment_id: str,
    req: DeploymentApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approves a deployment release gate."""
    try:
        if req.approved:
            return CiCdService.approve_deployment(db, deployment_id, current_user, req.comment)
        else:
            return CiCdService.reject_deployment(db, deployment_id, current_user, req.comment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/execute", response_model=DeploymentResponse)
def execute_deployment(
    deployment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Executes promotion of approved release assets to target environment."""
    try:
        return CiCdService.execute_deployment(db, deployment_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{deployment_id}/rollback", response_model=DeploymentResponse)
def rollback_deployment(
    deployment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Rolls back an executed deployment release to prior asset versions."""
    try:
        return CiCdService.rollback_deployment(db, deployment_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/template/github-actions")
def get_github_actions_workflow_template(
    project_name: str = Query("DataForge-Enterprise"),
    repo_name: str = Query("dataforge-pipelines"),
    target_branch: str = Query("main"),
    current_user: User = Depends(get_current_user)
):
    """Generates and returns production GitHub Actions CI/CD release workflow YAML."""
    yaml_content = CiCdService.generate_github_actions_workflow(project_name, repo_name, target_branch)
    return Response(content=yaml_content, media_type="application/x-yaml")
