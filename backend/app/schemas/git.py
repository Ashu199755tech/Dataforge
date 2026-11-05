from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class GitRepositoryConfig(BaseModel):
    """Configuration for connecting a workspace/project to Git."""
    repo_url: str
    provider: str = "github"  # github, gitlab, azure_devops
    default_branch: str = "main"
    current_branch: str = "main"
    root_folder: str = "/"
    auth_type: str = "pat"  # pat, oauth, ssh_key
    token: Optional[str] = None  # PAT or access token (encrypted upon receipt)


class GitRepositoryResponse(BaseModel):
    """Public Git repository connection status and metadata."""
    id: str
    project_id: str
    name: str
    provider: str
    repo_url: str
    default_branch: str
    current_branch: str
    root_folder: str
    auth_type: str
    last_commit_hash: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    sync_status: str
    is_connected: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GitBranchInfo(BaseModel):
    """Branch metadata and tracking status."""
    name: str
    is_current: bool = False
    is_default: bool = False
    commit_hash: Optional[str] = None
    commit_message: Optional[str] = None
    author: Optional[str] = None


class GitBranchSwitchRequest(BaseModel):
    """Request to switch active working branch or create a new branch."""
    branch_name: str
    create_new: bool = False
    source_branch: Optional[str] = "main"


class GitCommitRequest(BaseModel):
    """Request to commit and push local workspace changes to remote Git."""
    branch: Optional[str] = None
    message: str
    author_name: Optional[str] = None
    author_email: Optional[str] = None


class GitFileDiff(BaseModel):
    """Represents a single asset diff between workspace and Git repository."""
    path: str
    asset_type: str  # pipeline, dataset, trigger, connection, dataflow
    asset_name: str
    status: str      # added, modified, deleted, unchanged
    old_content: Optional[str] = None
    new_content: Optional[str] = None


class GitDiffResponse(BaseModel):
    """Summary and details of differences between local workspace and Git tree."""
    branch: str
    total_changes: int
    files: List[GitFileDiff] = Field(default_factory=list)
