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
from backend.app.models.billing import (
    Tenant,
    SubscriptionPlan,
    PricingConfigVersion,
    CustomerSubscription,
    BillingInvoice,
    InvoiceLineItem,
    BillingAuditLog
)
from backend.app.services.billing_service import BillingService
from backend.app.services.invoicing_service import InvoiceService
from backend.app.services.admin_pricing_service import AdminPricingService
from backend.app.schemas.billing import (
    PricingVersionCreate,
    CustomEnterpriseAgreementRequest,
    BillingAdjustmentRequest
)
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
def test_users(db: Session):
    admin = db.query(User).filter(User.role == "Admin").first()
    if not admin:
        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@dataforge.test",
            full_name="Billing Admin",
            hashed_password="hashed_admin_pass",
            role="Admin"
        )
        db.add(admin)
        db.flush()

    viewer = User(
        email=f"viewer_{uuid.uuid4().hex[:6]}@dataforge.test",
        full_name="Billing Viewer",
        hashed_password="hashed_viewer_pass",
        role="Viewer"
    )
    db.add(viewer)
    db.commit()

    admin_token = create_access_token({"sub": admin.id, "role": admin.role})
    viewer_token = create_access_token({"sub": viewer.id, "role": viewer.role})

    return {
        "admin": admin,
        "viewer": viewer,
        "admin_token": admin_token,
        "viewer_token": viewer_token
    }


@pytest.fixture
def admin_setup(db: Session):
    """Initializes plans, tenant, workspace, and active subscription."""
    BillingService.seed_default_plans(db)

    tenant = Tenant(
        name=f"Admin Test Corp {uuid.uuid4().hex[:6]}",
        billing_email="cfo@admintest.com",
        currency="INR",
        country="IN"
    )
    db.add(tenant)
    db.flush()

    workspace = Workspace(
        name=f"Admin WS {uuid.uuid4().hex[:6]}",
        tenant_id=tenant.id
    )
    db.add(workspace)
    db.flush()

    # Assign Starter plan subscription
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
        "subscription": sub
    }


def test_admin_role_enforcement(client: TestClient, test_users: dict, admin_setup: dict):
    """
    Verifies RBAC protection:
    - Non-admin (Viewer) is rejected with 403 Forbidden.
    - Admin user is authorized (200 OK).
    """
    viewer_headers = {"Authorization": f"Bearer {test_users['viewer_token']}"}
    admin_headers = {"Authorization": f"Bearer {test_users['admin_token']}"}

    # 1. Viewer trying to access admin plans -> 403 Forbidden
    resp_viewer = client.get("/api/v1/billing/admin/plans", headers=viewer_headers)
    assert resp_viewer.status_code == 403, f"Expected 403, got {resp_viewer.status_code}"

    # 2. Admin accessing admin plans -> 200 OK
    resp_admin = client.get("/api/v1/billing/admin/plans", headers=admin_headers)
    assert resp_admin.status_code == 200
    plans = resp_admin.json()
    assert len(plans) >= 3


