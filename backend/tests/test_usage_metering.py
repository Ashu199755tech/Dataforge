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
    PipelineUsageLedger
)
from backend.app.models.data_quality import AuditLog
from backend.app.services.billing_service import BillingService
from backend.app.services.metering_service import UsageMeteringEngine
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
            email="metering_admin@dataforge.test",
            full_name="Metering Admin",
            hashed_password="hashed_metering_test",
            role="Admin"
        )
        db.add(admin)
        db.commit()
    return create_access_token({"sub": admin.id, "role": admin.role})


@pytest.fixture
def test_setup(db: Session):
    """Provisions a test workspace, project, and pipeline for execution metering."""
    BillingService.seed_default_plans(db)
    tenant = BillingService.get_or_create_default_tenant(db)

    ws = db.query(Workspace).filter(Workspace.name == "Metering Test Workspace").first()
    if not ws:
        ws = Workspace(name="Metering Test Workspace", tenant_id=tenant.id)
        db.add(ws)
        db.commit()
        db.refresh(ws)

    project = db.query(Project).filter(Project.name == "Metering Test Project").first()
    if not project:
        project = Project(name="Metering Test Project", workspace_id=ws.id)
        db.add(project)
        db.commit()
        db.refresh(project)

    pipeline = db.query(Pipeline).filter(Pipeline.name == "Test Metered Pipeline").first()
    if not pipeline:
        pipeline = Pipeline(
            name="Test Metered Pipeline",
            project_id=project.id,
            definition_json={"activities": [{"name": "Copy1", "type": "CopyData"}]}
        )
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)

    return {"tenant": tenant, "workspace": ws, "project": project, "pipeline": pipeline}


def test_activity_classification_thresholds():
    """Validates activity complexity tier classification."""
    assert UsageMeteringEngine.classify_activity_count(1) == "Basic"
    assert UsageMeteringEngine.classify_activity_count(3) == "Basic"
    assert UsageMeteringEngine.classify_activity_count(5) == "Basic"
    assert UsageMeteringEngine.classify_activity_count(6) == "Standard"
    assert UsageMeteringEngine.classify_activity_count(15) == "Standard"
    assert UsageMeteringEngine.classify_activity_count(16) == "Advanced"
    assert UsageMeteringEngine.classify_activity_count(30) == "Advanced"
    assert UsageMeteringEngine.classify_activity_count(31) == "Complex"
    assert UsageMeteringEngine.classify_activity_count(100) == "Complex"


def test_detect_execution_engine(test_setup, db: Session):
    """Validates engine recognition from activity types."""
    pipeline = test_setup["pipeline"]

    # 1. Copy Data
    p_run = PipelineRun(pipeline_id=pipeline.id, status="Succeeded")
    p_run.activity_runs = [
        ActivityRun(activity_id="c1", activity_name="Copy1", activity_type="CopyData")
    ]
    assert UsageMeteringEngine.detect_execution_engine(p_run) == "CopyEngine"

    # 2. Spark DataFlow
    p_run.activity_runs = [
        ActivityRun(activity_id="s1", activity_name="SparkJob", activity_type="SparkDataFlow")
    ]
    assert UsageMeteringEngine.detect_execution_engine(p_run) == "SparkEngine"

    # 3. SQL Pushdown
    p_run.activity_runs = [
        ActivityRun(activity_id="q1", activity_name="Pushdown", activity_type="SqlPushdown")
    ]
    assert UsageMeteringEngine.detect_execution_engine(p_run) == "SqlPushdownEngine"

    # 4. Mixed Hybrid
    p_run.activity_runs = [
        ActivityRun(activity_id="c1", activity_name="Copy1", activity_type="CopyData"),
        ActivityRun(activity_id="s1", activity_name="SparkJob", activity_type="SparkDataFlow")
    ]
    assert UsageMeteringEngine.detect_execution_engine(p_run) == "Hybrid"


def test_billability_decision_rules():
    """Validates billability outcomes across all system and customer scenarios."""
    # Succeeded run -> Billable
    run_succeeded = PipelineRun(status="Succeeded")
    is_billable, reason = UsageMeteringEngine.determine_billability(run_succeeded)
    assert is_billable is True
    assert reason is None

    # Cancelled before start -> Non-billable
    run_cancelled = PipelineRun(status="Cancelled")
    run_cancelled.activity_runs = []
    is_billable, reason = UsageMeteringEngine.determine_billability(run_cancelled)
    assert is_billable is False
    assert reason == "CancelledBeforeStart"

    # Infrastructure system error -> Non-billable (PlatformSystemError)
    run_sys_fail = PipelineRun(status="Failed")
    run_sys_fail.activity_runs = [
        ActivityRun(activity_id="a1", activity_name="A1", status="Failed", error_classification="SystemError")
    ]
    is_billable, reason = UsageMeteringEngine.determine_billability(run_sys_fail)
    assert is_billable is False
    assert reason == "PlatformSystemError"

    # Customer user error (e.g. invalid SQL or schema) -> Billable
    run_user_fail = PipelineRun(status="Failed")
    run_user_fail.activity_runs = [
        ActivityRun(activity_id="a2", activity_name="A2", status="Failed", error_classification="UserError")
    ]
    is_billable, reason = UsageMeteringEngine.determine_billability(run_user_fail)
    assert is_billable is True
    assert reason is None


