import pytest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.models.billing import (
    Tenant,
    SubscriptionPlan,
    PricingConfigVersion,
    CustomerSubscription,
    PipelineUsageLedger,
    UsageAggregation,
    BillingInvoice,
    InvoiceLineItem,
    PaymentRecord
)
from backend.app.models.data_quality import AuditLog
from backend.app.services.billing_service import BillingService
from backend.app.services.invoicing_service import InvoiceService, OfflineBankTransferAdapter
from backend.app.services.pdf_generator import PDFInvoiceGenerator
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
def admin_token(db: Session):
    admin = db.query(User).filter(User.role == "Admin").first()
    if not admin:
        admin = User(
            email="invoice_admin@dataforge.test",
            full_name="Invoice Admin",
            hashed_password="hashed_admin_pass",
            role="Admin"
        )
        db.add(admin)
        db.commit()
    return create_access_token({"sub": admin.id, "role": admin.role})


@pytest.fixture
def invoice_setup(db: Session):
    """Provisions test tenant, workspace, project, and custom subscription for invoice testing."""
    BillingService.seed_default_plans(db)

    tenant_name = f"Invoice Tenant {uuid.uuid4().hex[:6]}"
    tenant = Tenant(
        name=tenant_name,
        billing_email="billing@invoicetest.com",
        currency="INR",
        country="IN",
        tax_identifier="29AABCI1234F1Z1",
        deployment_model="BYOC"
    )
    db.add(tenant)
    db.flush()

    workspace = Workspace(
        name=f"Invoice WS {uuid.uuid4().hex[:6]}",
        description="Invoicing Test Workspace",
        tenant_id=tenant.id
    )
    db.add(workspace)
    db.flush()

    project = Project(
        name=f"Invoice Project {uuid.uuid4().hex[:6]}",
        workspace_id=workspace.id
    )
    db.add(project)
    db.flush()

    pipeline = Pipeline(
        name="Invoice Pipeline",
        project_id=project.id,
        definition_json={"activities": [{"name": "act1"}]}
    )
    db.add(pipeline)
    db.flush()

    # Plan with custom small quota to easily trigger overages
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == "starter").first()
    pricing_v = plan.pricing_versions[0]

    now = datetime.now(timezone.utc)
    sub = CustomerSubscription(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        plan_id=plan.id,
        pricing_version_id=pricing_v.id,
        billing_period="Monthly",
        status="Active",
        current_period_start=now - timedelta(days=10),
        current_period_end=now + timedelta(days=20)
    )
    db.add(sub)
    db.commit()

    return {
        "tenant": tenant,
        "workspace": workspace,
        "project": project,
        "pipeline": pipeline,
        "subscription": sub,
        "pricing_version": pricing_v
    }


def test_generate_monthly_invoice_tax_and_line_items(db: Session, invoice_setup: dict):
    """
    Verifies that monthly invoice generation correctly calculates:
    1. Base subscription fee
    2. Overages and compute fees
    3. 18.00% GST tax calculation
    4. Granular itemized line items
    """
    tenant = invoice_setup["tenant"]
    workspace = invoice_setup["workspace"]
    project = invoice_setup["project"]
    pipeline = invoice_setup["pipeline"]
    sub = invoice_setup["subscription"]
    pricing_v = invoice_setup["pricing_version"]

    period_key = "2026-08"

    # Seed 3 pipeline usage entries
    for i in range(3):
        pr = PipelineRun(
            pipeline_id=pipeline.id,
            status="Succeeded",
            run_type="Manual",
            started_at=datetime(2026, 8, 10 + i, 12, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 8, 10 + i, 12, 5, 0, tzinfo=timezone.utc)
        )
        db.add(pr)
        db.flush()

        ledger = PipelineUsageLedger(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            project_id=project.id,
            pipeline_id=pipeline.id,
            pipeline_name=pipeline.name,
            pipeline_run_id=pr.id,
            execution_type="Manual",
            execution_engine="CopyEngine",
            activity_count=2,
            classification="Basic",
            started_at=pr.started_at,
            ended_at=pr.ended_at,
            duration_seconds=300,
            execution_status="Succeeded",
            billing_period_key=period_key,
            is_billable=True,
            calculated_charge=0.50,
            pricing_version_id=pricing_v.id
        )
        db.add(ledger)
    db.commit()

    # Generate invoice
    invoice = InvoiceService.generate_monthly_invoice(
        db=db,
        tenant_id=tenant.id,
        period_key=period_key,
        notes="Standard August monthly statement"
    )

    assert invoice is not None
    assert invoice.tenant_id == tenant.id
    assert invoice.period_key == period_key
    assert invoice.status == "Issued"
    assert invoice.currency == "INR"

    # Base subscription price check: Starter is ₹9,999.00
    expected_sub_price = float(pricing_v.monthly_base_price)
    assert float(invoice.subscription_amount) == expected_sub_price

    # 3 runs are within Starter's 10,000 allowance, so overages = 0
    assert float(invoice.overage_amount) == 0.00
    assert float(invoice.compute_amount) == 0.00

    # Subtotal check
    expected_subtotal = expected_sub_price
    assert float(invoice.subtotal_amount) == expected_subtotal

    # Tax check: 18.00% GST
    expected_tax = round(expected_subtotal * 0.18, 2)
    assert float(invoice.tax_amount) == expected_tax
    assert float(invoice.tax_percent) == 18.00

    # Total payable check
    expected_total = expected_subtotal + expected_tax
    assert float(invoice.total_amount) == expected_total

    # Check line items
    assert len(invoice.line_items) >= 1
    sub_item = invoice.line_items[0]
    assert sub_item.item_type == "SubscriptionBase"
    assert float(sub_item.amount) == expected_sub_price


