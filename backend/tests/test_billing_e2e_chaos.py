import pytest
import uuid
import threading
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.models.billing import (
    Tenant,
    SubscriptionPlan,
    PricingConfigVersion,
    CustomerSubscription,
    PipelineUsageLedger,
    UsageAggregation,
    BillingInvoice,
    BudgetConfiguration,
    BudgetAlertRecord,
    BillingAuditLog
)
from backend.app.services.billing_service import BillingService
from backend.app.services.metering_service import UsageMeteringEngine
from backend.app.services.rating_engine import RatingEngine
from backend.app.services.invoicing_service import InvoiceService
from backend.app.services.budget_service import BudgetService
from backend.app.services.admin_pricing_service import AdminPricingService
from backend.app.services.pdf_generator import PDFInvoiceGenerator
from backend.app.schemas.billing import BudgetConfigurationCreate
from backend.app.execution.runner import PipelineRunner
from backend.app.core.security import create_access_token


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def e2e_setup(db: Session):
    """Provisions a clean tenant, workspace, project, pipeline, and active subscription."""
    BillingService.seed_default_plans(db)

    # 1. Tenant A
    tenant_a = Tenant(
        name=f"E2E Enterprise Corp {uuid.uuid4().hex[:6]}",
        billing_email="cfo@e2ecorp.com",
        currency="INR",
        country="IN",
        tax_identifier="27AAACE1234F1Z5",
        deployment_model="BYOC"
    )
    db.add(tenant_a)
    db.flush()

    workspace_a = Workspace(
        name=f"E2E Prod WS {uuid.uuid4().hex[:6]}",
        tenant_id=tenant_a.id
    )
    db.add(workspace_a)
    db.flush()

    project_a = Project(
        name=f"E2E Data Platform {uuid.uuid4().hex[:6]}",
        workspace_id=workspace_a.id
    )
    db.add(project_a)
    db.flush()

    pipeline_a = Pipeline(
        name="Production Ingestion DAG",
        project_id=project_a.id,
        definition_json={
            "activities": [
                {"id": "step_1", "name": "Step1", "type": "Wait", "config": {"wait_time_in_seconds": 0}},
                {"id": "step_2", "name": "Step2", "type": "Wait", "config": {"wait_time_in_seconds": 0}},
                {"id": "step_3", "name": "Step3", "type": "Wait", "config": {"wait_time_in_seconds": 0}}
            ]
        }
    )
    db.add(pipeline_a)
    db.flush()

    # Starter subscription with quota
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == "starter").first()
    pricing_v = plan.pricing_versions[0]
    now = datetime.now(timezone.utc)
    sub_a = CustomerSubscription(
        tenant_id=tenant_a.id,
        workspace_id=workspace_a.id,
        plan_id=plan.id,
        pricing_version_id=pricing_v.id,
        billing_period="Monthly",
        status="Active",
        current_period_start=now - timedelta(days=15),
        current_period_end=now + timedelta(days=15)
    )
    db.add(sub_a)
    db.flush()

    # 2. Tenant B (for multi-tenant isolation testing)
    tenant_b = Tenant(
        name=f"Isolated Tenant B {uuid.uuid4().hex[:6]}",
        billing_email="admin@tenantb.com",
        currency="INR",
        country="IN"
    )
    db.add(tenant_b)
    db.flush()

    workspace_b = Workspace(
        name=f"Tenant B WS {uuid.uuid4().hex[:6]}",
        tenant_id=tenant_b.id
    )
    db.add(workspace_b)
    db.commit()

    return {
        "tenant_a": tenant_a,
        "workspace_a": workspace_a,
        "project_a": project_a,
        "pipeline_a": pipeline_a,
        "subscription_a": sub_a,
        "tenant_b": tenant_b,
        "workspace_b": workspace_b
    }


