import pytest
import uuid
from datetime import datetime, timezone, timedelta
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
    UsageAggregation
)
from backend.app.services.billing_service import BillingService
from backend.app.services.metering_service import UsageMeteringEngine
from backend.app.services.rating_engine import RatingEngine
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
            email="rating_admin@dataforge.test",
            full_name="Rating Admin",
            hashed_password="hashed_rating_pass",
            role="Admin"
        )
        db.add(admin)
        db.commit()
    return create_access_token({"sub": admin.id, "role": admin.role})


@pytest.fixture
def rating_setup(db: Session):
    """Provisions a test tenant, workspace, project, pipeline, and clean billing period."""
    BillingService.seed_default_plans(db)
    tenant = db.query(Tenant).filter(Tenant.name == "Rating Test Tenant").first()
    if not tenant:
        tenant = Tenant(
            name="Rating Test Tenant",
            billing_email="rating@dataforge.test",
            currency="INR",
            country="IN",
            deployment_model="BYOC"
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

    ws = db.query(Workspace).filter(Workspace.name == "Rating Test Workspace").first()
    if not ws:
        ws = Workspace(name="Rating Test Workspace", tenant_id=tenant.id)
        db.add(ws)
        db.commit()
        db.refresh(ws)

    project = db.query(Project).filter(Project.name == "Rating Test Project").first()
    if not project:
        project = Project(name="Rating Test Project", workspace_id=ws.id)
        db.add(project)
        db.commit()
        db.refresh(project)

    pipeline = db.query(Pipeline).filter(Pipeline.name == "Rating Pipeline").first()
    if not pipeline:
        pipeline = Pipeline(
            name="Rating Pipeline",
            project_id=project.id,
            definition_json={"activities": []}
        )
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)

    # Attach Professional subscription
    pro_plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.plan_code == "professional").first()
    sub = db.query(CustomerSubscription).filter(CustomerSubscription.tenant_id == tenant.id).first()
    now = datetime.now(timezone.utc)
    if not sub:
        sub = CustomerSubscription(
            tenant_id=tenant.id,
            workspace_id=ws.id,
            plan_id=pro_plan.id,
            pricing_version_id=pro_plan.pricing_versions[0].id,
            billing_period="Monthly",
            status="Active",
            current_period_start=now,
            current_period_end=now + timedelta(days=30)
        )
        db.add(sub)
        db.commit()
        db.refresh(sub)

    period_key = now.strftime("%Y-%m")
    # Clean previous test ledger items for this tenant
    db.query(PipelineUsageLedger).filter(
        PipelineUsageLedger.tenant_id == tenant.id,
        PipelineUsageLedger.billing_period_key == period_key
    ).delete()
    db.query(UsageAggregation).filter(
        UsageAggregation.tenant_id == tenant.id,
        UsageAggregation.period_key == period_key
    ).delete()
    db.commit()

    return {
        "tenant": tenant,
        "workspace": ws,
        "project": project,
        "pipeline": pipeline,
        "subscription": sub,
        "period_key": period_key
    }


def test_rating_within_included_allowance(rating_setup, db: Session):
    """Verifies executions within subscription allowance incur zero additional overage fee."""
    tenant = rating_setup["tenant"]
    ws = rating_setup["workspace"]
    project = rating_setup["project"]
    pipeline = rating_setup["pipeline"]
    period_key = rating_setup["period_key"]

    now = datetime.now(timezone.utc)
    # Add 3 basic billable runs
    for i in range(3):
        run = PipelineRun(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline.id,
            run_type="Manual",
            status="Succeeded",
            started_at=now + timedelta(minutes=i),
            ended_at=now + timedelta(minutes=i, seconds=10),
            duration_seconds=10,
            total_activities=2
        )
        db.add(run)
        db.commit()
        UsageMeteringEngine.record_pipeline_execution(db, run.id)

    agg = RatingEngine.aggregate_usage_for_period(
        db=db,
        tenant_id=tenant.id,
        period_key=period_key,
        workspace_id=ws.id
    )

    assert agg.total_runs == 3
    assert agg.billable_runs == 3
    assert agg.included_runs_consumed == 3
    assert agg.overage_runs == 0
    assert float(agg.total_overage_charge) == 0.00
    assert float(agg.total_charge) == 0.00


