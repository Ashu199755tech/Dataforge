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


class CostEstimateRequest(BaseModel):
    expected_pipelines: int = Field(default=10, ge=1, le=500, description="Expected total active pipelines")
    monthly_pipeline_runs: int = Field(default=35000, ge=100, le=5000000, description="Monthly total execution runs")
    average_activities_per_pipeline: int = Field(default=8, ge=1, le=100, description="Average activities per pipeline")
    copy_engine_pct: float = Field(default=60.0, ge=0.0, le=100.0, description="Copy engine share (%)")
    spark_engine_pct: float = Field(default=20.0, ge=0.0, le=100.0, description="Managed Spark engine share (%)")
    sql_pushdown_pct: float = Field(default=20.0, ge=0.0, le=100.0, description="SQL pushdown engine share (%)")
    data_volume_gb: float = Field(default=500.0, ge=0.0, description="Estimated total monthly data volume in GB")
    runtime_hours_per_month: float = Field(default=100.0, ge=0.0, description="Total active execution compute hours")
    deployment_model: str = Field(default="BYOC", description="BYOC (Bring Your Own Cloud) or SaaS")
    billing_period: str = Field(default="Monthly", description="Monthly or Annual")


class PlanComparisonItemResponse(BaseModel):
    plan_code: str
    plan_name: str
    tier_level: int
    monthly_base_price: float
    included_runs: int
    overage_runs: int
    overage_cost: float
    spark_compute_cost: float
    software_subtotal: float
    estimated_gst_tax: float
    software_total: float
    is_recommended: bool
    features_summary: List[str]


class CostEstimateResponse(BaseModel):
    recommended_plan: str
    recommended_plan_name: str
    billing_period: str
    deployment_model: str
    expected_monthly_runs: int
    activity_classification: str
    rate_per_overage_run: float
    included_runs: int
    overage_runs: int
    base_subscription_cost: float
    overage_cost: float
    spark_compute_cost: float
    estimated_software_subtotal: float
    estimated_tax_gst: float
    estimated_software_total: float
    estimated_cloud_infrastructure_cost: float
    cloud_markup_percent: float
    estimated_adf_equivalent_cost: float
    estimated_savings_percent: float
    plan_comparison: List[PlanComparisonItemResponse]
    assumptions_and_limitations: List[str]


class BudgetConfigurationBase(BaseModel):
    name: str = Field(..., description="Budget name e.g. 'Production Workspace Monthly Limit'")
    period_type: str = Field(default="Monthly", description="Budget period: Monthly, Quarterly, Annual")
    monthly_limit_amount: float = Field(default=0.0, ge=0.0, description="Monthly spending limit in INR (0 = uncapped)")
    monthly_run_limit: int = Field(default=0, ge=0, description="Monthly run count limit (0 = uncapped)")
    enforce_hard_limit: bool = Field(default=False, description="If true, hard stop executions when 100% reached")
    alert_recipients: List[Dict[str, str]] = Field(default_factory=list, description="Alert channels: [{'channel': 'email', 'target': 'ops@co.com'}]")
    threshold_percents: List[int] = Field(default_factory=lambda: [50, 75, 90, 100], description="Alert percentage triggers")
    is_active: bool = True


class BudgetConfigurationCreate(BudgetConfigurationBase):
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None


class BudgetConfigurationUpdate(BaseModel):
    name: Optional[str] = None
    monthly_limit_amount: Optional[float] = None
    monthly_run_limit: Optional[int] = None
    enforce_hard_limit: Optional[bool] = None
    alert_recipients: Optional[List[Dict[str, str]]] = None
    threshold_percents: Optional[List[int]] = None
    is_active: Optional[bool] = None


class BudgetAlertRecordResponse(BaseModel):
    id: str
    budget_id: str
    period_key: str
    threshold_percent: int
    current_spend: float
    budget_limit: float
    current_runs: int
    run_limit: int
    notification_channel: str
    dispatched_to: str
    status: str
    triggered_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetStatusResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    name: str
    period_type: str
    monthly_limit_amount: float
    monthly_run_limit: int
    enforce_hard_limit: bool
    alert_recipients: List[Dict[str, str]]
    threshold_percents: List[int]
    is_active: bool
    current_spend: float
    current_runs: int
    spend_utilization_pct: float
    run_utilization_pct: float
    is_hard_limit_breached: bool
    recent_alerts: List[BudgetAlertRecordResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetEvaluationResult(BaseModel):
    period_key: str
    evaluated_budgets: int
    triggered_alerts_count: int
    alerts_dispatched: List[BudgetAlertRecordResponse] = []


