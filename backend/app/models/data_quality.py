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


class DQRuleCatalogue(Base):
    """
    Metadata-driven Data Quality Rule Catalogue (DQ_RULE_CATALOGUE / DIM_DQ_RULE).
    Standard ADF/Enterprise schema:
      RULE_ID, RULE_TYPE, TARGET_COLUMN, RULE_EXPRESSION_LOGIC, TECHNICAL_DESCRIPTION, SEVERITY
    """
    __tablename__ = "dq_rule_catalogue"

    rule_id = Column(String(50), primary_key=True)
    rule_type = Column(String(50), nullable=False)  # ATR1-ATR8, DS1, CSQL
    target_column = Column(String(100), nullable=True)
    rule_expression_logic = Column(Text, nullable=True)
    technical_description = Column(Text, nullable=True)
    severity = Column(String(20), default="Error", nullable=False)  # Error, Warning
    dataset_id = Column(String(100), nullable=True)
    key_columns = Column(String(255), nullable=True)
    placeholder_values = Column(JSON, default=list, nullable=True)
    parameters = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


# Alias for DIM_DQ_RULE nomenclature
DimDQRule = DQRuleCatalogue


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


class DQCleansingLog(Base):
    """
    Cell-level audit log recording automated remediation diffs.
    Captures CLEANSING_ID (UUID per changed row), TABLE_NAME, COLUMN_NAME,
    RULE_ID, STRATEGY, BEFORE_VALUE, AFTER_VALUE, and PK.
    """
    __tablename__ = "dq_cleansing_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cleansing_id = Column(String(36), nullable=False, index=True)
    table_name = Column(String(150), nullable=False)
    column_name = Column(String(150), nullable=False)
    rule_id = Column(String(50), nullable=False)
    strategy = Column(String(50), nullable=False)
    primary_key_values = Column(JSON, default=dict, nullable=True)
    before_value = Column(Text, nullable=True)
    after_value = Column(Text, nullable=True)
    batch_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class FactDQExecutionLog(Base):
    """
    Audit execution log for DQAssessActivity and DQEnforceActivity runs.
    Records overall DQI, counts for clean/soft_reject/hard_reject/cleansed,
    and rule-level metrics.
    """
    __tablename__ = "fact_dq_execution_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id = Column(String(36), nullable=True, index=True)
    activity_run_id = Column(String(36), nullable=True, index=True)
    activity_type = Column(String(50), nullable=False)  # DQAssessActivity, DQEnforceActivity
    dataset_name = Column(String(150), nullable=False)
    total_records = Column(BigInteger, default=0, nullable=False)
    clean_records = Column(BigInteger, default=0, nullable=False)
    soft_reject_records = Column(BigInteger, default=0, nullable=False)
    hard_reject_records = Column(BigInteger, default=0, nullable=False)
    cleansed_records = Column(BigInteger, default=0, nullable=False)
    overall_dqi = Column(Float, default=1.0, nullable=False)
    gate_passed = Column(Boolean, default=True, nullable=False)
    rule_metrics = Column(JSON, default=dict, nullable=False)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

