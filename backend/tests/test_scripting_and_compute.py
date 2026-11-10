import pytest
import os
import time
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import text

# Import factory to ensure dynamic decorator registration occurs
import backend.app.activities.factory
from backend.app.core.database import SessionLocal
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.registry import activity_registry
from backend.app.activities.python_script import PythonScriptActivity
from backend.app.activities.stored_procedure import StoredProcedureActivity
from backend.app.activities.custom_activity import CustomActivity
from backend.app.activities.databricks import DatabricksNotebookActivity
from backend.app.execution.providers.databricks import DatabricksExecutionProvider
from backend.app.connectors.factory import get_connector
from backend.app.models.connection import Connection
from backend.app.models.workspace import Workspace, Project
from backend.app.core.security import encrypt_secret


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_project(db_session):
    ws = db_session.query(Workspace).first()
    ws_id = ws.id if ws else "ws_test"
    proj = db_session.query(Project).filter(Project.name == "ScriptingCompute_Test_Project").first()
    if not proj:
        proj = Project(workspace_id=ws_id, name="ScriptingCompute_Test_Project", description="Phase 4 test project")
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)
    return proj


def test_registry_contains_phase4_activities():
    """Verify that all Phase 4 activities are registered in ActivityRegistry."""
    activities = activity_registry.list_activities()
    types = {a["activity_type"] for a in activities}

    assert "PythonScript" in types
    assert "StoredProcedure" in types
    assert "CustomActivity" in types
    assert "DatabricksNotebook" in types
    assert "PySparkJob" in types

    # Check metadata properties
    py_desc = activity_registry.get_metadata("PythonScript")
    assert py_desc is not None
    assert py_desc.category == "Compute & External"
    assert "python" in py_desc.display_name.lower()


def test_python_script_execution_with_outputs():
    """Test PythonScriptActivity with parameter injection and output variable capture."""
    context = ActivityExecutionContext(
        activity_id="act-py-1",
        activity_name="ComputeMetrics",
        activity_type="PythonScript",
        pipeline_run_id="run-1",
        config={
            "script": """
x = context.get_param("x", 0)
y = context.get_param("y", 0)
result = {"sum": x + y, "product": x * y, "status": "COMPLETED"}
context.set_output("calculation", result)
print(f"Calculated sum: {x + y}")
""",
            "parameters": {"x": 25, "y": 4},
            "timeout_seconds": 15
        }
    )

    activity = PythonScriptActivity(context=context)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert "calculation" in result.output_variables
    assert result.output_variables["calculation"]["sum"] == 29
    assert result.output_variables["calculation"]["product"] == 100
    assert result.output_variables["calculation"]["status"] == "COMPLETED"
    assert result.metrics["duration_seconds"] > 0


def test_python_script_timeout_handling():
    """Test PythonScriptActivity cleanly terminates and fails when exceeding timeout limit."""
    context = ActivityExecutionContext(
        activity_id="act-py-timeout",
        activity_name="LongRunningScript",
        activity_type="PythonScript",
        pipeline_run_id="run-1",
        config={
            "script": """
import time
time.sleep(10)
""",
            "timeout_seconds": 1
        }
    )

    activity = PythonScriptActivity(context=context)
    result = activity.execute()

    assert result.status == "Failed"
    assert "timed out" in result.error_message.lower()


def test_python_script_syntax_or_runtime_error():
    """Test PythonScriptActivity captures traceback and error message on unhandled exception."""
    context = ActivityExecutionContext(
        activity_id="act-py-error",
        activity_name="FailingScript",
        activity_type="PythonScript",
        pipeline_run_id="run-1",
        config={
            "script": """
raise ValueError("Invalid dataset schema detected in worker process")
""",
            "timeout_seconds": 10
        }
    )

    activity = PythonScriptActivity(context=context)
    result = activity.execute()

    assert result.status == "Failed"
    assert "ValueError: Invalid dataset schema detected" in result.error_message


def test_custom_activity_success():
    """Test CustomActivity executing a command with arguments."""
    context = ActivityExecutionContext(
        activity_id="act-custom-1",
        activity_name="EchoCommand",
        activity_type="CustomActivity",
        pipeline_run_id="run-1",
        config={
            "command": "python3",
            "arguments": ["-c", "import sys; sys.stdout.write('dataflow custom output\\n'); sys.exit(0)"],
            "timeout_seconds": 10
        }
    )

    activity = CustomActivity(context=context)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert result.output_variables["exit_code"] == 0
    assert result.metrics["duration_seconds"] >= 0


