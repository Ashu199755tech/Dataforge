import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.billing import (
    Tenant,
    SubscriptionPlan,
    PricingConfigVersion,
    CustomerSubscription
)
from backend.app.services.billing_service import BillingService
from backend.app.models.user import User
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
            email="test_admin@dataforge.test",
            full_name="Test Admin",
            hashed_password="hashed_pass_test",
            role="Admin"
        )
        db.add(admin)
        db.commit()
    return create_access_token({"sub": admin.id, "role": admin.role})


def test_seed_default_subscription_plans(db: Session):
    """Verifies Starter, Professional, and Enterprise plans are seeded with exact specs."""
    BillingService.seed_default_plans(db)

    plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.tier_level.asc()).all()
    assert len(plans) >= 3

    starter = next(p for p in plans if p.plan_code == "starter")
    assert starter.name == "Starter Plan"
    assert starter.tier_level == 1
    assert len(starter.pricing_versions) >= 1
    v1_starter = next(v for v in starter.pricing_versions if v.version_number == 1)
    assert float(v1_starter.monthly_base_price) == 9999.00
    assert float(v1_starter.annual_base_price) == 99990.00
    assert v1_starter.included_pipeline_runs == 10000
    assert float(v1_starter.basic_run_rate) == 0.50
    assert float(v1_starter.standard_run_rate) == 1.50
    assert float(v1_starter.advanced_run_rate) == 3.00

    pro = next(p for p in plans if p.plan_code == "professional")
    assert pro.name == "Professional Plan"
    assert pro.tier_level == 2
    v1_pro = next(v for v in pro.pricing_versions if v.version_number == 1)
    assert float(v1_pro.monthly_base_price) == 29999.00
    assert v1_pro.included_pipeline_runs == 50000
    assert pro.features["spark_engine"] is True
    assert pro.features["sql_pushdown"] is True

    ent = next(p for p in plans if p.plan_code == "enterprise")
    assert ent.name == "Enterprise Plan"
    assert ent.tier_level == 3
    v1_ent = ent.pricing_versions[0]
    assert float(v1_ent.monthly_base_price) == 99999.00
    assert v1_ent.included_pipeline_runs == 250000
    assert ent.features["self_hosted_runtime"] is True


def test_api_list_subscription_plans(client: TestClient, admin_token: str):
    """Validates GET /api/v1/billing/plans returns active plans and versioned rates."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/v1/billing/plans", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    plan_codes = [p["plan_code"] for p in data]
    assert "starter" in plan_codes
    assert "professional" in plan_codes
    assert "enterprise" in plan_codes

    pro_plan = next(p for p in data if p["plan_code"] == "professional")
    assert pro_plan["active_pricing"]["monthly_base_price"] == 29999.00
    assert pro_plan["active_pricing"]["included_pipeline_runs"] == 50000


def test_api_get_single_plan(client: TestClient, admin_token: str, db: Session):
    """Validates GET /api/v1/billing/plans/{plan_id}."""
    pro = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == "professional").first()
    assert pro is not None

    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get(f"/api/v1/billing/plans/{pro.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pro.id
    assert data["name"] == "Professional Plan"
    assert data["active_pricing"]["monthly_base_price"] == 29999.00


def test_api_get_current_subscription(client: TestClient, admin_token: str):
    """Validates GET /api/v1/billing/subscription returns the tenant's active subscription."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/v1/billing/subscription", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["status"] == "Active"
    assert "plan" in data
    assert "pricing_version" in data


def test_api_switch_subscription_plan(client: TestClient, admin_token: str, db: Session):
    """Validates upgrading/switching to Enterprise plan via POST /api/v1/billing/subscription."""
    ent = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == "enterprise").first()
    assert ent is not None

    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "plan_id": ent.id,
        "billing_period": "Annual",
        "custom_agreement_notes": "Contracted Enterprise Tier with 24/7 SLA"
    }
    response = client.post("/api/v1/billing/subscription", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plan_id"] == ent.id
    assert data["billing_period"] == "Annual"
    assert data["status"] == "Active"
    assert data["custom_agreement_notes"] == "Contracted Enterprise Tier with 24/7 SLA"


def test_api_get_billing_overview(client: TestClient, admin_token: str):
    """Validates GET /api/v1/billing/overview returns complete commercial metrics."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/v1/billing/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert "tenant" in data
    assert "plan_name" in data
    assert "monthly_subscription_amount" in data
    assert "included_runs" in data
    assert "consumed_runs" in data
    assert "remaining_runs" in data
    assert "overage_runs" in data
    assert "estimated_total_software_charges" in data
    assert data["currency"] in ["INR", "USD", "EUR", "GBP"]
    assert data["deployment_model"] in ["BYOC", "SaaS", "Hybrid"]