def test_graduated_overage_rating_tiers(rating_setup, db: Session):
    """Validates graduated surcharge calculation when executions exceed included allowance."""
    tenant = rating_setup["tenant"]
    ws = rating_setup["workspace"]
    pipeline = rating_setup["pipeline"]
    sub = rating_setup["subscription"]
    period_key = rating_setup["period_key"]

    # Temporarily set included allowance to 1 run to test overage transition
    pv = sub.pricing_version
    original_allowance = pv.included_pipeline_runs
    pv.included_pipeline_runs = 1
    db.commit()

    try:
        now = datetime.now(timezone.utc)
        # 1. Run 1: Basic (within allowance) -> absorbed by allowance
        run1 = PipelineRun(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline.id,
            status="Succeeded",
            started_at=now + timedelta(minutes=1),
            ended_at=now + timedelta(minutes=1, seconds=5),
            duration_seconds=5,
            total_activities=2  # Basic: ₹0.50
        )
        db.add(run1)
        db.commit()
        UsageMeteringEngine.record_pipeline_execution(db, run1.id)

        # 2. Run 2: Basic overage -> ₹0.50
        run2 = PipelineRun(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline.id,
            status="Succeeded",
            started_at=now + timedelta(minutes=2),
            ended_at=now + timedelta(minutes=2, seconds=5),
            duration_seconds=5,
            total_activities=3  # Basic: ₹0.50
        )
        db.add(run2)
        db.commit()
        UsageMeteringEngine.record_pipeline_execution(db, run2.id)

        # 3. Run 3: Standard overage -> ₹1.50
        run3 = PipelineRun(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline.id,
            status="Succeeded",
            started_at=now + timedelta(minutes=3),
            ended_at=now + timedelta(minutes=3, seconds=15),
            duration_seconds=15,
            total_activities=10  # Standard: ₹1.50
        )
        db.add(run3)
        db.commit()
        UsageMeteringEngine.record_pipeline_execution(db, run3.id)

        # 4. Run 4: Advanced overage -> ₹3.00
        run4 = PipelineRun(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline.id,
            status="Succeeded",
            started_at=now + timedelta(minutes=4),
            ended_at=now + timedelta(minutes=4, seconds=25),
            duration_seconds=25,
            total_activities=20  # Advanced: ₹3.00
        )
        db.add(run4)
        db.commit()
        UsageMeteringEngine.record_pipeline_execution(db, run4.id)

        agg = RatingEngine.aggregate_usage_for_period(
            db=db,
            tenant_id=tenant.id,
            period_key=period_key,
            workspace_id=ws.id
        )

        assert agg.total_runs == 4
        assert agg.billable_runs == 4
        assert agg.included_runs_consumed == 1
        assert agg.overage_runs == 3
        # Expected overage: Run 2 (₹0.50) + Run 3 (₹1.50) + Run 4 (₹3.00) = ₹5.00
        assert float(agg.total_overage_charge) == 5.00
        assert float(agg.total_charge) == 5.00
    finally:
        pv.included_pipeline_runs = original_allowance
        db.commit()


def test_spark_compute_node_hour_rating(rating_setup, db: Session):
    """Verifies Spark worker hours are measured and rated at ₹45.00 / node-hour."""
    tenant = rating_setup["tenant"]
    ws = rating_setup["workspace"]
    pipeline = rating_setup["pipeline"]
    period_key = rating_setup["period_key"]

    now = datetime.now(timezone.utc)
    # Create Spark pipeline run lasting 7200 seconds (2.0 hours)
    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline.id,
        status="Succeeded",
        started_at=now,
        ended_at=now + timedelta(seconds=7200),
        duration_seconds=7200,
        total_activities=2
    )
    db.add(run)
    db.commit()

    act = ActivityRun(
        pipeline_run_id=run.id,
        activity_id="spark_act_1",
        activity_name="LargeSparkAggregation",
        activity_type="SparkDataFlow",
        status="Succeeded",
        duration_seconds=7200
    )
    db.add(act)
    db.commit()

    ledger = UsageMeteringEngine.record_pipeline_execution(db, run.id)
    assert ledger.execution_engine == "SparkEngine"

    agg = RatingEngine.aggregate_usage_for_period(
        db=db,
        tenant_id=tenant.id,
        period_key=period_key,
        workspace_id=ws.id
    )

    # 7200 seconds = 2.0 hours. At ₹45.00/hr = ₹90.00
    assert float(agg.spark_node_hours) == 2.0
    assert float(agg.spark_compute_charge) == 90.00
    assert float(agg.total_charge) == 90.00


def test_api_consumption_summary_and_daily(client: TestClient, admin_token: str, rating_setup, db: Session):
    """Verifies REST endpoints for ADF-parity consumption summaries and daily rollups."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    pipeline = rating_setup["pipeline"]
    period_key = rating_setup["period_key"]

    # Add a sample run
    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline.id,
        status="Succeeded",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        duration_seconds=30,
        total_activities=4
    )
    db.add(run)
    db.commit()
    UsageMeteringEngine.record_pipeline_execution(db, run.id)

    # 1. Summary endpoint
    res_summary = client.get(f"/api/v1/billing/usage/summary?period_key={period_key}", headers=headers)
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["period_key"] == period_key
    assert "classification_breakdown" in summary
    assert "engine_breakdown" in summary
    assert summary["total_runs"] >= 1
    assert "daily_consumption" in summary

    # 2. Daily endpoint
    res_daily = client.get(f"/api/v1/billing/usage/daily?period_key={period_key}", headers=headers)
    assert res_daily.status_code == 200
    daily_items = res_daily.json()
    assert isinstance(daily_items, list)
    assert len(daily_items) >= 1
    assert "total_runs" in daily_items[0]
    assert "billable_runs" in daily_items[0]

    # 3. Recalculate endpoint
    res_recalc = client.post(f"/api/v1/billing/usage/recalculate?period_key={period_key}", headers=headers)
    assert res_recalc.status_code == 200
    recalc = res_recalc.json()
    assert recalc["period_key"] == period_key
    assert recalc["total_runs"] >= 1
