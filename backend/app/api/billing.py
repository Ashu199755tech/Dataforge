from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.core.database import get_db
from backend.app.services.billing_service import BillingService
from backend.app.services.metering_service import UsageMeteringEngine
from backend.app.services.rating_engine import RatingEngine
from backend.app.services.invoicing_service import InvoiceService
from backend.app.services.cost_estimator_service import CostEstimatorService
from backend.app.schemas.billing import (
    SubscriptionPlanResponse,
    SubscriptionPlanCreate,
    CustomerSubscriptionResponse,
    CustomerSubscriptionCreate,
    CustomerSubscriptionUpdate,
    BillingOverviewResponse,
    PipelineUsageLedgerResponse,
    PipelineUsageOverrideRequest,
    ConsumptionSummaryResponse,
    DailyConsumptionItem,
    UsageAggregationResponse,
    BillingInvoiceResponse,
    BillingInvoiceDetailResponse,
    InvoiceGenerateRequest,
    PaymentRecordCreate,
    PaymentRecordResponse,
    CostEstimateRequest,
    CostEstimateResponse
)
from backend.app.api.deps import get_current_user
from backend.app.core.rbac import require_role
from backend.app.models.user import User

router = APIRouter(prefix="/billing", tags=["Pricing & Billing"])


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
def list_subscription_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns all available commercial subscription tiers (Starter, Professional, Enterprise)."""
    return BillingService.get_available_plans(db)


@router.get("/plans/{plan_id}", response_model=SubscriptionPlanResponse)
def get_subscription_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full details and versioned pricing for a single plan."""
    plan = BillingService.get_plan_by_id(db, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")
    
    latest_v = plan.pricing_versions[0] if plan.pricing_versions else None
    return {
        "id": plan.id,
        "plan_code": plan.plan_code,
        "name": plan.name,
        "description": plan.description,
        "tier_level": plan.tier_level,
        "is_active": plan.is_active,
        "is_custom": plan.is_custom,
        "features": plan.features,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "active_pricing": latest_v
    }


@router.get("/subscription", response_model=Optional[CustomerSubscriptionResponse])
def get_current_subscription(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves current active subscription contract for the tenant or workspace."""
    sub = BillingService.get_subscription_for_workspace(db, workspace_id)
    return sub


@router.post("/subscription", response_model=CustomerSubscriptionResponse)
def update_or_create_subscription(
    sub_in: CustomerSubscriptionCreate,
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Owner"]))
):
    """Upgrades, downgrades, or switches subscription terms."""
    try:
        return BillingService.update_subscription(
            db=db,
            plan_id=sub_in.plan_id,
            billing_period=sub_in.billing_period,
            workspace_id=workspace_id or sub_in.workspace_id,
            notes=sub_in.custom_agreement_notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/overview", response_model=BillingOverviewResponse)
def get_billing_overview(
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compiles complete billing overview with real execution counts and current balance."""
    return BillingService.get_billing_overview(db, workspace_id)


@router.get("/usage", response_model=List[PipelineUsageLedgerResponse])
def list_pipeline_usage(
    workspace_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
    execution_engine: Optional[str] = None,
    classification: Optional[str] = None,
    is_billable: Optional[bool] = None,
    period_key: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns metered usage records with classification, engine, and calculated charges."""
    records, _ = UsageMeteringEngine.query_ledger(
        db=db,
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        execution_engine=execution_engine,
        classification=classification,
        is_billable=is_billable,
        period_key=period_key,
        limit=limit,
        offset=offset
    )
    return records


@router.get("/usage/summary", response_model=ConsumptionSummaryResponse)
def get_consumption_summary(
    workspace_id: Optional[str] = None,
    period_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full consumption summary with ADF-parity classification breakdowns and engine splits."""
    return RatingEngine.get_consumption_summary(
        db=db,
        workspace_id=workspace_id,
        period_key=period_key
    )


@router.get("/usage/daily", response_model=List[DailyConsumptionItem])
def get_daily_consumption(
    workspace_id: Optional[str] = None,
    period_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves daily breakdown of executions and charges for trend charts."""
    tenant = BillingService.get_or_create_default_tenant(db, workspace_id)
    now = datetime.now(timezone.utc)
    effective_period = period_key or now.strftime("%Y-%m")
    return RatingEngine.get_daily_consumption(
        db=db,
        tenant_id=tenant.id,
        period_key=effective_period
    )


@router.post("/usage/recalculate", response_model=UsageAggregationResponse)
def recalculate_usage_rating(
    workspace_id: Optional[str] = None,
    period_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Owner"]))
):
    """Triggers on-demand re-rating of all usage records against current active subscription rules."""
    tenant = BillingService.get_or_create_default_tenant(db, workspace_id)
    now = datetime.now(timezone.utc)
    effective_period = period_key or now.strftime("%Y-%m")
    return RatingEngine.aggregate_usage_for_period(
        db=db,
        tenant_id=tenant.id,
        period_key=effective_period,
        workspace_id=workspace_id
    )


@router.get("/usage/{run_id}", response_model=PipelineUsageLedgerResponse)
def get_pipeline_usage_for_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves usage ledger entry for a specific pipeline execution run."""
    from backend.app.models.billing import PipelineUsageLedger
    ledger = db.query(PipelineUsageLedger).filter(
        PipelineUsageLedger.pipeline_run_id == run_id
    ).first()
    if not ledger:
        # Check if run exists and meter it on-demand if missing
        ledger = UsageMeteringEngine.record_pipeline_execution(db, run_id)
        if not ledger:
            raise HTTPException(status_code=404, detail="Usage record for run not found.")
    return ledger


@router.post("/usage/{ledger_id}/override", response_model=PipelineUsageLedgerResponse)
def override_run_billability(
    ledger_id: str,
    req: PipelineUsageOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Owner"]))
):
    """Administratively updates run billability status with audit logging."""
    try:
        return UsageMeteringEngine.override_ledger_billability(
            db=db,
            ledger_id=ledger_id,
            is_billable=req.is_billable,
            reason=req.reason,
            admin_user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------
# Phase 5: Invoicing & Payment Endpoints
# ---------------------------------------------------------

@router.get("/invoices", response_model=List[BillingInvoiceResponse])
def list_invoices(
    status: Optional[str] = None,
    period_key: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists monthly commercial invoices for the customer tenant."""
    tenant = BillingService.get_or_create_default_tenant(db, workspace_id)
    invoices, _ = InvoiceService.list_invoices(
        db=db,
        tenant_id=tenant.id,
        status=status,
        period_key=period_key,
        limit=limit,
        offset=offset
    )
    return invoices


@router.post("/invoices/generate", response_model=BillingInvoiceDetailResponse)
def generate_monthly_invoice(
    req: InvoiceGenerateRequest,
    workspace_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Owner"]))
):
    """Generates or recalculates a commercial invoice statement for the specified period."""
    tenant = None
    if req.tenant_id:
        from backend.app.models.billing import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == req.tenant_id).first()
    if not tenant:
        tenant = BillingService.get_or_create_default_tenant(db, workspace_id)

    try:
        invoice = InvoiceService.generate_monthly_invoice(
            db=db,
            tenant_id=tenant.id,
            period_key=req.period_key,
            notes=req.notes
        )
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices/{invoice_id}", response_model=BillingInvoiceDetailResponse)
def get_invoice_details(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full details of an invoice including line items and payment records."""
    invoice = InvoiceService.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


@router.get("/invoices/{invoice_id}/download")
def download_invoice_pdf(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates and downloads a standardized ISO 32000-1 PDF statement."""
    invoice = InvoiceService.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    pdf_bytes = InvoiceService.generate_invoice_pdf(db, invoice_id)
    filename = f"{invoice.invoice_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes))
        }
    )


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentRecordResponse)
def record_invoice_payment(
    invoice_id: str,
    payment_in: PaymentRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Owner"]))
):
    """Records a verified payment against an invoice with tamper-evident audit logging."""
    invoice = InvoiceService.get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    try:
        payment = InvoiceService.record_payment(
            db=db,
            invoice_id=invoice_id,
            payment_data=payment_in.model_dump(),
            admin_user_id=current_user.id
        )
        return payment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------
# Phase 6: Interactive Cost Estimator & Sizing API
# ---------------------------------------------------------

@router.post("/estimate", response_model=CostEstimateResponse)
def estimate_dataforge_cost(
    req: CostEstimateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Calculates detailed workload sizing, plan recommendations,
    overage estimates, and side-by-side plan comparisons (Starter vs Professional vs Enterprise).
    """
    return CostEstimatorService.estimate(
        expected_pipelines=req.expected_pipelines,
        monthly_pipeline_runs=req.monthly_pipeline_runs,
        average_activities_per_pipeline=req.average_activities_per_pipeline,
        copy_engine_pct=req.copy_engine_pct,
        spark_engine_pct=req.spark_engine_pct,
        sql_pushdown_pct=req.sql_pushdown_pct,
        data_volume_gb=req.data_volume_gb,
        runtime_hours_per_month=req.runtime_hours_per_month,
        deployment_model=req.deployment_model,
        billing_period=req.billing_period
    )

