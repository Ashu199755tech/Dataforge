import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    DateTime,
    Text,
    JSON,
    Integer,
    Numeric,
    Boolean,
    BigInteger
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Tenant(Base):
    """
    Multi-tenant organization boundary.
    Owns one or more Workspaces and holds commercial billing subscriptions.
    """
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(150), unique=True, index=True, nullable=False)
    billing_email = Column(String(255), nullable=False)
    currency = Column(String(3), default="INR", nullable=False)  # INR, USD, EUR, GBP
    country = Column(String(2), default="IN", nullable=False)   # ISO 2-letter country code
    tax_identifier = Column(String(50), nullable=True)          # GSTIN / VAT Number
    deployment_model = Column(String(20), default="BYOC", nullable=False)  # BYOC, SaaS, Hybrid
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    subscriptions = relationship("CustomerSubscription", back_populates="tenant", cascade="all, delete-orphan")


class SubscriptionPlan(Base):
    """
    Commercial subscription plan tier definition (Starter, Professional, Enterprise, Custom).
    """
    __tablename__ = "subscription_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_code = Column(String(50), unique=True, index=True, nullable=False)  # starter, professional, enterprise, custom
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    tier_level = Column(Integer, default=1, nullable=False)  # 1: Starter, 2: Professional, 3: Enterprise
    is_active = Column(Boolean, default=True, nullable=False)
    is_custom = Column(Boolean, default=False, nullable=False)
    features = Column(JSON, default=dict, nullable=False)    # Feature entitlements list
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    pricing_versions = relationship("PricingConfigVersion", back_populates="plan", cascade="all, delete-orphan")
    subscriptions = relationship("CustomerSubscription", back_populates="plan")


class PricingConfigVersion(Base):
    """
    Immutable versioned pricing rates for a subscription plan.
    Guarantees that updating prices for future billing periods does not retroactively alter past invoices.
    """
    __tablename__ = "pricing_config_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(36), ForeignKey("subscription_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, default=1, nullable=False)
    monthly_base_price = Column(Numeric(12, 2), nullable=False)   # e.g. 9999.00
    annual_base_price = Column(Numeric(12, 2), nullable=False)    # e.g. 99990.00
    included_pipeline_runs = Column(Integer, nullable=False)      # e.g. 10000, 50000, 250000
    basic_run_rate = Column(Numeric(8, 4), default=0.5000, nullable=False)     # ₹0.50 (2-5 activities)
    standard_run_rate = Column(Numeric(8, 4), default=1.5000, nullable=False)  # ₹1.50 (6-15 activities)
    advanced_run_rate = Column(Numeric(8, 4), default=3.0000, nullable=False)  # ₹3.00 (16-30 activities)
    complex_run_rate = Column(Numeric(8, 4), default=5.0000, nullable=False)   # ₹5.00 (31+ activities)
    spark_node_hour_rate = Column(Numeric(10, 4), default=45.0000, nullable=False)  # SaaS Spark worker hour rate
    sql_pushdown_rate = Column(Numeric(8, 4), default=0.0000, nullable=False)       # Pushdown egress markup (0 for BYOC)
    currency = Column(String(3), default="INR", nullable=False)
    effective_from = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    effective_to = Column(DateTime, nullable=True)
    created_by_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    plan = relationship("SubscriptionPlan", back_populates="pricing_versions")
    subscriptions = relationship("CustomerSubscription", back_populates="pricing_version")


class CustomerSubscription(Base):
    """
    Active or historical commercial contract binding a Tenant/Workspace to a Subscription Plan.
    """
    __tablename__ = "customer_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)  # Associated primary workspace
    plan_id = Column(String(36), ForeignKey("subscription_plans.id"), nullable=False)
    pricing_version_id = Column(String(36), ForeignKey("pricing_config_versions.id"), nullable=False)
    billing_period = Column(String(20), default="Monthly", nullable=False)  # Monthly, Annual
    status = Column(String(20), default="Active", nullable=False)          # Active, PastDue, Suspended, Cancelled, Trial
    current_period_start = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    custom_agreement_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    pricing_version = relationship("PricingConfigVersion", back_populates="subscriptions")


class PipelineUsageLedger(Base):
    """
    Immutable Usage Metering Ledger.
    Captures metered consumption for every pipeline execution.
    Natural uniqueness constraint on pipeline_run_id guarantees idempotency across worker retries.
    """
    __tablename__ = "pipeline_usage_ledger"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    project_id = Column(String(36), nullable=False)
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_name = Column(String(150), nullable=False)
    pipeline_run_id = Column(String(36), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    execution_type = Column(String(30), default="Manual", nullable=False)  # Manual, Scheduled, Triggered, ChildPipeline
    execution_engine = Column(String(30), default="CopyEngine", nullable=False)  # CopyEngine, SparkEngine, SqlPushdownEngine, Hybrid
    activity_count = Column(Integer, default=1, nullable=False)
    classification = Column(String(20), default="Basic", nullable=False)  # Basic, Standard, Advanced, Complex
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Numeric(10, 2), default=0.0, nullable=False)
    execution_status = Column(String(30), nullable=False)  # Succeeded, Failed, Cancelled
    retry_count = Column(Integer, default=0, nullable=False)
    runtime_id = Column(String(36), nullable=True)
    rows_processed = Column(BigInteger, default=0, nullable=False)
    bytes_processed = Column(BigInteger, default=0, nullable=False)
    billing_period_key = Column(String(7), nullable=False, index=True)  # 'YYYY-MM'
    is_billable = Column(Boolean, default=True, nullable=False)
    non_billable_reason = Column(String(100), nullable=True)  # PlatformSystemError, CancelledBeforeStart, InternalRetry, ValidationCheck
    calculated_charge = Column(Numeric(10, 4), default=0.0000, nullable=False)
    pricing_version_id = Column(String(36), ForeignKey("pricing_config_versions.id"), nullable=True)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
    pipeline = relationship("Pipeline")
    pipeline_run = relationship("PipelineRun")
    pricing_version = relationship("PricingConfigVersion")

