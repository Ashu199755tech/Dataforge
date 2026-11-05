from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.models.workspace import Workspace, Project
from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceResponse, ProjectCreate, ProjectResponse
from backend.app.api.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(tags=["Workspaces & Projects"])


@router.get("/workspaces", response_model=List[WorkspaceResponse])
def list_workspaces(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Workspace).all()


@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace(ws_in: WorkspaceCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing = db.query(Workspace).filter(Workspace.name == ws_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Workspace already exists.")
    ws = Workspace(name=ws_in.name, description=ws_in.description)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


@router.get("/workspaces/{workspace_id}/projects", response_model=List[ProjectResponse])
def list_projects(workspace_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Project).filter(Project.workspace_id == workspace_id).all()


@router.post("/projects", response_model=ProjectResponse)
def create_project(proj_in: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ws = db.query(Workspace).filter(Workspace.id == proj_in.workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    proj = Project(
        workspace_id=proj_in.workspace_id,
        name=proj_in.name,
        description=proj_in.description
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj
