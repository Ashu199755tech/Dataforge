from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class PipelineBase(BaseModel):
    name: str
    description: Optional[str] = None
    definition_json: Dict[str, Any] = {}
    concurrency_limit: Optional[int] = 5


class PipelineCreate(PipelineBase):
    project_id: str


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    definition_json: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    concurrency_limit: Optional[int] = None


class PipelineResponse(PipelineBase):
    id: str
    project_id: str
    status: str
    current_version: int
    concurrency_limit: int = 5
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PipelineRunRequest(BaseModel):
    parameters: Optional[Dict[str, Any]] = {}
    idempotency_key: Optional[str] = None


class PipelineVersionResponse(BaseModel):
    id: str
    pipeline_id: str
    version_number: int
    definition_json: Dict[str, Any]
    changelog: Optional[str] = None
    environment_name: str = "Dev"
    git_commit_hash: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
