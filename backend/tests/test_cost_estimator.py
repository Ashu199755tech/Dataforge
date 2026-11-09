import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.services.cost_estimator_service import CostEstimatorService
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
def user_token(db: Session):
    user = db.query(User).filter(User.email == "estimator_user@dataforge.test").first()
    if not user:
        user = User(
            email="estimator_user@dataforge.test",
            full_name="Estimator Test User",
            hashed_password="hashed_test_pass",
            role="Viewer"
        )
        db.add(user)
        db.commit()
    return create_access_token({"sub": user.id, "role": user.role})


def test_cost_estimator_basic_starter_workload():
    """
    Workload within 10,000 runs with <= 5 activities and 0% Spark
    should recommend Starter plan with ₹0 overage.
    """
    res = CostEstimatorService.estimate(
        expected_pipelines=5,
        monthly_pipeline_runs=6000,
        average_activities_per_pipeline=3,
        copy_engine_pct=80.0,
        spark_engine_pct=0.0,
        sql_pushdown_pct=20.0,
        data_volume_gb=100.0,
        runtime_hours_per_month=30.0,
        deployment_model="BYOC",
        billing_period="Monthly"
    )

    assert res.recommended_plan == "starter"
    assert res.activity_classification == "Basic"
    assert res.rate_per_overage_run == 0.50
    assert res.included_runs == 10000
    assert res.overage_runs == 0
    assert res.overage_cost == 0.00
    assert res.base_subscription_cost == 9999.00
    assert res.estimated_software_subtotal == 9999.00
    assert res.estimated_tax_gst == round(9999.00 * 0.18, 2)
    assert res.estimated_software_total == round(9999.00 * 1.18, 2)
    assert len(res.plan_comparison) == 3


def test_cost_estimator_pro_overage_calculations():
    """
    Workload of 65,000 runs with 10 activities (Standard ₹1.50) and 20% Spark
    should recommend Professional plan with 15,000 overage runs.
    """
    res = CostEstimatorService.estimate(
        expected_pipelines=15,
        monthly_pipeline_runs=65000,
        average_activities_per_pipeline=10,
        copy_engine_pct=60.0,
        spark_engine_pct=20.0,
        sql_pushdown_pct=20.0,
        data_volume_gb=800.0,
        runtime_hours_per_month=100.0,
        deployment_model="BYOC",
        billing_period="Monthly"
    )

    assert res.recommended_plan == "professional"
    assert res.activity_classification == "Standard"
    assert res.rate_per_overage_run == 1.50
    assert res.included_runs == 50000
    assert res.overage_runs == 15000

    # 15,000 * 1.50 = ₹22,500 overage cost
    expected_overage = 22500.00
    assert res.overage_cost == expected_overage
    assert res.base_subscription_cost == 29999.00

    # BYOC mode: DataForge Spark compute charge = 0
    assert res.spark_compute_cost == 0.00
    assert res.cloud_markup_percent == 0.0

    expected_subtotal = 29999.00 + expected_overage
    assert res.estimated_software_subtotal == expected_subtotal
    assert res.estimated_tax_gst == round(expected_subtotal * 0.18, 2)
    assert res.estimated_software_total == round(expected_subtotal * 1.18, 2)


def test_cost_estimator_enterprise_complex_workload():
    """
    Workload of 350,000 runs with 35 activities (Complex ₹5.00)
    should recommend Enterprise plan with 100,000 overage runs.
    """
    res = CostEstimatorService.estimate(
        expected_pipelines=50,
        monthly_pipeline_runs=350000,
        average_activities_per_pipeline=35,
        copy_engine_pct=50.0,
        spark_engine_pct=30.0,
        sql_pushdown_pct=20.0,
        data_volume_gb=10000.0,
        runtime_hours_per_month=500.0,
        deployment_model="BYOC",
        billing_period="Monthly"
    )

    assert res.recommended_plan == "enterprise"
    assert res.activity_classification == "Complex"
    assert res.rate_per_overage_run == 5.00
    assert res.included_runs == 250000
    assert res.overage_runs == 100000

    # 100,000 * 5.00 = ₹500,000
    assert res.overage_cost == 500000.00
    assert res.base_subscription_cost == 99999.00
    assert res.estimated_software_subtotal == 599999.00


def test_cost_estimator_annual_discount():
    """
    Annual billing should apply ~17% discounted equivalent monthly subscription base.
    """
    res_monthly = CostEstimatorService.estimate(
        monthly_pipeline_runs=20000,
        billing_period="Monthly"
    )
    res_annual = CostEstimatorService.estimate(
        monthly_pipeline_runs=20000,
        billing_period="Annual"
    )

    assert res_annual.base_subscription_cost < res_monthly.base_subscription_cost
    # Pro monthly is ₹29,999 vs annual equivalent of ₹24,999.17
    assert res_annual.base_subscription_cost == 24999.17
    assert res_annual.estimated_software_total < res_monthly.estimated_software_total


def test_cost_estimator_saas_vs_byoc_spark():
    """
    Verifies that SaaS mode charges ₹45/hr for managed Spark compute,
    whereas BYOC mode maintains 0% markup and ₹0 software charge.
    """
    res_byoc = CostEstimatorService.estimate(
        monthly_pipeline_runs=30000,
        spark_engine_pct=50.0,
        runtime_hours_per_month=100.0,
        deployment_model="BYOC"
    )
    res_saas = CostEstimatorService.estimate(
        monthly_pipeline_runs=30000,
        spark_engine_pct=50.0,
        runtime_hours_per_month=100.0,
        deployment_model="SaaS"
    )

    # 50% of 100 hrs = 50 hrs
    # BYOC = 0
    assert res_byoc.spark_compute_cost == 0.00
    # SaaS = 50 * 45 = 2250.00
    assert res_saas.spark_compute_cost == 2250.00
    assert res_saas.estimated_software_subtotal > res_byoc.estimated_software_subtotal


def test_api_cost_estimate(client: TestClient, user_token: str):
    """
    Verifies POST /api/v1/billing/estimate REST API.
    """
    headers = {"Authorization": f"Bearer {user_token}"}
    payload = {
        "expected_pipelines": 20,
        "monthly_pipeline_runs": 45000,
        "average_activities_per_pipeline": 12,
        "copy_engine_pct": 70.0,
        "spark_engine_pct": 15.0,
        "sql_pushdown_pct": 15.0,
        "data_volume_gb": 1200.0,
        "runtime_hours_per_month": 150.0,
        "deployment_model": "BYOC",
        "billing_period": "Monthly"
    }

    resp = client.post("/api/v1/billing/estimate", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["recommended_plan"] == "professional"
    assert data["activity_classification"] == "Standard"
    assert data["rate_per_overage_run"] == 1.50
    assert data["included_runs"] == 50000
    assert data["overage_runs"] == 0
    assert data["base_subscription_cost"] == 29999.00
    assert len(data["plan_comparison"]) == 3
    assert len(data["assumptions_and_limitations"]) >= 3
    assert data["estimated_savings_percent"] > 0
