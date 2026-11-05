from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Integer, Boolean, Float, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class IntegrationRuntime(Base):
    __tablename__ = "integration_runtimes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    runtime_type = Column(String(50), default="Cloud", nullable=False)  # Cloud, SelfHosted, LocalDev
    status = Column(String(50), default="Online", nullable=False)       # Online, Offline, Disabled, Registering
    is_enabled = Column(Boolean, default=True, nullable=False)
    
    # Security & Agent Authentication
    registration_key_encrypted = Column(String(500), nullable=True)     # Fernet encrypted token
    registration_key_hash = Column(String(64), nullable=True, index=True) # SHA-256 for fast lookup
    auth_token_hash = Column(String(64), nullable=True, index=True)       # Active agent session token hash
    
    # Agent Host Telemetry & Hardware Metadata
    agent_version = Column(String(50), default="1.0.0", nullable=True)
    agent_os = Column(String(50), default="Linux", nullable=True)         # Linux, Windows, Darwin
    host_name = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    cpu_cores = Column(Integer, default=4, nullable=False)
    cpu_usage_pct = Column(Float, default=0.0, nullable=False)
    memory_total_bytes = Column(BigInteger, default=8589934592, nullable=False) # 8 GB default
    memory_used_bytes = Column(BigInteger, default=0, nullable=False)
    concurrency_limit = Column(Integer, default=4, nullable=False)
    active_task_count = Column(Integer, default=0, nullable=False)
    last_heartbeat_at = Column(DateTime, nullable=True)
    
    # Configuration options & tags
    config = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", backref="runtimes")
    tasks = relationship("RuntimeTask", back_populates="runtime", cascade="all, delete-orphan")


class RuntimeTask(Base):
    __tablename__ = "runtime_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    runtime_id = Column(String(36), ForeignKey("integration_runtimes.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True)
    activity_run_id = Column(String(36), ForeignKey("activity_runs.id", ondelete="SET NULL"), nullable=True)
    
    task_type = Column(String(50), nullable=False)  # CopyData, DataFlow, Script, Web
    status = Column(String(50), default="Queued", nullable=False) # Queued, Dispatched, Running, Completed, Failed, Cancelled
    
    # Payload contains activity config & necessary credentials encrypted
    task_payload_encrypted = Column(Text, nullable=True)
    task_result = Column(JSON, default=dict, nullable=False)
    
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    timeout_seconds = Column(Integer, default=3600, nullable=False)
    assigned_agent_id = Column(String(100), nullable=True)
    
    queued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    dispatched_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    runtime = relationship("IntegrationRuntime", back_populates="tasks")
    pipeline_run = relationship("PipelineRun", backref="runtime_tasks")
    activity_run = relationship("ActivityRun", backref="runtime_tasks")
