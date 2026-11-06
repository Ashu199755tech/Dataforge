from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ExecutionEngineStrategy(str, Enum):
    AUTO = "AUTO"
    FORCE_COPY = "FORCE_COPY"
    FORCE_SPARK = "FORCE_SPARK"
    FORCE_SQL_PUSHDOWN = "FORCE_SQL_PUSHDOWN"


class PlanActivityRequest(BaseModel):
    activity_type: str = "CopyData"
    activity_config: Dict[str, Any] = {}
    strategy: Optional[str] = "AUTO"


class PlanActivityResponse(BaseModel):
    selected_engine: str
    strategy_applied: str
    confidence_score: float
    scores: Dict[str, float] = {}
    explanation: str
    primary_reason: str
    fallback_engine: Optional[str] = None
    estimated_egress_bytes: Optional[int] = None
    profile_summary: Dict[str, Any] = {}


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
