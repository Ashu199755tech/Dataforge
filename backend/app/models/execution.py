from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Integer, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    run_type = Column(String(50), default="Manual", nullable=False)  # Manual, Scheduled, Triggered
    idempotency_key = Column(String(64), nullable=True, index=True)
    status = Column(String(30), default="Pending", nullable=False)  # Pending, Running, Succeeded, Failed, Cancelled
    parameters = Column(JSON, default=dict, nullable=False)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0, nullable=False)
    total_activities = Column(Integer, default=0, nullable=False)
    succeeded_activities = Column(Integer, default=0, nullable=False)
    failed_activities = Column(Integer, default=0, nullable=False)
    total_rows_read = Column(BigInteger, default=0, nullable=False)
    total_rows_written = Column(BigInteger, default=0, nullable=False)
    total_bytes_processed = Column(BigInteger, default=0, nullable=False)
    worker_info = Column(JSON, default=dict, nullable=False)  # host, pid, thread_id, runtime
    execution_metrics = Column(JSON, default=dict, nullable=False)  # throughput, latencies, memory
    error_summary = Column(Text, nullable=True)

    pipeline = relationship("Pipeline", back_populates="runs")
    activity_runs = relationship("ActivityRun", back_populates="pipeline_run", cascade="all, delete-orphan")


class ActivityRun(Base):
    __tablename__ = "activity_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    activity_id = Column(String(100), nullable=False)  # Node ID in graph
    activity_name = Column(String(200), nullable=False)
    activity_type = Column(String(50), nullable=False)  # CopyData, SqlScript, etc.
    status = Column(String(30), default="Pending", nullable=False)  # Pending, Running, Succeeded, Failed, Skipped
    retry_attempt = Column(Integer, default=0, nullable=False)
    rows_read = Column(BigInteger, default=0, nullable=False)
    rows_written = Column(BigInteger, default=0, nullable=False)
    bytes_processed = Column(BigInteger, default=0, nullable=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0, nullable=False)
    metrics = Column(JSON, default=dict, nullable=False)
    worker_info = Column(JSON, default=dict, nullable=False)  # host, pid, thread_id
    error_classification = Column(String(50), nullable=True)  # UserError, SystemError, ConnectionError, TimeoutError, DataQualityError
    error_message = Column(Text, nullable=True)
    error_stack_trace = Column(Text, nullable=True)
    retry_history = Column(JSON, default=list, nullable=False)  # list of attempt records
    output_variables = Column(JSON, default=dict, nullable=False)

    pipeline_run = relationship("PipelineRun", back_populates="activity_runs")
    logs = relationship("ExecutionLog", back_populates="activity_run", cascade="all, delete-orphan")


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    activity_run_id = Column(String(36), ForeignKey("activity_runs.id", ondelete="CASCADE"), nullable=False)
    level = Column(String(20), default="INFO", nullable=False)  # INFO, WARNING, ERROR, DEBUG
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    activity_run = relationship("ActivityRun", back_populates="logs")
