from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Integer, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    target_type = Column(String(50), default="Pipeline", nullable=False)  # Pipeline, Global, DataQuality
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=True)
    condition_type = Column(String(50), nullable=False)  # OnFailure, OnSuccess, DurationExceeded, SLAThreshold, DQScoreThreshold
    threshold_value = Column(Float, nullable=True)  # SLA duration in seconds or DQ score threshold (0.0 - 100.0)
    action_type = Column(String(50), default="Log", nullable=False)  # Log, Webhook, Email, Slack, Teams
    action_config = Column(JSON, default=dict, nullable=False)  # webhook_url, recipients, channel, headers, smtp_config
    cooldown_minutes = Column(Integer, default=5, nullable=False)  # Cooldown suppression window
    last_triggered_at = Column(DateTime, nullable=True)  # Deduplication tracking
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    pipeline = relationship("Pipeline", backref="alert_rules")
    events = relationship("AlertEvent", back_populates="alert_rule", cascade="all, delete-orphan")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_rule_id = Column(String(36), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=True)
    activity_run_id = Column(String(36), ForeignKey("activity_runs.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    severity = Column(String(20), default="Warning", nullable=False)  # Info, Warning, Critical
    message = Column(Text, nullable=False)
    payload = Column(JSON, default=dict, nullable=False)
    status = Column(String(30), default="Triggered", nullable=False)  # Triggered, Delivered, Failed
    delivered_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    alert_rule = relationship("AlertRule", back_populates="events")
    pipeline_run = relationship("PipelineRun", backref="alert_events")
    activity_run = relationship("ActivityRun", backref="alert_events")