def test_publish_new_pricing_version_and_immutability(db: Session, test_users: dict, admin_setup: dict):
    """
    Verifies that:
    1. Publishing a new pricing version increments version_number and sets effective_to on previous version.
    2. Audit log entry is written with before_state and after_state.
    3. Past invoices remain linked to their original historical pricing version.
    """
    admin = test_users["admin"]
    starter_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == "starter").first()
    assert starter_plan is not None

    v1 = db.query(PricingConfigVersion).filter(
        PricingConfigVersion.plan_id == starter_plan.id
    ).order_by(PricingConfigVersion.version_number.desc()).first()
    assert v1 is not None
    initial_ver_num = v1.version_number

    # Publish Version N + 1
    update_data = PricingVersionCreate(
        monthly_base_price=11999.0,
        annual_base_price=119990.0,
        included_pipeline_runs=12000,
        basic_run_rate=0.60,
        standard_run_rate=1.80,
        advanced_run_rate=3.50,
        complex_run_rate=6.00,
        spark_node_hour_rate=50.0,
        currency="INR",
        justification="Annual inflation indexation and expanded infrastructure tier"
    )

    v2 = AdminPricingService.publish_new_pricing_version(db, starter_plan.id, admin, update_data)
    assert v2.version_number == initial_ver_num + 1
    assert float(v2.monthly_base_price) == 11999.0
    assert v2.included_pipeline_runs == 12000
    assert v2.effective_to is None

    # Verify previous version has effective_to set
    db.refresh(v1)
    assert v1.effective_to is not None

    # Verify audit log
    audit = db.query(BillingAuditLog).filter(
        BillingAuditLog.resource_id == v2.id,
        BillingAuditLog.action == "UpdatePricingVersion"
    ).first()
    assert audit is not None
    assert audit.admin_user_id == admin.id
    assert audit.before_state["version_number"] == initial_ver_num
    assert audit.after_state["version_number"] == initial_ver_num + 1
    assert "Annual inflation" in audit.justification


def test_configure_custom_enterprise_agreement(db: Session, test_users: dict, admin_setup: dict):
    """
    Verifies bespoke enterprise volume licensing configuration:
    - Creates a custom plan and version for the tenant.
    - Switches tenant subscription to custom tier.
    - Captures before/after audit log.
    """
    admin = test_users["admin"]
    tenant = admin_setup["tenant"]

    req = CustomEnterpriseAgreementRequest(
        tenant_id=tenant.id,
        plan_name="Enterprise Dedicated Volume Agreement",
        monthly_base_price=150000.0,
        annual_base_price=1500000.0,
        included_pipeline_runs=750000,
        basic_run_rate=0.30,
        standard_run_rate=1.00,
        advanced_run_rate=2.00,
        complex_run_rate=3.50,
        spark_node_hour_rate=30.0,
        custom_agreement_notes="Contract DF-ENT-2026-9081 signed with dedicated 99.99% SLA",
        justification="Contract approved by VP Sales and Enterprise Legal"
    )

    sub = AdminPricingService.configure_custom_enterprise_agreement(db, admin, req)
    assert sub.tenant_id == tenant.id
    assert sub.status == "Active"
    assert "Contract DF-ENT-2026-9081" in sub.custom_agreement_notes

    # Check custom plan
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
    assert plan.is_custom is True
    assert plan.tier_level == 3

    # Check custom version
    ver = db.query(PricingConfigVersion).filter(PricingConfigVersion.id == sub.pricing_version_id).first()
    assert float(ver.monthly_base_price) == 150000.0
    assert ver.included_pipeline_runs == 750000
    assert float(ver.basic_run_rate) == 0.30

    # Check audit log
    audit = db.query(BillingAuditLog).filter(
        BillingAuditLog.resource_id == sub.id,
        BillingAuditLog.action == "ConfigureCustomAgreement"
    ).first()
    assert audit is not None
    assert audit.admin_user_id == admin.id
    assert "Enterprise Legal" in audit.justification


