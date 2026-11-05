import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Trigger(Base):
    """
    Advanced Multi-Cloud Pipeline Trigger model supporting:
    - Manual Trigger: on-demand parameterized invocation
    - Schedule Trigger: timezone-aware recurrence (cron or frequency/interval) with start/end bounds
    - Storage Event Trigger: event-driven file arrival on Blob, ADLS Gen2, S3, GCS
    - Tumbling Window Trigger: fixed non-overlapping slices, backfills, concurrency & prior window dependency
    - Pipeline Dependency Trigger: upstream pipeline status evaluation with cycle prevention
    """
    __tablename__ = "triggers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    trigger_type = Column(String(50), default="cron", nullable=False)  # manual, schedule, cron, tumbling_window, storage_event, pipeline_dependency
    
    # Target pipeline(s)
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=True)
    pipelines_to_run = Column(JSON, default=list, nullable=False)  # [{"pipeline_id": "...", "pipeline_name": "...", "parameters": {...}}]

    is_active = Column(Boolean, default=True, nullable=False)
    cron_expression = Column(String(100), nullable=True)

    # Type-specific configurations
    schedule_config = Column(JSON, default=dict, nullable=False)
    tumbling_window_config = Column(JSON, default=dict, nullable=False)
    storage_event_config = Column(JSON, default=dict, nullable=False)
    pipeline_dependency_config = Column(JSON, default=dict, nullable=False)

    parameters = Column(JSON, default=dict, nullable=False)
    last_fired_at = Column(DateTime, nullable=True)
    next_fire_time = Column(DateTime, nullable=True)

    # Runtime state for tumbling window pointers, seen storage event etags, upstream run ids
    window_state = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="triggers")
    runs = relationship("TriggerRun", back_populates="trigger", cascade="all, delete-orphan", order_by="desc(TriggerRun.fired_at)")


class TriggerRun(Base):
    """
    Historical log of trigger executions and dispatches.
    Captures event payloads (storage file metadata, window boundaries, upstream pipeline run IDs)
    and maps dispatches to resulting PipelineRun instances.
    """
    __tablename__ = "trigger_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trigger_id = Column(String(36), ForeignKey("triggers.id", ondelete="CASCADE"), nullable=False)
    run_status = Column(String(50), default="Succeeded", nullable=False)  # Succeeded, Failed, Running, Skipped
    fired_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)

    # Resulting pipeline runs dispatched by this trigger execution
    triggered_pipeline_runs = Column(JSON, default=list, nullable=False)  # [{"pipeline_id": "...", "pipeline_run_id": "...", "status": "Pending"}]
    event_payload = Column(JSON, default=dict, nullable=False)  # Event metadata (e.g., file path, size, window start/end)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    trigger = relationship("Trigger", back_populates="runs")
