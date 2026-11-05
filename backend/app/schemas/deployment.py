from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class DeploymentCreateRequest(BaseModel):
    """Request to create and schedule a deployment promotion between environments."""
    source_environment: str = "Dev"
    target_environment: str = "Test"
    bundle_version: str = "v1.0.0"
    pipeline_ids: List[str] = Field(default_factory=list)
    dataset_ids: List[str] = Field(default_factory=list)
    trigger_ids: List[str] = Field(default_factory=list)
    parameter_substitutions: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class DeploymentDryRunRequest(BaseModel):
    """Request for dry-run validation and comparison prior to deployment."""
    source_environment: str = "Dev"
    target_environment: str = "Test"
    pipeline_ids: List[str] = Field(default_factory=list)
    dataset_ids: List[str] = Field(default_factory=list)
    trigger_ids: List[str] = Field(default_factory=list)
    parameter_substitutions: Dict[str, Any] = Field(default_factory=dict)


class DeploymentDryRunResponse(BaseModel):
    """Pre-validation report with warnings, asset diffs, and parameter substitutions."""
    source_environment: str
    target_environment: str
    can_deploy: bool
    warnings: List[str] = Field(default_factory=list)
    diff_summary: Dict[str, int] = Field(default_factory=dict)  # {"added": 2, "modified": 1, "unchanged": 3}
    asset_diffs: List[Dict[str, Any]] = Field(default_factory=list)
    parameter_substitutions: Dict[str, Any] = Field(default_factory=dict)


class DeploymentApprovalRequest(BaseModel):
    """Approval or rejection decision for a pending deployment gate."""
    approved: bool
    comment: Optional[str] = None


class DeploymentResponse(BaseModel):
    """Full deployment record including asset manifest and approval state."""
    id: str
    project_id: str
    source_environment: str
    target_environment: str
    bundle_version: str
    status: str
    pipeline_ids: List[str] = Field(default_factory=list)
    dataset_ids: List[str] = Field(default_factory=list)
    trigger_ids: List[str] = Field(default_factory=list)
    parameter_substitutions: Dict[str, Any] = Field(default_factory=dict)
    manifest_json: Dict[str, Any] = Field(default_factory=dict)
    dry_run_diff: Dict[str, Any] = Field(default_factory=dict)
    requested_by_id: Optional[str] = None
    approved_by_id: Optional[str] = None
    approval_comment: Optional[str] = None
    deployed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
