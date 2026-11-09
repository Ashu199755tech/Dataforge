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
