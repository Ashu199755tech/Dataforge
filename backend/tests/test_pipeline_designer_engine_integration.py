import os
import sqlite3
import tempfile
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline
from backend.app.models.dataflow import DataFlow
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.core.security import encrypt_secret, get_password_hash, create_access_token
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.activities.data_flow import ExecuteDataFlowActivity
from backend.app.execution.runner import PipelineRunner


@pytest.fixture
def test_db():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_env(test_db):
    user = test_db.query(User).filter(User.email == "designer_admin@test.com").first()
    if not user:
        user = User(
            email="designer_admin@test.com",
            full_name="Designer Admin",
            hashed_password=get_password_hash("testpass"),
            role="Admin"
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

    ws = test_db.query(Workspace).filter(Workspace.name == "DesignerWS").first()
    if not ws:
        ws = Workspace(name="DesignerWS", description="Test Workspace")
        test_db.add(ws)
        test_db.commit()
        test_db.refresh(ws)

    proj = test_db.query(Project).filter(Project.name == "DesignerProj").first()
    if not proj:
        proj = Project(name="DesignerProj", workspace_id=ws.id)
        test_db.add(proj)
        test_db.commit()
        test_db.refresh(proj)

    token = create_access_token({"sub": user.id, "role": user.role})
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {token}"}
    return client, user, proj


def test_plan_activity_endpoint_copy(test_env):
    client, user, proj = test_env
    payload = {
        "activity_type": "CopyData",
        "activity_config": {
            "source": {"table_name": "source_orders"},
            "destination": {"table_name": "target_orders"}
        },
        "strategy": "AUTO"
    }
    resp = client.post("/api/v1/pipelines/plan-activity", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["selected_engine"] == "COPY"
    assert data["strategy_applied"] == "AUTO"
    assert "scores" in data
    assert "explanation" in data


def test_plan_activity_endpoint_force_sql_pushdown(test_env):
    client, user, proj = test_env
    payload = {
        "activity_type": "CopyData",
        "activity_config": {
            "source": {"table_name": "src_table"},
            "destination": {"table_name": "dst_table"}
        },
        "strategy": "FORCE_SQL_PUSHDOWN"
    }
    resp = client.post("/api/v1/pipelines/plan-activity", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["selected_engine"] == "SQL_PUSHDOWN"
    assert data["strategy_applied"] == "FORCE_SQL_PUSHDOWN"
    assert data["confidence_score"] == 1.0


def test_plan_dataflow_endpoint(test_env, test_db):
    client, user, proj = test_env
    df = DataFlow(
        project_id=proj.id,
        name="TestFlowForPlanning",
        description="Testing planning endpoint",
        graph_json={
            "nodes": [
                {"id": "src", "operatorType": "Source", "config": {"table_name": "orders"}},
                {"id": "flt", "operatorType": "Filter", "config": {"column": "status", "operator": "==", "value": "shipped"}},
                {"id": "snk", "operatorType": "Sink", "config": {"table_name": "orders_shipped"}}
            ],
            "edges": [
                {"id": "e1", "source": "src", "target": "flt"},
                {"id": "e2", "source": "flt", "target": "snk"}
            ]
        }
    )
    test_db.add(df)
    test_db.commit()
    test_db.refresh(df)

    resp = client.post(f"/api/v1/dataflows/{df.id}/plan", json={"strategy": "FORCE_SPARK"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["selected_engine"] == "SPARK"
    assert data["strategy_applied"] == "FORCE_SPARK"


def test_copy_data_activity_in_db_pushdown_execution(test_env, test_db):
    client, user, proj = test_env
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE source_items (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
        cur.execute("CREATE TABLE target_items (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
        for i in range(100):
            cur.execute("INSERT INTO source_items VALUES (?, ?, ?)", (i, f"Item_{i}", i * 1.5))
        conn.commit()
        conn.close()

        db_conn = Connection(
            project_id=proj.id,
            name="SQLite_Pushdown_Test",
            connector_type="sqlite",
            config_encrypted=encrypt_secret({"database_path": db_path})
        )
        test_db.add(db_conn)
        test_db.commit()
        test_db.refresh(db_conn)

        ctx = ActivityExecutionContext(
            pipeline_run_id="run_pushdown_1",
            activity_id="act_copy_pushdown",
            activity_name="CopyPushdown",
            activity_type="CopyData",
            config={
                "source": {"connection_id": db_conn.id, "table_name": "source_items", "filter_expr": "price > 50.0"},
                "destination": {"connection_id": db_conn.id, "table_name": "target_items"},
                "execution_engine_strategy": "FORCE_SQL_PUSHDOWN"
            }
        )

        activity = CopyDataActivity(ctx, test_db)
        res = activity.execute()

        assert res.status == "Succeeded"
        assert res.metrics["execution_engine"] == "SQL_PUSHDOWN"
        assert res.metrics["egress_bytes"] == 0

        # Verify records in target table
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM target_items")
        cnt = cur.fetchone()[0]
        conn.close()
        assert cnt > 0
        assert cnt < 100
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_copy_data_activity_partitioning_config(test_env, test_db):
    client, user, proj = test_env
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE src_part (id INTEGER PRIMARY KEY, val TEXT)")
        cur.execute("CREATE TABLE dst_part (id INTEGER PRIMARY KEY, val TEXT)")
        for i in range(50):
            cur.execute("INSERT INTO src_part VALUES (?, ?)", (i, f"Val_{i}"))
        conn.commit()
        conn.close()

        db_conn = Connection(
            project_id=proj.id,
            name="SQLite_Part_Test",
            connector_type="sqlite",
            config_encrypted=encrypt_secret({"database_path": db_path})
        )
        test_db.add(db_conn)
        test_db.commit()
        test_db.refresh(db_conn)

        ctx = ActivityExecutionContext(
            pipeline_run_id="run_part_1",
            activity_id="act_copy_part",
            activity_name="CopyPartitioned",
            activity_type="CopyData",
            config={
                "source": {"connection_id": db_conn.id, "table_name": "src_part"},
                "destination": {"connection_id": db_conn.id, "table_name": "dst_part"},
                "execution_engine_strategy": "FORCE_COPY",
                "partitioning": {
                    "column": "id",
                    "strategy": "Range",
                    "concurrency_limit": 4
                }
            }
        )

        activity = CopyDataActivity(ctx, test_db)
        res = activity.execute()

        assert res.status == "Succeeded"
        assert res.metrics["execution_engine"] == "COPY"
        assert res.metrics["partition_column"] == "id"
        assert res.metrics["concurrency_limit"] == 4
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_pipeline_runner_records_engine_decision(test_env, test_db):
    client, user, proj = test_env
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE customers_src (id INTEGER PRIMARY KEY, name TEXT)")
        cur.execute("CREATE TABLE customers_dst (id INTEGER PRIMARY KEY, name TEXT)")
        for i in range(20):
            cur.execute("INSERT INTO customers_src VALUES (?, ?)", (i, f"Customer_{i}"))
        conn.commit()
        conn.close()

        db_conn = Connection(
            project_id=proj.id,
            name="SQLite_Pipeline_Runner_Test",
            connector_type="sqlite",
            config_encrypted=encrypt_secret({"database_path": db_path})
        )
        test_db.add(db_conn)
        test_db.commit()
        test_db.refresh(db_conn)

        pipeline = Pipeline(
            project_id=proj.id,
            name="TestEnginePipeline",
            description="Testing planner metrics recorded by runner",
            definition_json={
                "activities": [
                    {
                        "id": "act_copy",
                        "name": "CopyCustomers",
                        "type": "CopyData",
                        "config": {
                            "source": {"connection_id": db_conn.id, "table_name": "customers_src"},
                            "destination": {"connection_id": db_conn.id, "table_name": "customers_dst"},
                            "execution_engine_strategy": "AUTO"
                        }
                    }
                ]
            }
        )
        test_db.add(pipeline)
        test_db.commit()
        test_db.refresh(pipeline)

        p_run = PipelineRun(
            pipeline_id=pipeline.id,
            run_type="Manual",
            status="Pending"
        )
        test_db.add(p_run)
        test_db.commit()
        test_db.refresh(p_run)

        runner = PipelineRunner(p_run.id)
        runner.execute_sync()

        test_db.refresh(p_run)
        assert p_run.status == "Succeeded"

        act_run = test_db.query(ActivityRun).filter(
            ActivityRun.pipeline_run_id == p_run.id,
            ActivityRun.activity_id == "act_copy"
        ).first()
        assert act_run is not None
        assert act_run.status == "Succeeded"
        assert "execution_engine" in act_run.metrics
        assert act_run.metrics["execution_engine"] in ("COPY", "SQL_PUSHDOWN")
        assert "planner_confidence" in act_run.metrics
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
