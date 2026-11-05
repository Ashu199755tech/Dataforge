from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Integer, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), default="Draft", nullable=False)  # Draft, Published, Archived
    definition_json = Column(JSON, nullable=False, default=dict)
    current_version = Column(Integer, default=1, nullable=False)
    concurrency_limit = Column(Integer, default=5, nullable=False)
    environment_id = Column(String(36), nullable=True)
    runtime_id = Column(String(36), ForeignKey("integration_runtimes.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="pipelines")
    runtime = relationship("IntegrationRuntime", backref="pipelines")
    versions = relationship("PipelineVersion", back_populates="pipeline", cascade="all, delete-orphan")
    runs = relationship("PipelineRun", back_populates="pipeline", cascade="all, delete-orphan")
    triggers = relationship("Trigger", back_populates="pipeline", cascade="all, delete-orphan")


class PipelineVersion(Base):
    __tablename__ = "pipeline_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    definition_json = Column(JSON, nullable=False)
    changelog = Column(Text, nullable=True)
    created_by_id = Column(String(36), nullable=True)
    git_commit_hash = Column(String(40), nullable=True)
    environment_name = Column(String(50), default="Dev", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pipeline = relationship("Pipeline", back_populates="versions")


class Trigger(Base):
    __tablename__ = "triggers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    trigger_type = Column(String(50), default="cron", nullable=False)  # cron, manual, event
    cron_expression = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    parameters = Column(JSON, default=dict, nullable=False)
    last_fired_at = Column(DateTime, nullable=True)
    next_fire_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    pipeline = relationship("Pipeline", back_populates="triggers")