def test_strict_idempotency_prevents_duplicate_billing(test_setup, db: Session):
    """Guarantees natural key constraint prevents duplicate usage entries for the same pipeline_run_id."""
    pipeline = test_setup["pipeline"]

    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Succeeded",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(seconds=12),
        duration_seconds=12,
        total_activities=3,
        total_rows_read=1000,
        total_rows_written=1000
    )
    db.add(run)
    db.commit()

    # First execution metering
    ledger1 = UsageMeteringEngine.record_pipeline_execution(db, run.id)
    assert ledger1 is not None
    assert ledger1.pipeline_run_id == run.id
    assert ledger1.classification == "Basic"
    assert ledger1.is_billable is True
    assert float(ledger1.calculated_charge) == 0.50

    # Second invocation (e.g. retry or concurrent event)
    ledger2 = UsageMeteringEngine.record_pipeline_execution(db, run.id)
    assert ledger2.id == ledger1.id

    # Verify database has exactly 1 ledger record for this run
    count = db.query(PipelineUsageLedger).filter(
        PipelineUsageLedger.pipeline_run_id == run.id
    ).count()
    assert count == 1


def test_administrative_billability_override(test_setup, db: Session):
    """Verifies administrators can mark runs non-billable with justification and audit trail."""
    pipeline = test_setup["pipeline"]

    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline.id,
        run_type="Scheduled",
        status="Succeeded",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(seconds=45),
        duration_seconds=45,
        total_activities=8
    )
    db.add(run)
    db.commit()

    ledger = UsageMeteringEngine.record_pipeline_execution(db, run.id)
    assert ledger.classification == "Standard"
    assert ledger.is_billable is True
    assert float(ledger.calculated_charge) == 1.50

    # Administrator waives charge due to customer satisfaction ticket
    updated = UsageMeteringEngine.override_ledger_billability(
        db=db,
        ledger_id=ledger.id,
        is_billable=False,
        reason="Goodwill credit applied per CS ticket #9021",
        admin_user_id="admin_user_test"
    )
    assert updated.is_billable is False
    assert updated.non_billable_reason == "Goodwill credit applied per CS ticket #9021"
    assert float(updated.calculated_charge) == 0.0

    # Verify audit log was recorded
    audit = db.query(AuditLog).filter(
        AuditLog.resource_id == ledger.id,
        AuditLog.action == "BILLABILITY_OVERRIDE"
    ).first()
    assert audit is not None
    assert audit.details["new_billable"] is False
    assert audit.details["justification"] == "Goodwill credit applied per CS ticket #9021"


def test_api_list_usage_and_override(client: TestClient, admin_token: str, test_setup, db: Session):
    """Verifies REST API endpoints for querying ledger and overriding billability."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    pipeline = test_setup["pipeline"]

    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline.id,
        status="Succeeded",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(seconds=10),
        duration_seconds=10,
        total_activities=18
    )
    db.add(run)
    db.commit()

    ledger = UsageMeteringEngine.record_pipeline_execution(db, run.id)

    # 1. Query usage list
    res = client.get("/api/v1/billing/usage?classification=Advanced", headers=headers)
    assert res.status_code == 200
    records = res.json()
    assert len(records) >= 1
    target = next((r for r in records if r["id"] == ledger.id), None)
    assert target is not None
    assert target["classification"] == "Advanced"
    assert target["calculated_charge"] == 3.00

    # 2. Query single run usage
    res_single = client.get(f"/api/v1/billing/usage/{run.id}", headers=headers)
    assert res_single.status_code == 200
    assert res_single.json()["pipeline_run_id"] == run.id

    # 3. Post override
    res_override = client.post(
        f"/api/v1/billing/usage/{ledger.id}/override",
        json={"is_billable": False, "reason": "Test waiver via API"},
        headers=headers
    )
    assert res_override.status_code == 200
    override_data = res_override.json()
    assert override_data["is_billable"] is False
    assert override_data["non_billable_reason"] == "Test waiver via API"
    assert override_data["calculated_charge"] == 0.0
