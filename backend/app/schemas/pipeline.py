from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class PipelineBase(BaseModel):
    name: str
    description: Optional[str] = None
    definition_json: Dict[str, Any] = {}


class PipelineCreate(PipelineBase):
    project_id: str


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    definition_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class PipelineResponse(PipelineBase):
    id: str
    project_id: str
    status: str
    current_version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PipelineRunRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = {}
