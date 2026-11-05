import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Deployment(Base):
    """
    CI/CD Release Deployment and Environment Promotion Model.
    Tracks asset promotion across environments (Dev -> Test -> Staging -> Prod),
    parameter substitutions, dry-run comparison diffs, and approval workflows.
    """
    __tablename__ = "deployments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_environment = Column(String(50), default="Dev", nullable=False)
    target_environment = Column(String(50), default="Test", nullable=False)
    bundle_version = Column(String(50), nullable=False)  # e.g., v1.0.0
    
    # Status: PendingApproval, Approved, Rejected, Deployed, Failed, RolledBack
    status = Column(String(50), default="PendingApproval", nullable=False, index=True)

    # Asset Manifests & Substitutions
    pipeline_ids = Column(JSON, default=list, nullable=False)
    dataset_ids = Column(JSON, default=list, nullable=False)
    trigger_ids = Column(JSON, default=list, nullable=False)
    parameter_substitutions = Column(JSON, default=dict, nullable=False)
    manifest_json = Column(JSON, default=dict, nullable=False)  # Canonical snapshot of assets deployed
    dry_run_diff = Column(JSON, default=dict, nullable=False)   # Pre-validation and comparison diff

    # Approval Gates & Audit
    requested_by_id = Column(String(36), nullable=True)
    approved_by_id = Column(String(36), nullable=True)
    approval_comment = Column(Text, nullable=True)
    deployed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", backref="deployments")
