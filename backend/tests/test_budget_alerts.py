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
    BudgetConfiguration,
    BudgetAlertRecord,
    PipelineUsageLedger
)
from backend.app.services.billing_service import BillingService
from backend.app.services.budget_service import BudgetService
from backend.app.schemas.billing import BudgetConfigurationCreate, BudgetConfigurationUpdate
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
            email="budget_admin@dataforge.test",
            full_name="Budget Admin",
            hashed_password="hashed_admin_pass",
            role="Admin"
        )
        db.add(admin)
        db.commit()
    return create_access_token({"sub": admin.id, "role": admin.role})


@pytest.fixture
def budget_setup(db: Session):
    """Provisions a test tenant, workspace, project, and pipeline for budget testing."""
    BillingService.seed_default_plans(db)

    tenant = Tenant(
        name=f"Budget Tenant {uuid.uuid4().hex[:6]}",
        billing_email="finance@budgettest.com",
        currency="INR",
        country="IN"
    )
    db.add(tenant)
    db.flush()

    workspace = Workspace(
        name=f"Budget WS {uuid.uuid4().hex[:6]}",
        tenant_id=tenant.id
    )
    db.add(workspace)
    db.flush()

    project = Project(
        name=f"Budget Project {uuid.uuid4().hex[:6]}",
        workspace_id=workspace.id
    )
    db.add(project)
    db.flush()

    pipeline = Pipeline(
        name="Budget Pipeline",
        project_id=project.id,
        definition_json={"activities": [{"name": "act1"}]}
    )
    db.add(pipeline)
    db.commit()

    return {
        "tenant": tenant,
        "workspace": workspace,
        "project": project,
        "pipeline": pipeline
    }


def test_create_and_update_budget_configuration(db: Session, budget_setup: dict):
    """
    Verifies creating and modifying spending and run limits on a budget configuration.
    """
    tenant = budget_setup["tenant"]
    workspace = budget_setup["workspace"]

    budget_in = BudgetConfigurationCreate(
        name="Production Ingestion Budget",
        period_type="Monthly",
        monthly_limit_amount=25000.0,
        monthly_run_limit=10000,
        enforce_hard_limit=True,
        alert_recipients=[{"channel": "email", "target": "alerts@client.com"}],
        threshold_percents=[50, 75, 90, 100],
        workspace_id=workspace.id
    )

    budget = BudgetService.create_budget(db, tenant.id, budget_in)
    assert budget.id is not None
    assert budget.name == "Production Ingestion Budget"
    assert float(budget.monthly_limit_amount) == 25000.0
    assert budget.monthly_run_limit == 10000
    assert budget.enforce_hard_limit is True

    # Update budget
    updated = BudgetService.update_budget(
        db,
        budget.id,
        BudgetConfigurationUpdate(monthly_limit_amount=30000.0, enforce_hard_limit=False)
    )
    assert float(updated.monthly_limit_amount) == 30000.0
    assert updated.enforce_hard_limit is False


def test_budget_utilization_and_status_calculation(db: Session, budget_setup: dict):
    """
    Verifies that real-time spend and run count utilization are calculated correctly.
    """
    tenant = budget_setup["tenant"]
    workspace = budget_setup["workspace"]
    project = budget_setup["project"]
    pipeline = budget_setup["pipeline"]

    period_key = "2026-03"

    budget = BudgetService.create_budget(
        db,
        tenant.id,
        BudgetConfigurationCreate(
            name="Q1 Ingestion Budget",
            monthly_limit_amount=10000.0,
            monthly_run_limit=1000,
            workspace_id=workspace.id
        )
    )

    # Seed 50 runs totaling ₹2,500 spend (25% spend, 5% runs)
    for i in range(50):
        pr = PipelineRun(
            pipeline_id=pipeline.id,
            run_type="Manual",
            status="Succeeded",
            started_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            ended_at=datetime(2026, 3, 10, 0, 5, tzinfo=timezone.utc),
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
            started_at=datetime(2026, 3, 10, tzinfo=timezone.utc),
            execution_status="Succeeded",
            billing_period_key=period_key,
            is_billable=True,
            calculated_charge=50.00
        )
        db.add(ledger)
    db.commit()

    status = BudgetService.get_budget_status(db, budget.id, period_key)
    assert status.current_runs == 50
    assert status.current_spend == 2500.00
    assert status.spend_utilization_pct == 25.0
    assert status.run_utilization_pct == 5.0
    assert status.is_hard_limit_breached is False


def test_budget_threshold_alert_dispatch_and_deduplication(db: Session, budget_setup: dict):
    """
    Verifies that:
    1. Reaching 80% consumption triggers 50% and 75% threshold alerts.
    2. Repeated evaluation in the same period deduplicates alerts to avoid spam.
    """
    tenant = budget_setup["tenant"]
    workspace = budget_setup["workspace"]
    project = budget_setup["project"]
    pipeline = budget_setup["pipeline"]

    period_key = "2026-02"

    budget = BudgetService.create_budget(
        db,
        tenant.id,
        BudgetConfigurationCreate(
            name="Threshold Test Budget",
            monthly_limit_amount=10000.0,
            monthly_run_limit=100,
            threshold_percents=[50, 75, 90, 100],
            alert_recipients=[{"channel": "email", "target": "finops@company.com"}],
            workspace_id=workspace.id
        )
    )

    # Seed 80 runs totaling ₹8,000 (80% spend, 80% runs)
    for i in range(80):
        pr = PipelineRun(
            pipeline_id=pipeline.id,
            run_type="Manual",
            status="Succeeded",
            started_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
            ended_at=datetime(2026, 2, 10, 0, 5, tzinfo=timezone.utc),
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
            started_at=datetime(2026, 2, 10, tzinfo=timezone.utc),
            execution_status="Succeeded",
            billing_period_key=period_key,
            is_billable=True,
            calculated_charge=100.00
        )
        db.add(ledger)
    db.commit()

    # Evaluation 1: Should trigger 50% and 75% thresholds
    eval_res1 = BudgetService.evaluate_budgets_for_tenant(db, tenant.id, period_key)
    assert eval_res1.triggered_alerts_count == 2
    triggered_pcts = [a.threshold_percent for a in eval_res1.alerts_dispatched]
    assert 50 in triggered_pcts
    assert 75 in triggered_pcts
    assert 90 not in triggered_pcts

    # Evaluation 2: Repeated evaluation should NOT dispatch duplicate alerts
    eval_res2 = BudgetService.evaluate_budgets_for_tenant(db, tenant.id, period_key)
    assert eval_res2.triggered_alerts_count == 0