def test_full_e2e_billing_monetization_lifecycle(db: Session, e2e_setup: dict):
    """
    Validates complete end-to-end monetization lifecycle:
    1. Pipeline Execution via PipelineRunner -> status Succeeded
    2. Automated Usage Metering Ledger creation with exact engine and classification
    3. Rating Engine monthly rollup aggregation
    4. Budget threshold alert evaluation and dispatch
    5. Monthly Invoicing with 18% GST calculation
    6. Offline bank wire remittance and invoice transition to Paid
    7. PDF Invoice statement compilation
    """
    tenant = e2e_setup["tenant_a"]
    workspace = e2e_setup["workspace_a"]
    pipeline = e2e_setup["pipeline_a"]

    # --- STEP 1: Execute Pipeline ---
    run = PipelineRun(
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Pending"
    )
    db.add(run)
    db.commit()

    # Execute synchronously
    runner = PipelineRunner(run.id)
    runner.execute_sync()
    db.refresh(run)
    assert run.status == "Succeeded"
    assert run.total_activities == 3

    # --- STEP 2: Metering Ledger Verification ---
    ledger = db.query(PipelineUsageLedger).filter(
        PipelineUsageLedger.pipeline_run_id == run.id
    ).first()
    assert ledger is not None
    assert ledger.tenant_id == tenant.id
    assert ledger.workspace_id == workspace.id
    assert ledger.pipeline_id == pipeline.id
    assert ledger.classification == "Basic"  # 3 activities
    assert ledger.is_billable is True
    assert ledger.execution_status == "Succeeded"

    # --- STEP 3: Rating Engine Rollup ---
    period_key = datetime.now(timezone.utc).strftime("%Y-%m")
    rollup = RatingEngine.aggregate_usage_for_period(db, tenant.id, period_key)
    assert rollup.total_runs >= 1
    assert rollup.billable_runs >= 1
    assert rollup.basic_runs >= 1

    # --- STEP 4: Budget Threshold Evaluation ---
    budget = BudgetService.create_budget(
        db,
        tenant.id,
        BudgetConfigurationCreate(
            name="E2E Lifecycle Guardrail",
            monthly_limit_amount=500.0,
            monthly_run_limit=100,
            threshold_percents=[50, 75, 90, 100],
            workspace_id=workspace.id
        )
    )
    status = BudgetService.get_budget_status(db, budget.id, period_key)
    assert status.current_runs >= 1
    assert status.is_hard_limit_breached is False

    # --- STEP 5: Generate Invoice ---
    invoice = InvoiceService.generate_monthly_invoice(db, tenant.id, period_key)
    assert invoice.tenant_id == tenant.id
    assert invoice.status == "Issued"
    assert float(invoice.subscription_amount) == 9999.00  # Starter base
    assert float(invoice.tax_percent) == 18.00
    assert float(invoice.tax_amount) == round(float(invoice.subtotal_amount) * 0.18, 2)
    assert float(invoice.total_amount) == float(invoice.subtotal_amount) + float(invoice.tax_amount)

    # Line items verified
    line_items = invoice.line_items
    assert len(line_items) >= 1
    assert any(li.item_type == "SubscriptionBase" for li in line_items)

    # --- STEP 6: Offline Bank Wire Remittance ---
    payment = InvoiceService.record_payment(
        db=db,
        invoice_id=invoice.id,
        payment_data={
            "amount": float(invoice.total_amount),
            "payment_reference": f"E2E-UTR-{uuid.uuid4().hex[:8]}",
            "payment_method": "BankTransfer",
            "notes": "Automated E2E Verification Wire Settlement"
        },
        admin_user_id="admin_e2e_auditor"
    )
    db.refresh(invoice)
    assert invoice.status == "Paid"
    assert payment.payment_status == "Completed"
    assert float(payment.amount) == float(invoice.total_amount)

    # --- STEP 7: PDF Statement Verification ---
    pdf_bytes = InvoiceService.generate_invoice_pdf(db, invoice.id)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
    assert len(pdf_bytes) > 1000


