import pytest
import uuid
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.main import app
from backend.app.core.database import SessionLocal, engine
from backend.app.models.dataset import Dataset, DatasetVersion
from backend.app.models.connection import Connection
from backend.app.models.workspace import Project
from backend.app.models.user import User
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.schemas.dataset import DatasetCreate, DatasetUpdate
from backend.app.services.dataset_service import DatasetService
from backend.app.core.security import encrypt_secret, create_access_token
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.copy_data import CopyDataActivity


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_sqlite_conn(db_session: Session):
    """Creates a temporary SQLite file with a sample table and DataForge Connection."""
    temp_dir = tempfile.mkdtemp(prefix="df_ds_test_")
    db_path = os.path.join(temp_dir, "test_dataset_store.db")
    
    # Initialize table with sample data
    import sqlite3
    s_conn = sqlite3.connect(db_path)
    cur = s_conn.cursor()
    cur.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, email TEXT, score REAL);")
    cur.execute("INSERT INTO customers VALUES (1, 'Alice Corp', 'alice@corp.com', 95.5);")
    cur.execute("INSERT INTO customers VALUES (2, 'Bob LLC', 'bob@llc.com', 82.0);")
    cur.execute("INSERT INTO customers VALUES (3, 'Charlie Inc', 'charlie@inc.com', 90.1);")
    s_conn.commit()
    s_conn.close()

    proj = db_session.query(Project).first()
    conn = Connection(
        project_id=proj.id if proj else "default-project",
        name=f"sqlite-conn-{uuid.uuid4().hex[:6]}",
        connector_type="sqlite",
        config_encrypted=encrypt_secret({"database": db_path}),
        status="Active"
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    
    return conn, db_path


def test_dataset_crud_and_versioning(db_session: Session, test_sqlite_conn):
    """Test creating, versioning, updating, and deleting reusable datasets."""
    conn, _ = test_sqlite_conn

    # 1. Create dataset
    ds_in = DatasetCreate(
        name=f"ds-customers-{uuid.uuid4().hex[:6]}",
        dataset_type="RelationalTable",
        connection_id=conn.id,
        description="Master customer dataset",
        location_config={"table": "customers"},
        format_settings={},
        parameters={"env": {"type": "String", "default": "prod"}},
        schema_definition=[
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "name", "type": "TEXT", "nullable": True}
        ],
        auto_discover_schema=False
    )
    dataset = DatasetService.create_dataset(db_session, ds_in)
    assert dataset.id is not None
    assert dataset.current_version == 1
    assert dataset.schema_status == "Current"

    # Verify Version 1 snapshot exists
    v1 = db_session.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset.id,
        DatasetVersion.version_number == 1
    ).first()
    assert v1 is not None
    assert len(v1.schema_snapshot) == 2

    # 2. Update schema definition -> triggers Version 2 snapshot
    updated_schema = [
        {"name": "id", "type": "INTEGER", "nullable": False},
        {"name": "name", "type": "TEXT", "nullable": True},
        {"name": "email", "type": "TEXT", "nullable": True}
    ]
    ds_up = DatasetUpdate(schema_definition=updated_schema)
    updated_ds = DatasetService.update_dataset(db_session, dataset.id, ds_up)
    assert updated_ds.current_version == 2
    assert len(updated_ds.schema_definition) == 3

    v2 = db_session.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset.id,
        DatasetVersion.version_number == 2
    ).first()
    assert v2 is not None
    assert len(v2.schema_snapshot) == 3

    # 3. List datasets
    all_ds = DatasetService.list_datasets(db_session, connection_id=conn.id)
    assert any(d.id == dataset.id for d in all_ds)

    # 4. Delete dataset
    DatasetService.delete_dataset(db_session, dataset.id)
    assert db_session.query(Dataset).filter(Dataset.id == dataset.id).first() is None


def test_schema_inference_and_auto_discovery(db_session: Session, test_sqlite_conn):
    """Test automatic schema discovery from live physical database connection."""
    conn, _ = test_sqlite_conn

    ds_in = DatasetCreate(
        name=f"ds-auto-discover-{uuid.uuid4().hex[:6]}",
        dataset_type="RelationalTable",
        connection_id=conn.id,
        location_config={"table": "customers"},
        auto_discover_schema=True  # Auto discover on creation
    )
    dataset = DatasetService.create_dataset(db_session, ds_in)
    assert dataset.id is not None
    assert len(dataset.schema_definition) >= 4  # id, name, email, score

    col_names = [c["name"].lower() for c in dataset.schema_definition]
    assert "id" in col_names
    assert "name" in col_names
    assert "email" in col_names
    assert "score" in col_names


