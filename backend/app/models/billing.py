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
    invoices = relationship("BillingInvoice", back_populates="tenant", cascade="all, delete-orphan")
    budgets = relationship("BudgetConfiguration", back_populates="tenant", cascade="all, delete-orphan")


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
    invoices = relationship("BillingInvoice", back_populates="subscription")


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


class UsageAggregation(Base):
    """
    Aggregated usage and rating rollups for billing periods (e.g. YYYY-MM).
    Supports high-performance reporting and fast rating recalculation.
    """
    __tablename__ = "usage_aggregations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    subscription_id = Column(String(36), ForeignKey("customer_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    period_key = Column(String(7), nullable=False, index=True)  # 'YYYY-MM'
    total_runs = Column(Integer, default=0, nullable=False)
    billable_runs = Column(Integer, default=0, nullable=False)
    non_billable_runs = Column(Integer, default=0, nullable=False)
    basic_runs = Column(Integer, default=0, nullable=False)
    standard_runs = Column(Integer, default=0, nullable=False)
    advanced_runs = Column(Integer, default=0, nullable=False)
    complex_runs = Column(Integer, default=0, nullable=False)
    copy_engine_runs = Column(Integer, default=0, nullable=False)
    spark_runs = Column(Integer, default=0, nullable=False)
    sql_pushdown_runs = Column(Integer, default=0, nullable=False)
    hybrid_runs = Column(Integer, default=0, nullable=False)
    spark_node_hours = Column(Numeric(10, 2), default=0.00, nullable=False)
    included_runs_consumed = Column(Integer, default=0, nullable=False)
    overage_runs = Column(Integer, default=0, nullable=False)
    total_overage_charge = Column(Numeric(12, 2), default=0.00, nullable=False)
    spark_compute_charge = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_charge = Column(Numeric(12, 2), default=0.00, nullable=False)
    last_calculated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant")
    subscription = relationship("CustomerSubscription")


class BillingInvoice(Base):
    """
    Monthly commercial billing statement generated for a customer tenant.
    Captures subscription base, usage overage, compute charges, taxes (18% GST), and adjustments.
    """
    __tablename__ = "billing_invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    subscription_id = Column(String(36), ForeignKey("customer_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g. DF-INV-2026-11-0001
    period_key = Column(String(7), nullable=False, index=True)  # 'YYYY-MM'
    billing_period_start = Column(DateTime, nullable=False)
    billing_period_end = Column(DateTime, nullable=False)
    issue_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    due_date = Column(DateTime, nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    subscription_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    overage_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    compute_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    subtotal_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    tax_percent = Column(Numeric(5, 2), default=18.00, nullable=False)  # 18.00% GST
    tax_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    adjustments_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    total_amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    status = Column(String(30), default="Issued", nullable=False)  # Draft, Issued, Paid, PastDue, Void
    pdf_storage_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant", back_populates="invoices")
    subscription = relationship("CustomerSubscription", back_populates="invoices")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLineItem.created_at")
    payments = relationship("PaymentRecord", back_populates="invoice", cascade="all, delete-orphan", order_by="PaymentRecord.payment_date")


class InvoiceLineItem(Base):
    """
    Granular itemized charge on a billing invoice.
    """
    __tablename__ = "invoice_line_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("billing_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(String(40), nullable=False)  # SubscriptionBase, OverageBasic, OverageStandard, OverageAdvanced, OverageComplex, SparkCompute, CreditAdjustment
    description = Column(String(255), nullable=False)
    quantity = Column(Numeric(10, 2), default=1.00, nullable=False)
    unit_price = Column(Numeric(10, 4), default=0.0000, nullable=False)
    amount = Column(Numeric(12, 2), default=0.00, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = relationship("BillingInvoice", back_populates="line_items")


class PaymentRecord(Base):
    """
    Verified payment transaction associated with an issued invoice.
    Supports B2B offline bank transfer / corporate purchase order verification and online gateways.
    """
    __tablename__ = "payment_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id = Column(String(36), ForeignKey("billing_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_reference = Column(String(100), unique=True, nullable=False, index=True)  # Bank UTR, Wire Reference, PO Number
    payment_method = Column(String(50), default="BankTransfer", nullable=False)  # BankTransfer, CorporatePO, Stripe, Razorpay
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="INR", nullable=False)
    payment_status = Column(String(30), default="Completed", nullable=False)  # Completed, Pending, Failed, Refunded
    payment_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    verified_by_user_id = Column(String(36), nullable=True)  # Admin user who verified the wire transfer
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    invoice = relationship("BillingInvoice", back_populates="payments")
    tenant = relationship("Tenant")


class BudgetConfiguration(Base):
    """
    Spending and Execution Run Budget Limits.
    Allows workspace- and project-level caps with automated threshold notifications (50%, 75%, 90%, 100%)
    and optional hard execution stoppage.
    """
    __tablename__ = "budget_configurations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    project_id = Column(String(36), nullable=True, index=True)
    name = Column(String(150), nullable=False)
    period_type = Column(String(20), default="Monthly", nullable=False)  # Monthly, Quarterly, Annual
    monthly_limit_amount = Column(Numeric(12, 2), default=0.00, nullable=False)  # Currency limit (0 = uncapped)
    monthly_run_limit = Column(Integer, default=0, nullable=False)               # Run count limit (0 = uncapped)
    enforce_hard_limit = Column(Boolean, default=False, nullable=False)          # If true, block new executions at 100%
    alert_recipients = Column(JSON, default=list, nullable=False)                # [{"channel": "email", "target": "..."}, {"channel": "slack", "target": "..."}]
    threshold_percents = Column(JSON, default=lambda: [50, 75, 90, 100], nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    tenant = relationship("Tenant", back_populates="budgets")
    alerts = relationship("BudgetAlertRecord", back_populates="budget", cascade="all, delete-orphan", order_by="BudgetAlertRecord.triggered_at.desc()")


class BudgetAlertRecord(Base):
    """
    Immutable audit record of dispatched budget threshold notifications.
    Guarantees that a threshold (e.g. 75%) is alerted at most once per billing period.
    """
    __tablename__ = "budget_alert_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    budget_id = Column(String(36), ForeignKey("budget_configurations.id", ondelete="CASCADE"), nullable=False, index=True)
    period_key = Column(String(7), nullable=False, index=True)  # 'YYYY-MM'
    threshold_percent = Column(Integer, nullable=False)         # 50, 75, 90, 100
    current_spend = Column(Numeric(12, 2), nullable=False)
    budget_limit = Column(Numeric(12, 2), nullable=False)
    current_runs = Column(Integer, nullable=False)
    run_limit = Column(Integer, nullable=False)
    notification_channel = Column(String(50), default="email", nullable=False)
    dispatched_to = Column(String(255), nullable=False)
    status = Column(String(30), default="Delivered", nullable=False)  # Delivered, Triggered, Failed
    triggered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    budget = relationship("BudgetConfiguration", back_populates="alerts")


