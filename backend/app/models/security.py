from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="Viewer", nullable=False)  # Owner, Contributor, Operator, Viewer
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    workspace = relationship("Workspace", backref="members")
    user = relationship("User", backref="workspace_memberships")


class Environment(Base):
    __tablename__ = "environments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, index=True, nullable=False)  # Dev, Test, Prod, Staging
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    variables = Column(JSON, default=dict, nullable=False)  # Environment-specific configuration & parameters
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SecretVaultEntry(Base):
    __tablename__ = "secret_vault_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    encrypted_value = Column(Text, nullable=False)
    vault_provider = Column(String(50), default="AES-256-Fernet", nullable=False)
    created_by_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