def test_schema_drift_detection_and_sync(db_session: Session, test_sqlite_conn):
    """Test detecting added/removed columns and synchronizing schema snapshots."""
    conn, db_path = test_sqlite_conn

    # 1. Create dataset with initial 3 columns
    ds_in = DatasetCreate(
        name=f"ds-drift-{uuid.uuid4().hex[:6]}",
        dataset_type="RelationalTable",
        connection_id=conn.id,
        location_config={"table": "customers"},
        schema_definition=[
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "name", "type": "TEXT", "nullable": True}
        ],
        auto_discover_schema=False
    )
    dataset = DatasetService.create_dataset(db_session, ds_in)

    # 2. Check drift: the physical table has 4 columns (email and score were added)
    drift_report = DatasetService.detect_schema_drift(db_session, dataset.id)
    assert drift_report.has_drift is True
    assert drift_report.status == "DriftDetected"
    added_col_names = [c["name"].lower() for c in drift_report.added_columns]
    assert "email" in added_col_names or "score" in added_col_names

    db_session.refresh(dataset)
    assert dataset.schema_status == "DriftDetected"

    # 3. Synchronize schema to accept physical changes
    synced_ds, new_version = DatasetService.sync_schema(db_session, dataset.id, "Accepted new columns")
    assert synced_ds.schema_status == "Current"
    assert synced_ds.current_version == 2
    assert new_version.version_number == 2
    assert len(synced_ds.schema_definition) >= 4

    # 4. Re-check drift -> should now report Current with no drift
    drift_after = DatasetService.detect_schema_drift(db_session, dataset.id)
    assert drift_after.has_drift is False
    assert drift_after.status == "Current"


def test_dataset_bounded_preview(db_session: Session, test_sqlite_conn):
    """Test previewing dataset records with bounded memory safety."""
    conn, _ = test_sqlite_conn

    dataset = DatasetService.create_dataset(
        db_session,
        DatasetCreate(
            name=f"ds-prev-{uuid.uuid4().hex[:6]}",
            dataset_type="RelationalTable",
            connection_id=conn.id,
            location_config={"table": "customers"}
        )
    )

    preview = DatasetService.preview_data(db_session, dataset.id, row_limit=2)
    assert preview.total_rows_previewed == 2
    assert len(preview.rows) == 2
    assert "name" in preview.columns
    assert preview.rows[0]["name"] == "Alice Corp"
    assert preview.bytes_sampled > 0
    assert preview.duration_ms >= 0


def test_dataset_usages(db_session: Session, test_sqlite_conn):
    """Test tracking which pipelines and activities reference a dataset."""
    conn, _ = test_sqlite_conn
    proj = db_session.query(Project).first()

    dataset = DatasetService.create_dataset(
        db_session,
        DatasetCreate(
            name=f"ds-usage-{uuid.uuid4().hex[:6]}",
            dataset_type="RelationalTable",
            connection_id=conn.id,
            location_config={"table": "customers"}
        )
    )

    # Create pipeline referencing this dataset as source
    pipeline = Pipeline(
        project_id=proj.id if proj else None,
        name=f"pipe-ds-usage-{uuid.uuid4().hex[:6]}",
        definition_json={
            "activities": [
                {
                    "id": "act_copy_1",
                    "name": "CopyCustomers",
                    "type": "CopyData",
                    "config": {
                        "source": {"dataset_id": dataset.id},
                        "sink": {"connection_id": conn.id, "table_name": "target_tbl"}
                    }
                }
            ]
        }
    )
    db_session.add(pipeline)
    db_session.commit()

    usages = DatasetService.get_dataset_usages(db_session, dataset.id)
    assert usages.pipeline_count >= 1
    assert any(p["pipeline_id"] == pipeline.id for p in usages.pipelines)
    assert usages.pipelines[0]["activities"][0]["activity_name"] == "CopyCustomers"
    assert usages.pipelines[0]["activities"][0]["role"] == "Source"


