from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.workspace import Project
from backend.app.models.user import User
from backend.app.schemas.git import (
    GitRepositoryConfig,
    GitRepositoryResponse,
    GitBranchInfo,
    GitBranchSwitchRequest,
    GitCommitRequest,
    GitDiffResponse
)
from backend.app.services.git_service import GitService
from backend.app.api.deps import get_current_user

router = APIRouter(prefix="/git", tags=["Git Version Control"])


def _resolve_project_id(project_id: Optional[str], db: Session) -> str:
    if project_id:
        return project_id
    proj = db.query(Project).first()
    if not proj:
        raise HTTPException(status_code=404, detail="No active project found in workspace.")
    return proj.id


@router.post("/connect", response_model=GitRepositoryResponse)
def connect_git_repository(
    config: GitRepositoryConfig,
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Connects a workspace project to a remote Git repository (GitHub/GitLab/Azure DevOps)."""
    pid = _resolve_project_id(project_id, db)
    try:
        repo = GitService.connect_repository(db, pid, config, current_user)
        return repo
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect Git repository: {str(e)}")


@router.get("/config", response_model=Optional[GitRepositoryResponse])
def get_git_repository_config(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves current Git repository connection configuration and sync status."""
    pid = _resolve_project_id(project_id, db)
    repo = GitService.get_repository(db, pid)
    return repo


@router.get("/branches", response_model=List[GitBranchInfo])
def list_git_branches(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists tracked branches and current working branch."""
    pid = _resolve_project_id(project_id, db)
    return GitService.get_branches(db, pid)


@router.post("/switch-branch", response_model=GitRepositoryResponse)
def switch_git_branch(
    req: GitBranchSwitchRequest,
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Switches active branch or creates a new branch from a source branch."""
    pid = _resolve_project_id(project_id, db)
    try:
        repo = GitService.switch_branch(db, pid, req, current_user)
        return repo
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/diff", response_model=GitDiffResponse)
def get_git_diff(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculates granular working differences between local workspace and Git tree."""
    pid = _resolve_project_id(project_id, db)
    try:
        return GitService.compute_diff(db, pid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/commit")
def commit_and_push_changes(
    req: GitCommitRequest,
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Commits and pushes local workspace canonical JSON assets to the remote repository."""
    pid = _resolve_project_id(project_id, db)
    try:
        return GitService.commit_and_push(db, pid, req, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pull")
def pull_and_sync_changes(
    branch: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Pulls and syncs canonical assets from remote repository into local workspace."""
    pid = _resolve_project_id(project_id, db)
    try:
        return GitService.pull_and_sync(db, pid, branch, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disconnect")
def disconnect_git_repository(
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Disconnects repository, switching workspace to disconnected live edit mode."""
    pid = _resolve_project_id(project_id, db)
    success = GitService.disconnect_repository(db, pid, current_user)
    return {"message": "Repository disconnected successfully", "disconnected": success}