def test_chaos_concurrent_duplicate_metering_prevention(db: Session, e2e_setup: dict):
    """
    Chaos Test: Concurrency Race Condition.
    Simulates 10 concurrent threads attempting to meter the exact same pipeline run simultaneously.
    Verifies that unique database constraints serialize the operations and produce exactly 1 ledger record.
    """
    tenant = e2e_setup["tenant_a"]
    workspace = e2e_setup["workspace_a"]
    pipeline = e2e_setup["pipeline_a"]

    pr = PipelineRun(
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Succeeded"
    )
    db.add(pr)
    db.commit()

    created_records = []
    errors = []

    def run_concurrent_meter():
        local_session = SessionLocal()
        try:
            res = UsageMeteringEngine.record_pipeline_execution(
                db=local_session,
                pipeline_run_id=pr.id
            )
            created_records.append(res.id)
        except Exception as e:
            errors.append(e)
        finally:
            local_session.close()

    threads = [threading.Thread(target=run_concurrent_meter) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Query database: exact 1 record exists
    ledger_count = db.query(PipelineUsageLedger).filter(
        PipelineUsageLedger.pipeline_run_id == pr.id
    ).count()
    assert ledger_count == 1
    # All threads safely resolved to the same ledger record ID
    assert len(set(created_records)) == 1


def test_chaos_worker_crash_and_retry_zero_duplicate_charge(db: Session, e2e_setup: dict):
    """
    Chaos Test: Worker Crash & Retry Resumption.
    Simulates a worker crash (SIGKILL / unhandled exception) during execution, followed by a task retry.
    Verifies that retrying within the same pipeline run creates zero duplicate orchestration run charges.
    """
    workspace = e2e_setup["workspace_a"]
    pipeline = e2e_setup["pipeline_a"]

    # Initial Run
    pr = PipelineRun(
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Running"
    )
    db.add(pr)
    db.commit()

    # Attempt 1: Failed with SystemError (Worker crash)
    act1 = ActivityRun(
        pipeline_run_id=pr.id,
        activity_id="act_copy_1",
        activity_name="Copy Data",
        activity_type="CopyData",
        status="Failed",
        retry_attempt=1
    )
    db.add(act1)
    pr.status = "Failed"
    pr.error_summary = "Fatal engine error: WorkerCrash termination"
    db.commit()

    meter_res1 = UsageMeteringEngine.record_pipeline_execution(
        db=db,
        pipeline_run_id=pr.id
    )
    assert meter_res1.is_billable is False  # Platform infrastructure crash is non-billable
    assert meter_res1.calculated_charge == Decimal("0.00")

    # Attempt 2: Worker resumes on retry for the same run
    meter_res2 = UsageMeteringEngine.record_pipeline_execution(
        db=db,
        pipeline_run_id=pr.id
    )
    # Natural idempotency returns the existing ledger record with zero new charges
    assert meter_res2.id == meter_res1.id

    ledger_count = db.query(PipelineUsageLedger).filter(
        PipelineUsageLedger.pipeline_run_id == pr.id
    ).count()
    assert ledger_count == 1


def test_strict_multi_tenant_isolation(db: Session, client: TestClient, e2e_setup: dict):
    """
    Security Test: Cross-Tenant Data Isolation.
    Verifies that Tenant A cannot retrieve, view, or aggregate Tenant B's usage ledger,
    subscriptions, invoices, or budgets.
    """
    tenant_a = e2e_setup["tenant_a"]
    workspace_a = e2e_setup["workspace_a"]
    tenant_b = e2e_setup["tenant_b"]
    workspace_b = e2e_setup["workspace_b"]

    # Create users for Tenant A and Tenant B
    user_a = User(
        email=f"user_a_{uuid.uuid4().hex[:6]}@tenanta.com",
        full_name="Tenant A Admin",
        hashed_password="hash",
        role="Admin"
    )
    user_b = User(
        email=f"user_b_{uuid.uuid4().hex[:6]}@tenantb.com",
        full_name="Tenant B Admin",
        hashed_password="hash",
        role="Admin"
    )
    db.add_all([user_a, user_b])
    db.commit()

    token_a = create_access_token({"sub": user_a.id, "role": user_a.role})
    token_b = create_access_token({"sub": user_b.id, "role": user_b.role})

    # Create Invoice and Budget for Tenant B
    period_key = "2026-03"
    inv_b = InvoiceService.generate_monthly_invoice(db, tenant_b.id, period_key)
    budget_b = BudgetService.create_budget(
        db,
        tenant_b.id,
        BudgetConfigurationCreate(
            name="Tenant B Private Budget",
            monthly_limit_amount=50000.0,
            workspace_id=workspace_b.id
        )
    )

    # 1. Tenant A calls invoices endpoint for workspace A -> should not see Tenant B's invoice
    headers_a = {"Authorization": f"Bearer {token_a}"}
    resp_inv_a = client.get(f"/api/v1/billing/invoices?workspace_id={workspace_a.id}", headers=headers_a)
    assert resp_inv_a.status_code == 200
    invoices_seen = resp_inv_a.json()
    assert not any(i["id"] == inv_b.id for i in invoices_seen)

    # 2. Tenant A attempts to fetch Tenant B's invoice directly by ID
    resp_direct_b = client.get(f"/api/v1/billing/invoices/{inv_b.id}?workspace_id={workspace_a.id}", headers=headers_a)
    # Must be 404 Not Found or masked
    assert resp_direct_b.status_code == 404

    # 3. Tenant A lists budgets -> should not see Tenant B's budget
    resp_budgets_a = client.get(f"/api/v1/billing/budgets?workspace_id={workspace_a.id}", headers=headers_a)
    assert resp_budgets_a.status_code == 200
    budgets_seen = resp_budgets_a.json()
    assert not any(b["id"] == budget_b.id for b in budgets_seen)


def test_malformed_corrupted_payload_recovery(db: Session, e2e_setup: dict):
    """
    Chaos Test: Malformed & Empty Payloads.
    Verifies that malformed activity definitions, empty pipelines, or missing runtime metrics
    fail gracefully without crashing the rating or metering engines.
    """
    workspace = e2e_setup["workspace_a"]
    project = e2e_setup["project_a"]

    # Pipeline with empty definition
    empty_pipeline = Pipeline(
        name="Empty Pipeline",
        project_id=project.id,
        definition_json={}
    )
    db.add(empty_pipeline)
    db.commit()

    pr = PipelineRun(
        pipeline_id=empty_pipeline.id,
        run_type="Manual",
        status="Succeeded"
    )
    db.add(pr)
    db.commit()

    # Metering should handle 0 activities gracefully
    meter_res = UsageMeteringEngine.record_pipeline_execution(
        db=db,
        pipeline_run_id=pr.id
    )
    assert meter_res.classification == "Basic"
    assert meter_res.activity_count == 1
    assert meter_res.is_billable is True

    # Rating engine aggregates without arithmetic error
    period_key = datetime.now(timezone.utc).strftime("%Y-%m")
    summary = RatingEngine.get_consumption_summary(db, workspace_id=workspace.id, period_key=period_key)
    assert summary is not None
    assert summary["total_runs"] >= 1