def test_hard_limit_enforcement_blocks_execution(db: Session, budget_setup: dict):
    """
    Verifies that:
    1. enforce_hard_limit=True blocks execution when 100% threshold breached.
    2. enforce_hard_limit=False permits execution even if 100% exceeded.
    """
    tenant = budget_setup["tenant"]
    workspace = budget_setup["workspace"]
    project = budget_setup["project"]
    pipeline = budget_setup["pipeline"]

    now = datetime.now(timezone.utc)
    current_period = now.strftime("%Y-%m")

    # Budget with hard limit = True, limit = ₹1,000
    budget = BudgetService.create_budget(
        db,
        tenant.id,
        BudgetConfigurationCreate(
            name="Strict Cap Budget",
            monthly_limit_amount=1000.0,
            enforce_hard_limit=True,
            workspace_id=workspace.id
        )
    )

    # Before exceeding: allowed
    allowed, _ = BudgetService.check_execution_allowed(db, workspace.id)
    assert allowed is True

    # Seed ₹1,200 spend (120% consumption)
    pr = PipelineRun(
        pipeline_id=pipeline.id,
        run_type="Manual",
        status="Succeeded",
        started_at=now,
        ended_at=now,
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
        started_at=now,
        execution_status="Succeeded",
        billing_period_key=current_period,
        is_billable=True,
        calculated_charge=1200.00
    )
    db.add(ledger)
    db.commit()

    # Now hard limit breached: blocked
    allowed, block_reason = BudgetService.check_execution_allowed(db, workspace.id)
    assert allowed is False
    assert "Execution blocked" in block_reason

    # Toggle to warn-only (enforce_hard_limit=False): should allow
    BudgetService.update_budget(db, budget.id, BudgetConfigurationUpdate(enforce_hard_limit=False))
    allowed, _ = BudgetService.check_execution_allowed(db, workspace.id)
    assert allowed is True


def test_api_budget_management_and_evaluate(client: TestClient, admin_token: str, budget_setup: dict):
    """
    Tests REST APIs:
    - POST /api/v1/billing/budgets
    - GET /api/v1/billing/budgets
    - GET /api/v1/billing/budgets/{id}
    - PUT /api/v1/billing/budgets/{id}
    - POST /api/v1/billing/budgets/evaluate
    - DELETE /api/v1/billing/budgets/{id}
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    tenant = budget_setup["tenant"]
    workspace = budget_setup["workspace"]

    # 1. Create Budget via API
    create_payload = {
        "name": "API Analytics Budget",
        "period_type": "Monthly",
        "monthly_limit_amount": 50000.0,
        "monthly_run_limit": 25000,
        "enforce_hard_limit": False,
        "alert_recipients": [{"channel": "email", "target": "lead@client.com"}],
        "threshold_percents": [50, 75, 90, 100],
        "workspace_id": workspace.id
    }
    create_resp = client.post(
        f"/api/v1/billing/budgets?workspace_id={workspace.id}",
        headers=headers,
        json=create_payload
    )
    assert create_resp.status_code == 200, create_resp.text
    budget_data = create_resp.json()
    b_id = budget_data["id"]
    assert budget_data["name"] == "API Analytics Budget"
    assert budget_data["monthly_limit_amount"] == 50000.0

    # 2. List Budgets
    list_resp = client.get(f"/api/v1/billing/budgets?workspace_id={workspace.id}", headers=headers)
    assert list_resp.status_code == 200
    budgets = list_resp.json()
    assert any(b["id"] == b_id for b in budgets)

    # 3. Get single budget status
    get_resp = client.get(f"/api/v1/billing/budgets/{b_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == b_id

    # 4. Update budget
    put_resp = client.put(
        f"/api/v1/billing/budgets/{b_id}",
        headers=headers,
        json={"monthly_limit_amount": 60000.0, "enforce_hard_limit": True}
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["monthly_limit_amount"] == 60000.0
    assert put_resp.json()["enforce_hard_limit"] is True

    # 5. Evaluate budgets
    eval_resp = client.post(
        f"/api/v1/billing/budgets/evaluate?workspace_id={workspace.id}",
        headers=headers
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert "evaluated_budgets" in eval_data

    # 6. Delete budget
    del_resp = client.delete(f"/api/v1/billing/budgets/{b_id}", headers=headers)
    assert del_resp.status_code == 200

    # Verify deleted
    get_del = client.get(f"/api/v1/billing/budgets/{b_id}", headers=headers)
    assert get_del.status_code == 404
