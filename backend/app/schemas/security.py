from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class EnvironmentBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False
    variables: Dict[str, Any] = {}


class EnvironmentCreate(EnvironmentBase):
    pass


class EnvironmentResponse(EnvironmentBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class SecretCreate(BaseModel):
    name: str
    value: str
    description: Optional[str] = None


class SecretResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    vault_provider: str
    is_masked: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SecretRotateRequest(BaseModel):
    new_encryption_key: str


class WorkspaceMemberCreate(BaseModel):
    user_id: str
    role: str = "Viewer"  # Owner, Contributor, Operator, Viewer


class WorkspaceMemberResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class PipelinePromoteRequest(BaseModel):
    target_environment: str  # Test, Prod, Staging
    parameter_overrides: Dict[str, Any] = {}


class PipelineRollbackRequest(BaseModel):
    version_number: int


class PipelineGitImportRequest(BaseModel):
    project_id: str
    spec: Dict[str, Any]


class AuditLogResponse(BaseModel):
    id: int
    workspace_id: Optional[str] = None
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True
