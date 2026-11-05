import pytest
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.models.trigger import Trigger, TriggerRun
from backend.app.schemas.trigger import (
    TriggerCreate,
    TriggerUpdate,
    PipelineTarget,
    ScheduleConfig,
    TumblingWindowConfig,
    StorageEventConfig,
    PipelineDependencyConfig
)
from backend.app.services.trigger_service import TriggerService
from backend.app.main import app
from backend.app.core.security import encrypt_secret
from backend.app.connectors.storage.models import StorageItem
from backend.app.connectors.storage.local import LocalStorageConnector


@pytest.fixture(scope="module")
def db_session():
    """Provides test database session with clean metadata."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def test_setup(db_session: Session):
    """Initializes workspace, project, user, and test pipelines."""
    # Ensure test user
    user = db_session.query(User).filter(User.email == "trigger_admin@dataforge.test").first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email="trigger_admin@dataforge.test",
            hashed_password="testpassword",
            full_name="Trigger Test Admin",
            is_active=True
        )
        db_session.add(user)

    # Ensure test workspace & project
    ws = db_session.query(Workspace).first()
    if not ws:
        ws = Workspace(id=str(uuid.uuid4()), name="Trigger Workspace", owner_id=user.id)
        db_session.add(ws)
    proj = db_session.query(Project).first()
    if not proj:
        proj = Project(id=str(uuid.uuid4()), name="Trigger Project", workspace_id=ws.id)
        db_session.add(proj)
    db_session.commit()

    # Create Pipelines A, B, C for trigger testing
    pipe_a = Pipeline(id=str(uuid.uuid4()), project_id=proj.id, name="Pipeline_Alpha", definition_json={"activities": []})
    pipe_b = Pipeline(id=str(uuid.uuid4()), project_id=proj.id, name="Pipeline_Beta", definition_json={"activities": []})
    pipe_c = Pipeline(id=str(uuid.uuid4()), project_id=proj.id, name="Pipeline_Gamma", definition_json={"activities": []})
    db_session.add_all([pipe_a, pipe_b, pipe_c])

    # Storage connection for storage event tests
    conn = Connection(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Test Storage Conn",
        connector_type="local_storage",
        config_encrypted=encrypt_secret({"base_path": "/tmp/dataforge_test_storage"})
    )
    db_session.add(conn)
    db_session.commit()

    return {
        "user": user,
        "project": proj,
        "pipe_a": pipe_a,
        "pipe_b": pipe_b,
        "pipe_c": pipe_c,
        "storage_conn": conn
    }


def test_schedule_trigger_with_timezone_and_bounds(db_session: Session, test_setup):
    """Verifies schedule trigger with timezone awareness, frequency, and start/end boundaries."""
    pipe_a = test_setup["pipe_a"]

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=1)
    end_time = now + timedelta(days=2)

    trigger_in = TriggerCreate(
        name="Daily_NY_Schedule",
        trigger_type="schedule",
        pipeline_id=pipe_a.id,
        cron_expression="0 9 * * *",  # 9 AM every day
        schedule_config=ScheduleConfig(
            timezone="America/New_York",
            frequency="Day",
            interval=1,
            start_time=start_time,
            end_time=end_time
        ),
        is_active=True
    )

    trigger = TriggerService.create_trigger(db_session, trigger_in)
    assert trigger.id is not None
    assert trigger.next_fire_time is not None

    # Test end_time expiry
    past_end_time = now - timedelta(hours=2)
    next_fire = TriggerService.calculate_next_schedule_fire(
        "schedule",
        "0 9 * * *",
        {"timezone": "America/New_York", "start_time": start_time.isoformat(), "end_time": past_end_time.isoformat()},
        now
    )
    assert next_fire is None


def test_tumbling_window_trigger_slicing_and_concurrency(db_session: Session, test_setup):
    """Verifies tumbling window slice calculation, delay handling, and prior window dependency."""
    pipe_a = test_setup["pipe_a"]
    now = datetime.now(timezone.utc)
    start_window = now - timedelta(hours=2)

    tumb_cfg = TumblingWindowConfig(
        frequency="Hour",
        interval=1,
        start_time=start_window,
        delay_minutes=5,
        max_concurrency=1,
        depends_on_prior_window=True
    )

    trigger_in = TriggerCreate(
        name="Hourly_Tumbling_Window",
        trigger_type="tumbling_window",
        pipeline_id=pipe_a.id,
        tumbling_window_config=tumb_cfg,
        is_active=True
    )

    trigger = TriggerService.create_trigger(db_session, trigger_in)
    assert trigger.id is not None
    assert "current_window_start" in trigger.window_state

    # Evaluate tumbling window trigger
    tr_run = TriggerService.evaluate_tumbling_window_trigger(db_session, trigger, now=now)
    assert tr_run is not None
    assert tr_run.event_payload is not None
    assert "windowStartTime" in tr_run.event_payload
    assert "windowEndTime" in tr_run.event_payload

    # Window state should have advanced
    db_session.refresh(trigger)
    assert len(trigger.window_state.get("processed_windows", [])) == 1


def test_storage_event_trigger_detection_and_deduplication(db_session: Session, test_setup):
    """Verifies storage event trigger detecting new files and deduplicating seen ETags."""
    pipe_a = test_setup["pipe_a"]
    storage_conn = test_setup["storage_conn"]

    stor_cfg = StorageEventConfig(
        connection_id=storage_conn.id,
        container="test-landing",
        prefix="incoming/",
        suffix=".csv",
        ignore_empty_blobs=True
    )

    trigger_in = TriggerCreate(
        name="Blob_Arrival_Trigger",
        trigger_type="storage_event",
        pipeline_id=pipe_a.id,
        storage_event_config=stor_cfg,
        is_active=True
    )

    trigger = TriggerService.create_trigger(db_session, trigger_in)

    mock_files = [
        StorageItem(
            path="incoming/sales_20261105.csv",
            name="sales_20261105.csv",
            size_in_bytes=4096,
            last_modified=datetime.now(timezone.utc),
            etag="etag-abc-123"
        ),
        StorageItem(
            path="incoming/notes.txt",  # does not match .csv suffix
            name="notes.txt",
            size_in_bytes=100,
            last_modified=datetime.now(timezone.utc),
            etag="etag-txt-456"
        )
    ]

    with patch.object(LocalStorageConnector, "list_files", return_value=mock_files):
        dispatched_1 = TriggerService.evaluate_storage_event_trigger(db_session, trigger)
        assert len(dispatched_1) == 1
        assert dispatched_1[0].event_payload["fileName"] == "sales_20261105.csv"

        # Second evaluation with the exact same files should produce 0 dispatches due to deduplication
        dispatched_2 = TriggerService.evaluate_storage_event_trigger(db_session, trigger)
        assert len(dispatched_2) == 0

        # Adding a new file should trigger 1 new dispatch
        mock_files.append(
            StorageItem(
                path="incoming/customers_20261105.csv",
                name="customers_20261105.csv",
                size_in_bytes=8192,
                last_modified=datetime.now(timezone.utc),
                etag="etag-cust-789"
            )
        )
        dispatched_3 = TriggerService.evaluate_storage_event_trigger(db_session, trigger)
        assert len(dispatched_3) == 1
        assert dispatched_3[0].event_payload["fileName"] == "customers_20261105.csv"


def test_pipeline_dependency_and_circular_prevention(db_session: Session, test_setup):
    """Verifies pipeline dependency triggering and circular dependency rejection."""
    pipe_a = test_setup["pipe_a"]
    pipe_b = test_setup["pipe_b"]
    pipe_c = test_setup["pipe_c"]

    # 1. Trigger 1: Pipe A -> Pipe B
    t1 = TriggerService.create_trigger(db_session, TriggerCreate(
        name="Dep_A_to_B",
        trigger_type="pipeline_dependency",
        pipeline_id=pipe_b.id,
        pipeline_dependency_config=PipelineDependencyConfig(
            upstream_pipeline_id=pipe_a.id,
            fire_on_status=["Succeeded"]
        ),
        is_active=True
    ))

    # 2. Trigger 2: Pipe B -> Pipe C
    t2 = TriggerService.create_trigger(db_session, TriggerCreate(
        name="Dep_B_to_C",
        trigger_type="pipeline_dependency",
        pipeline_id=pipe_c.id,
        pipeline_dependency_config=PipelineDependencyConfig(
            upstream_pipeline_id=pipe_b.id,
            fire_on_status=["Succeeded"]
        ),
        is_active=True
    ))

    # 3. Trigger 3: Pipe C -> Pipe A (Creates cycle A -> B -> C -> A)
    with pytest.raises(ValueError, match="Circular pipeline trigger dependency detected"):
        TriggerService.create_trigger(db_session, TriggerCreate(
            name="Dep_C_to_A_Circular",
            trigger_type="pipeline_dependency",
            pipeline_id=pipe_a.id,
            pipeline_dependency_config=PipelineDependencyConfig(
                upstream_pipeline_id=pipe_c.id,
                fire_on_status=["Succeeded"]
            ),
            is_active=True
        ))

    # 4. Trigger legitimate dependency firing when Pipe A finishes with Succeeded
    run_a = PipelineRun(
        pipeline_id=pipe_a.id,
        run_type="Manual",
        status="Succeeded",
        parameters={"source_batch": "1001"},
        started_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        ended_at=datetime.now(timezone.utc) + timedelta(seconds=2)
    )
    db_session.add(run_a)
    db_session.commit()

    dispatched = TriggerService.evaluate_pipeline_dependency_trigger(db_session, t1)
    assert len(dispatched) == 1
    assert dispatched[0].event_payload["upstreamPipelineId"] == pipe_a.id
    assert dispatched[0].event_payload["upstreamStatus"] == "Succeeded"


def test_multi_pipeline_trigger_dispatch(db_session: Session, test_setup):
    """Verifies that a single trigger can dispatch multiple target pipelines with distinct parameters."""
    pipe_a = test_setup["pipe_a"]
    pipe_b = test_setup["pipe_b"]

    trigger_in = TriggerCreate(
        name="Multi_Pipeline_Trigger",
        trigger_type="manual",
        pipelines_to_run=[
            PipelineTarget(pipeline_id=pipe_a.id, pipeline_name=pipe_a.name, parameters={"mode": "extract"}),
            PipelineTarget(pipeline_id=pipe_b.id, pipeline_name=pipe_b.name, parameters={"mode": "transform"})
        ],
        parameters={"common_batch_id": "BATCH_99"}
    )

    trigger = TriggerService.create_trigger(db_session, trigger_in)
    assert len(trigger.pipelines_to_run) == 2

    # Fire trigger
    tr_run = TriggerService.fire_trigger_now(db_session, trigger)
    assert tr_run.run_status == "Succeeded"
    assert len(tr_run.triggered_pipeline_runs) == 2

    run_pipe_ids = [r["pipeline_id"] for r in tr_run.triggered_pipeline_runs]
    assert pipe_a.id in run_pipe_ids
    assert pipe_b.id in run_pipe_ids


def test_trigger_rest_api_lifecycle(test_setup):
    """Verifies FastAPI REST endpoints: CRUD, activate/deactivate, fire-now, runs history."""
    client = TestClient(app)
    pipe_a = test_setup["pipe_a"]

    # 1. Create trigger via REST API
    res = client.post("/api/v1/triggers", json={
        "name": "API_Scheduled_Trigger",
        "trigger_type": "schedule",
        "pipeline_id": pipe_a.id,
        "cron_expression": "*/30 * * * *",
        "is_active": True,
        "parameters": {"env": "test"}
    })
    assert res.status_code == 200, res.text
    tr_data = res.json()
    trigger_id = tr_data["id"]
    assert tr_data["name"] == "API_Scheduled_Trigger"
    assert tr_data["is_active"] is True

    # 2. Get trigger details
    res = client.get(f"/api/v1/triggers/{trigger_id}")
    assert res.status_code == 200
    assert res.json()["id"] == trigger_id

    # 3. Deactivate trigger
    res = client.post(f"/api/v1/triggers/{trigger_id}/deactivate")
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    # 4. Activate trigger
    res = client.post(f"/api/v1/triggers/{trigger_id}/activate")
    assert res.status_code == 200
    assert res.json()["is_active"] is True

    # 5. Fire trigger now
    res = client.post(f"/api/v1/triggers/{trigger_id}/fire-now", json={"override_key": "val123"})
    assert res.status_code == 200
    fire_data = res.json()
    assert "trigger_run_id" in fire_data
    assert "run_id" in fire_data

    # 6. Query trigger run history
    res = client.get(f"/api/v1/triggers/{trigger_id}/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) >= 1
    assert runs[0]["trigger_id"] == trigger_id

    # 7. Query all runs endpoint
    res = client.get("/api/v1/triggers/runs/all")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 8. Delete trigger
    res = client.delete(f"/api/v1/triggers/{trigger_id}")
    assert res.status_code == 200
    assert res.json()["message"] == "Trigger deleted successfully"


def test_cycle_validation_endpoint(test_setup):
    """Verifies the REST API dependency cycle validation preflight check."""
    client = TestClient(app)
    pipe_a = test_setup["pipe_a"]
    pipe_b = test_setup["pipe_b"]

    # Valid dependency (no cycle)
    res = client.post("/api/v1/triggers/validate-dependency-cycle", json={
        "upstream_pipeline_id": pipe_a.id,
        "downstream_pipeline_ids": [pipe_b.id]
    })
    assert res.status_code == 200
    assert res.json()["valid"] is True

    # Cycle check with identical source & destination
    res = client.post("/api/v1/triggers/validate-dependency-cycle", json={
        "upstream_pipeline_id": pipe_a.id,
        "downstream_pipeline_ids": [pipe_a.id]
    })
    assert res.status_code == 200
    assert res.json()["valid"] is False
    assert "Circular pipeline trigger dependency detected" in res.json()["error"]

