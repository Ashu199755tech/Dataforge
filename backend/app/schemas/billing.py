from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class PricingConfigVersionBase(BaseModel):
    version_number: int = Field(default=1, description="Version number of pricing rules")
    monthly_base_price: float = Field(..., description="Base monthly subscription fee in selected currency")
    annual_base_price: float = Field(..., description="Discounted annual subscription fee")
    included_pipeline_runs: int = Field(..., description="Standard pipeline execution allowance per month")
    basic_run_rate: float = Field(default=0.50, description="Overage fee per Basic run (2-5 activities)")
    standard_run_rate: float = Field(default=1.50, description="Overage fee per Standard run (6-15 activities)")
    advanced_run_rate: float = Field(default=3.00, description="Overage fee per Advanced run (16-30 activities)")
    complex_run_rate: float = Field(default=5.00, description="Overage fee per Complex run (31+ activities)")
    spark_node_hour_rate: float = Field(default=45.00, description="Compute rate per worker node-hour for managed Spark")
    sql_pushdown_rate: float = Field(default=0.00, description="Egress fee for in-database SQL Pushdown (0 for BYOC)")
    currency: str = Field(default="INR", description="Currency code (INR, USD, EUR, GBP)")
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None


class PricingConfigVersionCreate(PricingConfigVersionBase):
    pass


class PricingConfigVersionResponse(PricingConfigVersionBase):
    id: str
    plan_id: str
    created_by_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanBase(BaseModel):
    plan_code: str = Field(..., description="Unique plan code (starter, professional, enterprise, custom)")
    name: str = Field(..., description="Display name of plan")
    description: Optional[str] = None
    tier_level: int = Field(default=1, description="Tier ranking (1: Starter, 2: Pro, 3: Enterprise)")
    is_active: bool = True
    is_custom: bool = False
    features: Dict[str, Any] = Field(default_factory=dict, description="Entitlements & capabilities")


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pricing: PricingConfigVersionCreate


class SubscriptionPlanResponse(SubscriptionPlanBase):
    id: str
    created_at: datetime
    updated_at: datetime
    active_pricing: Optional[PricingConfigVersionResponse] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerSubscriptionBase(BaseModel):
    plan_id: str
    billing_period: str = Field(default="Monthly", description="Billing frequency: 'Monthly' or 'Annual'")
    custom_agreement_notes: Optional[str] = None


class CustomerSubscriptionCreate(CustomerSubscriptionBase):
    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None


class CustomerSubscriptionUpdate(BaseModel):
    plan_id: Optional[str] = None
    billing_period: Optional[str] = None
    status: Optional[str] = None
    cancel_at_period_end: Optional[bool] = None
    custom_agreement_notes: Optional[str] = None


class CustomerSubscriptionResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: Optional[str] = None
    plan_id: str
    pricing_version_id: str
    billing_period: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    custom_agreement_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    plan: Optional[SubscriptionPlanResponse] = None
    pricing_version: Optional[PricingConfigVersionResponse] = None

    model_config = ConfigDict(from_attributes=True)


class TenantBase(BaseModel):
    name: str
    billing_email: str
    currency: str = "INR"
    country: str = "IN"
    tax_identifier: Optional[str] = None
    deployment_model: str = "BYOC"  # BYOC, SaaS, Hybrid


class TenantCreate(TenantBase):
    pass


class TenantResponse(TenantBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillingOverviewResponse(BaseModel):
    tenant: TenantResponse
    subscription: Optional[CustomerSubscriptionResponse] = None
    plan_name: str
    tier_level: int
    monthly_subscription_amount: float
    annual_subscription_amount: float
    currency: str
    billing_period: str
    subscription_status: str
    next_billing_date: Optional[datetime] = None
    included_runs: int
    consumed_runs: int
    remaining_runs: int
    overage_runs: int
    estimated_overage_charges: float
    estimated_spark_compute_charges: float
    estimated_total_software_charges: float
    previous_month_charges: float
    deployment_model: str


class PipelineUsageLedgerResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    project_id: str
    pipeline_id: str
    pipeline_name: str
    pipeline_run_id: str
    execution_type: str
    execution_engine: str
    activity_count: int
    classification: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: float
    execution_status: str
    retry_count: int
    runtime_id: Optional[str] = None
    rows_processed: int
    bytes_processed: int
    billing_period_key: str
    is_billable: bool
    non_billable_reason: Optional[str] = None
    calculated_charge: float
    pricing_version_id: Optional[str] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineUsageOverrideRequest(BaseModel):
    is_billable: bool
    reason: str


class UsageAggregationResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: Optional[str] = None
    subscription_id: Optional[str] = None
    period_key: str
    total_runs: int
    billable_runs: int
    non_billable_runs: int
    basic_runs: int
    standard_runs: int
    advanced_runs: int
    complex_runs: int
    copy_engine_runs: int
    spark_runs: int
    sql_pushdown_runs: int
    hybrid_runs: int
    spark_node_hours: float
    included_runs_consumed: int
    overage_runs: int
    total_overage_charge: float
    spark_compute_charge: float
    total_charge: float
    last_calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyConsumptionItem(BaseModel):
    date: str  # YYYY-MM-DD
    total_runs: int
    billable_runs: int
    non_billable_runs: int
    basic_runs: int
    standard_runs: int
    advanced_runs: int
    complex_runs: int
    spark_runs: int
    copy_runs: int
    sql_runs: int
    estimated_charges: float


class ConsumptionSummaryResponse(BaseModel):
    period_key: str
    plan_name: str
    tier_level: int
    included_runs: int
    consumed_runs: int
    remaining_runs: int
    overage_runs: int
    total_runs: int
    billable_runs: int
    non_billable_runs: int
    classification_breakdown: Dict[str, int]
    engine_breakdown: Dict[str, int]
    spark_node_hours: float
    estimated_overage_charge: float
    estimated_spark_compute_charge: float
    estimated_total_software_charge: float
    daily_consumption: List[DailyConsumptionItem]


class InvoiceLineItemResponse(BaseModel):
    id: str
    invoice_id: str
    item_type: str
    description: str
    quantity: float
    unit_price: float
    amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentRecordBase(BaseModel):
    payment_reference: str
    payment_method: str = "BankTransfer"  # BankTransfer, CorporatePO, Stripe, Razorpay
    amount: float
    currency: str = "INR"
    notes: Optional[str] = None


class PaymentRecordCreate(PaymentRecordBase):
    payment_status: str = "Completed"


class PaymentRecordResponse(PaymentRecordBase):
    id: str
    invoice_id: str
    tenant_id: str
    payment_status: str
    payment_date: datetime
    verified_by_user_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillingInvoiceBase(BaseModel):
    invoice_number: str
    period_key: str
    billing_period_start: datetime
    billing_period_end: datetime
    issue_date: datetime
    due_date: datetime
    currency: str = "INR"
    subscription_amount: float
    overage_amount: float
    compute_amount: float
    subtotal_amount: float
    tax_percent: float = 18.00
    tax_amount: float
    adjustments_amount: float = 0.00
    total_amount: float
    status: str
    pdf_storage_path: Optional[str] = None
    notes: Optional[str] = None


class BillingInvoiceResponse(BillingInvoiceBase):
    id: str
    tenant_id: str
    subscription_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BillingInvoiceDetailResponse(BillingInvoiceResponse):
    line_items: List[InvoiceLineItemResponse] = []
    payments: List[PaymentRecordResponse] = []


class InvoiceGenerateRequest(BaseModel):
    tenant_id: Optional[str] = None
    period_key: Optional[str] = None  # Defaults to current YYYY-MM
    notes: Optional[str] = None


