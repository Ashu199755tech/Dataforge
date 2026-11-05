from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    workspace_id: str


class ProjectResponse(ProjectBase):
    id: str
    workspace_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class WorkspaceBase(BaseModel):
    name: str
    description: Optional[str] = None


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceResponse(WorkspaceBase):
    id: str
    created_at: datetime
    projects: List[ProjectResponse] = []

    class Config:
        from_attributes = True