def test_copy_data_with_dataset_references(db_session: Session, test_sqlite_conn):
    """Test CopyDataActivity executing end-to-end with reusable dataset references."""
    conn, db_path = test_sqlite_conn

    # Source dataset referencing customers
    src_dataset = DatasetService.create_dataset(
        db_session,
        DatasetCreate(
            name=f"ds-src-{uuid.uuid4().hex[:6]}",
            dataset_type="RelationalTable",
            connection_id=conn.id,
            location_config={"table": "customers"}
        )
    )

    # Sink dataset referencing customers_archive
    sink_dataset = DatasetService.create_dataset(
        db_session,
        DatasetCreate(
            name=f"ds-dst-{uuid.uuid4().hex[:6]}",
            dataset_type="RelationalTable",
            connection_id=conn.id,
            location_config={"table": "customers_archive"}
        )
    )

    # Create target table in SQLite
    import sqlite3
    s_conn = sqlite3.connect(db_path)
    s_conn.execute("CREATE TABLE IF NOT EXISTS customers_archive (id INTEGER PRIMARY KEY, name TEXT, email TEXT, score REAL);")
    s_conn.commit()
    s_conn.close()

    # Activity config referencing both datasets
    act_config = {
        "source": {"dataset_id": src_dataset.id},
        "destination": {"dataset_id": sink_dataset.id}
    }

    ctx = ActivityExecutionContext(
        pipeline_run_id=f"run-{uuid.uuid4().hex[:6]}",
        activity_id="act_copy_dataset",
        activity_name="CopyCustomerDataset",
        activity_type="CopyData",
        config=act_config,
        pipeline_parameters={},
        pipeline_variables={},
        activity_outputs={}
    )

    activity = CopyDataActivity(ctx, db_session)
    res = activity.execute()

    assert res.status == "Succeeded"
    assert res.rows_read == 3
    assert res.rows_written == 3

    # Verify rows in target sqlite table
    s_conn = sqlite3.connect(db_path)
    cur = s_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM customers_archive;")
    count = cur.fetchone()[0]
    s_conn.close()
    assert count == 3


def test_dataset_rest_api_endpoints(client: TestClient, db_session: Session, test_sqlite_conn):
    """Test FastAPI REST endpoints for dataset management."""
    conn, _ = test_sqlite_conn
    user = db_session.query(User).first()
    token = create_access_token({"sub": user.id if user else "admin", "role": "Admin"})
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create dataset via API
    ds_name = f"api-ds-{uuid.uuid4().hex[:6]}"
    create_resp = client.post(
        "/api/v1/datasets",
        json={
            "name": ds_name,
            "dataset_type": "RelationalTable",
            "connection_id": conn.id,
            "location_config": {"table": "customers"},
            "auto_discover_schema": True
        },
        headers=auth_headers
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    ds_id = created["id"]
    assert created["name"] == ds_name
    assert len(created["schema_definition"]) >= 4

    # 2. Get dataset by ID
    get_resp = client.get(f"/api/v1/datasets/{ds_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == ds_id

    # 3. List datasets
    list_resp = client.get("/api/v1/datasets", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(d["id"] == ds_id for d in list_resp.json())

    # 4. Preview data
    prev_resp = client.post(
        f"/api/v1/datasets/{ds_id}/preview",
        json={"row_limit": 2},
        headers=auth_headers
    )
    assert prev_resp.status_code == 200
    prev_data = prev_resp.json()
    assert prev_data["total_rows_previewed"] == 2
    assert len(prev_data["rows"]) == 2

    # 5. Detect drift
    drift_resp = client.post(f"/api/v1/datasets/{ds_id}/detect-drift", headers=auth_headers)
    assert drift_resp.status_code == 200
    assert "has_drift" in drift_resp.json()

    # 6. Get versions
    versions_resp = client.get(f"/api/v1/datasets/{ds_id}/versions", headers=auth_headers)
    assert versions_resp.status_code == 200
    assert len(versions_resp.json()) >= 1

    # 7. Get usages
    usages_resp = client.get(f"/api/v1/datasets/{ds_id}/usages", headers=auth_headers)
    assert usages_resp.status_code == 200
    assert "pipeline_count" in usages_resp.json()

    # 8. Delete dataset
    del_resp = client.delete(f"/api/v1/datasets/{ds_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"