def test_invoicing_idempotency_prevents_duplicate_billing(db: Session, invoice_setup: dict):
    """
    Verifies that repeatedly generating an invoice for the same period
    returns the existing invoice without creating duplicate records.
    """
    tenant = invoice_setup["tenant"]
    period_key = "2026-07"

    inv1 = InvoiceService.generate_monthly_invoice(db, tenant.id, period_key)
    inv2 = InvoiceService.generate_monthly_invoice(db, tenant.id, period_key)

    assert inv1.id == inv2.id
    assert inv1.invoice_number == inv2.invoice_number

    # Verify count in database is exactly 1
    count = db.query(BillingInvoice).filter(
        BillingInvoice.tenant_id == tenant.id,
        BillingInvoice.period_key == period_key
    ).count()
    assert count == 1


def test_pdf_invoice_generator_output(db: Session, invoice_setup: dict):
    """
    Verifies that standard ISO 32000-1 PDF statement generation produces a valid,
    compliant PDF stream without errors.
    """
    tenant = invoice_setup["tenant"]
    period_key = "2026-06"

    invoice = InvoiceService.generate_monthly_invoice(db, tenant.id, period_key)
    pdf_bytes = InvoiceService.generate_invoice_pdf(db, invoice.id)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_bytes
    assert b"DATAFORGE" in pdf_bytes


def test_offline_bank_transfer_payment_and_status_transition(db: Session, invoice_setup: dict):
    """
    Verifies B2B offline bank transfer / wire payment reconciliation:
    1. Partial payment keeps invoice in 'Issued' state.
    2. Final payment completing the total transitions invoice to 'Paid'.
    3. Tamper-evident AuditLog recorded.
    """
    tenant = invoice_setup["tenant"]
    period_key = "2026-05"

    invoice = InvoiceService.generate_monthly_invoice(db, tenant.id, period_key)
    total_due = float(invoice.total_amount)
    assert invoice.status == "Issued"

    # Step 1: Partial payment (50%)
    half_payment = round(total_due / 2.0, 2)
    p1 = InvoiceService.record_payment(
        db=db,
        invoice_id=invoice.id,
        payment_data={
            "payment_reference": f"UTR-{uuid.uuid4().hex[:8].upper()}",
            "payment_method": "BankTransfer",
            "amount": half_payment,
            "notes": "First installment wire payment"
        },
        admin_user_id="admin_verifier_1"
    )

    assert p1.id is not None
    assert p1.payment_status == "Completed"
    assert invoice.status == "Issued"  # Still outstanding balance

    # Step 2: Final installment payment
    remaining = round(total_due - half_payment, 2)
    p2 = InvoiceService.record_payment(
        db=db,
        invoice_id=invoice.id,
        payment_data={
            "payment_reference": f"UTR-{uuid.uuid4().hex[:8].upper()}",
            "payment_method": "BankTransfer",
            "amount": remaining,
            "notes": "Final balance settlement"
        },
        admin_user_id="admin_verifier_1"
    )

    assert invoice.status == "Paid"

    # Verify audit logs
    audit = db.query(AuditLog).filter(
        AuditLog.action == "PAYMENT_RECORDED",
        AuditLog.resource_id == invoice.id
    ).order_by(AuditLog.created_at.desc()).first()
    assert audit is not None
    assert audit.details["invoice_status"] == "Paid"


def test_api_invoices_and_pdf_download(client: TestClient, admin_token: str, invoice_setup: dict):
    """
    Tests REST API endpoints:
    - GET /api/v1/billing/invoices
    - GET /api/v1/billing/invoices/{id}
    - GET /api/v1/billing/invoices/{id}/download
    - POST /api/v1/billing/invoices/{id}/payments
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    tenant = invoice_setup["tenant"]
    workspace = invoice_setup["workspace"]

    # 1. Trigger invoice generation via API
    gen_resp = client.post(
        f"/api/v1/billing/invoices/generate?workspace_id={workspace.id}",
        headers=headers,
        json={"period_key": "2026-04", "notes": "API generated invoice"}
    )
    assert gen_resp.status_code == 200, gen_resp.text
    inv_data = gen_resp.json()
    inv_id = inv_data["id"]
    assert inv_data["period_key"] == "2026-04"
    assert inv_data["status"] == "Issued"
    assert len(inv_data["line_items"]) >= 1

    # 2. List invoices
    list_resp = client.get(
        f"/api/v1/billing/invoices?workspace_id={workspace.id}",
        headers=headers
    )
    assert list_resp.status_code == 200
    invoices = list_resp.json()
    assert any(i["id"] == inv_id for i in invoices)

    # 3. Get invoice details
    detail_resp = client.get(f"/api/v1/billing/invoices/{inv_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == inv_id

    # 4. Download PDF statement
    pdf_resp = client.get(f"/api/v1/billing/invoices/{inv_id}/download", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in pdf_resp.headers["content-disposition"]
    assert pdf_resp.content.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_resp.content

    # 5. Record verified payment via API
    pay_resp = client.post(
        f"/api/v1/billing/invoices/{inv_id}/payments",
        headers=headers,
        json={
            "payment_reference": f"PO-{uuid.uuid4().hex[:6].upper()}",
            "payment_method": "CorporatePO",
            "amount": inv_data["total_amount"],
            "currency": "INR",
            "notes": "Corporate PO settlement via NetBanking"
        }
    )
    assert pay_resp.status_code == 200, pay_resp.text
    pay_data = pay_resp.json()
    assert pay_data["payment_status"] == "Completed"

    # Verify status changed to Paid
    updated_inv = client.get(f"/api/v1/billing/invoices/{inv_id}", headers=headers).json()
    assert updated_inv["status"] == "Paid"