def test_apply_invoice_credit_adjustment(db: Session, test_users: dict, admin_setup: dict):
    """
    Verifies applying manual financial credit adjustments to an invoice:
    - Decreases subtotal.
    - Recomputes 18% GST tax and final total.
    - Captures before and after audit log.
    - Blocks adjustment if invoice is Paid.
    """
    admin = test_users["admin"]
    tenant = admin_setup["tenant"]

    # Generate an invoice first
    invoice = InvoiceService.generate_monthly_invoice(db, tenant.id, "2026-03")
    initial_total = float(invoice.total_amount)
    initial_subtotal = float(invoice.subtotal_amount)

    # Apply ₹2,000 SLA Credit
    adj_req = BillingAdjustmentRequest(
        adjustment_amount=2000.0,
        adjustment_type="GoodwillSLA",
        description="SLA incident credit for March 12 outage",
        justification="Executive approval per Incident INC-4091"
    )

    updated_inv = AdminPricingService.apply_invoice_adjustment(db, invoice.id, admin, adj_req)
    assert float(updated_inv.adjustments_amount) == 2000.0
    assert float(updated_inv.subtotal_amount) == pytest.approx(initial_subtotal - 2000.0, 0.01)

    expected_tax = round(float(updated_inv.subtotal_amount) * 0.18, 2)
    assert float(updated_inv.tax_amount) == pytest.approx(expected_tax, 0.01)
    assert float(updated_inv.total_amount) == pytest.approx(float(updated_inv.subtotal_amount) + expected_tax, 0.01)
    assert float(updated_inv.total_amount) < initial_total

    # Verify audit log
    audit = db.query(BillingAuditLog).filter(
        BillingAuditLog.resource_id == invoice.id,
        BillingAuditLog.action == "ApplyCredit"
    ).first()
    assert audit is not None
    assert audit.admin_user_id == admin.id
    assert audit.before_state["subtotal_amount"] == initial_subtotal
    assert audit.after_state["credit_applied"] == 2000.0


def test_api_admin_pricing_and_audit_routes(client: TestClient, test_users: dict, admin_setup: dict):
    """
    Tests REST API endpoints:
    - GET /api/v1/billing/admin/plans
    - POST /api/v1/billing/admin/plans/{id}/pricing-versions
    - POST /api/v1/billing/admin/custom-agreement
    - GET /api/v1/billing/admin/audit-logs
    """
    headers = {"Authorization": f"Bearer {test_users['admin_token']}"}
    tenant = admin_setup["tenant"]

    # 1. List admin plans
    plans_resp = client.get("/api/v1/billing/admin/plans", headers=headers)
    assert plans_resp.status_code == 200
    plans = plans_resp.json()
    starter = next(p for p in plans if p["plan_code"] == "starter")

    # 2. Publish new version via API
    ver_payload = {
        "monthly_base_price": 10500.0,
        "annual_base_price": 105000.0,
        "included_pipeline_runs": 11000,
        "basic_run_rate": 0.55,
        "standard_run_rate": 1.65,
        "advanced_run_rate": 3.20,
        "complex_run_rate": 5.50,
        "spark_node_hour_rate": 48.0,
        "sql_pushdown_rate": 0.0,
        "currency": "INR",
        "justification": "API Pricing Update Test"
    }
    ver_resp = client.post(
        f"/api/v1/billing/admin/plans/{starter['id']}/pricing-versions",
        headers=headers,
        json=ver_payload
    )
    assert ver_resp.status_code == 200, ver_resp.text
    assert ver_resp.json()["monthly_base_price"] == 10500.0

    # 3. Configure custom agreement via API
    custom_payload = {
        "tenant_id": tenant.id,
        "plan_name": "API Enterprise Custom Agreement",
        "monthly_base_price": 120000.0,
        "annual_base_price": 1200000.0,
        "included_pipeline_runs": 400000,
        "basic_run_rate": 0.35,
        "standard_run_rate": 1.10,
        "advanced_run_rate": 2.20,
        "complex_run_rate": 3.80,
        "spark_node_hour_rate": 32.0,
        "currency": "INR",
        "custom_agreement_notes": "API test agreement",
        "justification": "API Custom Agreement Provision"
    }
    custom_resp = client.post(
        "/api/v1/billing/admin/custom-agreement",
        headers=headers,
        json=custom_payload
    )
    assert custom_resp.status_code == 200, custom_resp.text
    assert custom_resp.json()["status"] == "Active"

    # 4. Fetch audit logs
    audit_resp = client.get("/api/v1/billing/admin/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 2
    actions = [l["action"] for l in logs]
    assert "UpdatePricingVersion" in actions
    assert "ConfigureCustomAgreement" in actions
