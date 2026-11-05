import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class GitRepository(Base):
    """
    Git repository connection settings and active sync state.
    Supports GitHub, GitLab, and Azure DevOps integration with branch tracking.
    """
    __tablename__ = "git_repositories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    provider = Column(String(50), default="github", nullable=False)  # github, gitlab, azure_devops
    repo_url = Column(String(255), nullable=False)
    default_branch = Column(String(100), default="main", nullable=False)
    current_branch = Column(String(100), default="main", nullable=False)
    root_folder = Column(String(200), default="/", nullable=False)
    auth_type = Column(String(50), default="pat", nullable=False)  # pat, oauth, ssh_key
    token_encrypted = Column(Text, nullable=True)  # Fernet-encrypted PAT or secret token
    
    # Synchronization State
    last_commit_hash = Column(String(40), nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String(50), default="synced", nullable=False)  # synced, ahead, behind, diverged, disconnected
    is_connected = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", backref="git_repository")
