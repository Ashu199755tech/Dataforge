from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Integer, Float, BigInteger, Boolean
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class DataQualityRule(Base):
    __tablename__ = "data_quality_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    rule_name = Column(String(150), nullable=False)
    rule_type = Column(String(50), nullable=False)  # MandatoryFieldCheck, NonBlankCheck, NullValidation, DuplicateCheck, PrimaryKeyUniqueness, ReferentialIntegrity, RangeValidation, DateValidation, ControlledListValidation, SchemaValidation, SchemaDriftDetection, RowCountValidation, PIIDetection
    target_table = Column(String(150), nullable=False)
    target_column = Column(String(150), nullable=True)
    severity = Column(String(20), default="Error", nullable=False)  # Error, Warning
    parameters = Column(JSON, default=dict, nullable=False)
    threshold_percent = Column(Float, default=100.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=True)
    rule_name = Column(String(150), nullable=False)
    rule_type = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False)  # Passed, Failed, Warning
    total_records_evaluated = Column(BigInteger, default=0, nullable=False)
    failed_records_count = Column(BigInteger, default=0, nullable=False)
    pass_percentage = Column(Float, default=100.0, nullable=False)
    sample_failed_records = Column(JSON, default=list, nullable=False)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class DataProfileResult(Base):
    __tablename__ = "data_profile_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id = Column(String(36), nullable=True)
    dataset_name = Column(String(150), nullable=False)
    total_rows = Column(BigInteger, default=0, nullable=False)
    total_columns = Column(Integer, default=0, nullable=False)
    column_profiles = Column(JSON, default=list, nullable=False)
    profiled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id = Column(String(36), nullable=True)
    source_dataset = Column(String(150), nullable=False)
    target_dataset = Column(String(150), nullable=False)
    source_rows = Column(BigInteger, default=0, nullable=False)
    target_rows = Column(BigInteger, default=0, nullable=False)
    row_variance = Column(BigInteger, default=0, nullable=False)
    status = Column(String(30), nullable=False)  # MATCHED, DISCREPANCY_DETECTED
    details = Column(JSON, default=dict, nullable=False)
    reconciled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    workspace_id = Column(String(36), nullable=True)
    user_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
