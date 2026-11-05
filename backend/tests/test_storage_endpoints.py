import pytest
import os
import tempfile
import shutil
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import SessionLocal, get_db
from backend.app.models.user import User
from backend.app.models.workspace import Project
from backend.app.models.connection import Connection
from backend.app.core.security import encrypt_secret, create_access_token

from backend.app.core.config import settings

client = TestClient(app)
api_prefix = settings.API_V1_STR


@pytest.fixture(scope="module")
def auth_header_and_conn():
    temp_dir = tempfile.mkdtemp(prefix="dataforge_storage_test_")
    # Create test container folder and subfiles
    os.makedirs(os.path.join(temp_dir, "raw-data", "nested"), exist_ok=True)
    with open(os.path.join(temp_dir, "raw-data", "sample.csv"), "w") as f:
        f.write("id,name\n1,Alice\n2,Bob\n")
    with open(os.path.join(temp_dir, "raw-data", "nested", "inner.json"), "w") as f:
        f.write('{"key": "value"}')

    db = SessionLocal()
    # Find or create a user
    user = db.query(User).first()
    if not user:
        user = User(
            email="test_storage_user@example.com",
            hashed_password="dummy_password_hash",
            full_name="Storage Test User",
            role="Admin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    proj = db.query(Project).first()
    if not proj:
        proj = Project(name="Default Storage Project", description="Test Project")
        db.add(proj)
        db.commit()
        db.refresh(proj)

    token = create_access_token({"sub": user.id, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    # Create LocalStorage connection
    conn = Connection(
        project_id=proj.id,
        name="Test Local Storage Connection",
        connector_type="local_storage",
        description="For storage endpoint tests",
        config_encrypted=encrypt_secret({"base_path": temp_dir})
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    conn_id = conn.id
    db.close()

    yield headers, conn_id, temp_dir

    # Cleanup
    db = SessionLocal()
    c = db.query(Connection).filter(Connection.id == conn_id).first()
    if c:
        db.delete(c)
        db.commit()
    db.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_list_storage_containers(auth_header_and_conn):
    headers, conn_id, _ = auth_header_and_conn
    res = client.get(f"{api_prefix}/connections/{conn_id}/storage/containers", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["is_storage"] is True
    assert "raw-data" in data["containers"]


def test_list_storage_items(auth_header_and_conn):
    headers, conn_id, _ = auth_header_and_conn
    res = client.get(
        f"{api_prefix}/connections/{conn_id}/storage/items?container=raw-data",
        headers=headers
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["container"] == "raw-data"
    assert "nested" in data["directories"]
    filenames = [f["name"] for f in data["files"]]
    assert "sample.csv" in filenames


def test_get_storage_metadata(auth_header_and_conn):
    headers, conn_id, _ = auth_header_and_conn
    res = client.get(
        f"{api_prefix}/connections/{conn_id}/storage/metadata?container=raw-data&path=sample.csv",
        headers=headers
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "metadata" in data
    assert data["metadata"]["name"] == "sample.csv"
    assert data["metadata"]["size_in_bytes"] > 0


def test_preview_storage_csv(auth_header_and_conn):
    headers, conn_id, _ = auth_header_and_conn
    payload = {
        "container": "raw-data",
        "path": "sample.csv",
        "format": "csv",
        "limit": 10
    }
    res = client.post(f"{api_prefix}/connections/{conn_id}/storage/preview", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["sample_row_count"] == 2
    assert len(data["rows"]) == 2
    assert data["rows"][0]["name"] == "Alice"
    assert len(data["columns"]) == 2


def test_preview_storage_parquet(auth_header_and_conn):
    import pyarrow as pa
    import pyarrow.parquet as pq

    headers, conn_id, temp_dir = auth_header_and_conn
    parquet_path = os.path.join(temp_dir, "raw-data", "users.parquet")
    table = pa.Table.from_pydict({
        "user_id": [101, 102, 103],
        "username": ["admin", "analyst", "guest"],
        "is_active": [True, True, False]
    })
    pq.write_table(table, parquet_path)

    payload = {
        "container": "raw-data",
        "path": "users.parquet",
        "limit": 2
    }
    res = client.post(f"{api_prefix}/connections/{conn_id}/storage/preview", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["sample_row_count"] == 2
    assert data["format_detected"] == "parquet"
    assert len(data["columns"]) == 3
    assert data["rows"][0]["username"] == "admin"


def test_preview_storage_missing_file(auth_header_and_conn):
    headers, conn_id, _ = auth_header_and_conn
    payload = {
        "container": "raw-data",
        "path": "nonexistent.csv"
    }
    res = client.post(f"{api_prefix}/connections/{conn_id}/storage/preview", json=payload, headers=headers)
    assert res.status_code == 400