def test_custom_activity_failure_exit_code():
    """Test CustomActivity reporting non-zero exit code as Failed."""
    context = ActivityExecutionContext(
        activity_id="act-custom-fail",
        activity_name="FailCommand",
        activity_type="CustomActivity",
        pipeline_run_id="run-1",
        config={
            "command": "python3",
            "arguments": ["-c", "import sys; sys.stderr.write('fatal binary error\\n'); sys.exit(3)"],
            "timeout_seconds": 10
        }
    )

    activity = CustomActivity(context=context)
    result = activity.execute()

    assert result.status == "Failed"
    assert result.metrics["exit_code"] == 3
    assert "fatal binary error" in result.error_message


def test_stored_procedure_postgresql(db_session, test_project):
    """Test StoredProcedureActivity against live PostgreSQL database."""
    from backend.app.testing.multicloud_harness import is_port_listening
    if not is_port_listening("127.0.0.1", 5433):
        pytest.skip("Local PostgreSQL daemon on port 5433 not available")

    pg_config = {
        "host": "localhost",
        "port": 5433,
        "user": "postgres",
        "password": "",
        "database": "postgres_target_warehouse"
    }

    # 1. Create a stored function in PostgreSQL target warehouse
    connector = get_connector("PostgreSQL", pg_config)
    connector.execute_query("""
        CREATE OR REPLACE FUNCTION dataflow_test_calc(a INT, b INT)
        RETURNS INT AS $$
        BEGIN
            RETURN a * b + 10;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 2. Setup connection record
    conn_rec = db_session.query(Connection).filter(Connection.name == "Test_Pg_Proc_Conn").first()
    if not conn_rec:
        conn_rec = Connection(
            project_id=test_project.id,
            name="Test_Pg_Proc_Conn",
            connector_type="PostgreSQL",
            config_encrypted=encrypt_secret(pg_config)
        )
        db_session.add(conn_rec)
        db_session.commit()
        db_session.refresh(conn_rec)

    context = ActivityExecutionContext(
        activity_id="act-proc-1",
        activity_name="InvokeCalcProc",
        activity_type="StoredProcedure",
        pipeline_run_id="run-1",
        config={
            "connection_id": conn_rec.id,
            "stored_procedure_name": "dataflow_test_calc",
            "is_function": True,
            "parameters": {"a": 7, "b": 6}
        }
    )

    activity = StoredProcedureActivity(context=context, db_session=db_session)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert result.rows_read == 1
    assert result.output_variables["first_row"]["result"] == 52  # 7*6 + 10 = 52

    # Cleanup test function
    connector.execute_query("DROP FUNCTION IF EXISTS dataflow_test_calc(INT, INT);")


def test_databricks_execution_provider_flow():
    """Test DatabricksExecutionProvider and DatabricksNotebookActivity state transitions."""
    # Mock _make_request for submit and poll
    with patch.object(DatabricksExecutionProvider, "_make_request") as mock_req:
        # 1. POST /api/2.1/jobs/runs/submit returns run_id
        # 2. GET status poll 1 returns RUNNING
        # 3. GET status poll 2 returns TERMINATED / SUCCESS
        mock_req.side_effect = [
            {"run_id": 998811},
            {"state": {"life_cycle_state": "RUNNING", "result_state": None}},
            {"state": {"life_cycle_state": "TERMINATED", "result_state": "SUCCESS"}}
        ]

        context = ActivityExecutionContext(
            activity_id="act-databricks-1",
            activity_name="RunETLNotebook",
            activity_type="DatabricksNotebook",
            pipeline_run_id="run-1",
            config={
                "host": "https://adb-fake.azuredatabricks.net",
                "token": "dapi123",
                "notebook_path": "/Users/data/cleanse",
                "existing_cluster_id": "0101-223344-cluster",
                "poll_interval_seconds": 1,
                "timeout_seconds": 10
            }
        )

        activity = DatabricksNotebookActivity(context=context)
        res = activity.execute()

        assert res.status == "Succeeded"
        assert res.output_variables["run_id"] == "998811"
        assert res.output_variables["result_state"] == "SUCCESS"
