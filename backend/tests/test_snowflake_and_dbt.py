import pytest
import os
import json
import time
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

# Ensure activity and connector registrations are loaded
import backend.app.activities.factory
import backend.app.connectors.factory
from backend.app.core.database import SessionLocal
from backend.app.connectors.factory import get_connector
from backend.app.connectors.snowflake import SnowflakeConnector
from backend.app.activities.factory import get_activity_instance
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.registry import activity_registry
from backend.app.activities.dbt import DbtActivity
from backend.app.models.workspace import Workspace, Project
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.execution.runner import PipelineRunner


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_project(db_session: Session):
    ws = db_session.query(Workspace).first()
    if not ws:
        ws = Workspace(name="Snowflake_Test_WS", description="Workspace for snowflake tests")
        db_session.add(ws)
        db_session.commit()
        db_session.refresh(ws)

    proj = db_session.query(Project).filter(Project.name == "Modern_Data_Stack_Project").first()
    if not proj:
        proj = Project(workspace_id=ws.id, name="Modern_Data_Stack_Project", description="Modern Data Stack Pipeline Project")
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)
    return proj


# ==========================================
# 1. Snowflake Connector Tests
# ==========================================

def test_snowflake_connector_registration():
    """Verify Snowflake connector is registered in connector factory."""
    config = {
        "account": "xy12345.us-east-1",
        "user": "DATA_ENGINEER",
        "warehouse": "COMPUTE_WH",
        "database": "ANALYTICS",
        "schema": "PUBLIC",
        "mock_mode": True
    }
    connector = get_connector("Snowflake", config)
    assert isinstance(connector, SnowflakeConnector)
    assert connector.account == "xy12345.us-east-1"
    assert connector.warehouse == "COMPUTE_WH"


def test_snowflake_test_connection():
    """Test Snowflake test_connection under mock and parameter validation modes."""
    # Validation failure when credentials missing
    bad_conn = SnowflakeConnector({"mock_mode": False})
    res_bad = bad_conn.test_connection()
    assert res_bad.success is False
    assert "requires 'account' and 'user'" in res_bad.message

    # Successful mock connection
    good_conn = SnowflakeConnector({
        "account": "xy12345.eu-central-1",
        "user": "SVC_DATAFORGE",
        "warehouse": "TRANSFORM_WH",
        "mock_mode": True
    })
    res_good = good_conn.test_connection()
    assert res_good.success is True
    assert "Connected to Snowflake account" in res_good.message
    assert res_good.server_version == "Snowflake 8.12.0"


def test_snowflake_schema_table_column_discovery():
    """Test discovering schemas, tables, and column metadata."""
    connector = SnowflakeConnector({
        "account": "xy12345.us-east-1",
        "user": "DATA_ENGINEER",
        "database": "ANALYTICS_DB",
        "schema": "MARTS",
        "mock_mode": True,
        "_mock_tables": {
            "DIM_CUSTOMERS": [
                {"customer_id": "C001", "name": "Acme Corp", "tier": "Enterprise", "arr": 120000.0},
                {"customer_id": "C002", "name": "Globex", "tier": "Growth", "arr": 45000.0}
            ]
        }
    })

    schemas = connector.discover_schemas()
    assert "PUBLIC" in schemas
    assert "MARTS" in schemas

    tables = connector.discover_tables("MARTS")
    table_names = [t.name for t in tables]
    assert "DIM_CUSTOMERS" in table_names

    cols = connector.discover_columns("DIM_CUSTOMERS", "MARTS")
    col_names = [c.name for c in cols]
    assert "customer_id" in col_names
    assert "tier" in col_names
    assert "arr" in col_names


def test_snowflake_streaming_read_and_query_execution():
    """Test reading streaming chunks and executing direct queries."""
    sample_records = [
        {"order_id": 101, "amount": 250.0, "status": "COMPLETED"},
        {"order_id": 102, "amount": 80.5, "status": "PENDING"},
        {"order_id": 103, "amount": 420.0, "status": "COMPLETED"}
    ]
    connector = SnowflakeConnector({
        "account": "xy12345.us-east-1",
        "user": "ANALYST",
        "database": "SALES_DB",
        "mock_mode": True,
        "_mock_tables": {"FCT_ORDERS": sample_records}
    })

    # Test direct query
    rows = connector.execute_query("SELECT * FROM FCT_ORDERS WHERE status = 'COMPLETED'")
    assert len(rows) == 2
    assert rows[0]["order_id"] == 101

    # Test streaming batch reader
    stream = connector.read_data_stream("FCT_ORDERS", batch_size=2)
    batches = list(stream)
    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1


def test_snowflake_writing_append_truncate_and_upsert_merge():
    """Test writing batches in append, truncate, and upsert/merge modes."""
    connector = SnowflakeConnector({
        "account": "xy12345.us-east-1",
        "user": "ETL_USER",
        "database": "DWH",
        "schema": "REPORTING",
        "mock_mode": True
    })

    records = [
        {"metric_id": "M1", "val": 100},
        {"metric_id": "M2", "val": 200}
    ]

    # Append mode
    res_append = connector.write_data_batch("METRICS_SUMMARY", records, write_mode="append")
    assert res_append == 2
    assert len(connector._mock_tables["METRICS_SUMMARY"]) == 2

    # Truncate overwrite mode
    new_records = [{"metric_id": "M3", "val": 300}]
    res_trunc = connector.write_data_batch("METRICS_SUMMARY", new_records, write_mode="truncate")
    assert res_trunc == 1
    assert len(connector._mock_tables["METRICS_SUMMARY"]) == 1
    assert connector._mock_tables["METRICS_SUMMARY"][0]["metric_id"] == "M3"

    # Upsert / Merge mode
    upsert_records = [
        {"metric_id": "M3", "val": 350},  # Update
        {"metric_id": "M4", "val": 400}   # Insert
    ]
    res_upsert = connector.write_data_batch(
        "METRICS_SUMMARY",
        upsert_records,
        write_mode="upsert",
        key_columns=["metric_id"]
    )
    assert res_upsert == 2
    assert len(connector._mock_tables["METRICS_SUMMARY"]) == 2
    vals = {r["metric_id"]: r["val"] for r in connector._mock_tables["METRICS_SUMMARY"]}
    assert vals["M3"] == 350
    assert vals["M4"] == 400


# ==========================================
# 2. dbt Activity Tests
# ==========================================

def test_dbt_activity_registration(db_session: Session):
    """Verify DbtActivity is cataloged in the ActivityRegistry and ActivityFactory."""
    activities = activity_registry.list_activities()
    types = {a["activity_type"] for a in activities}
    assert "Dbt" in types

    context = ActivityExecutionContext(
        activity_id="act-dbt-reg",
        activity_name="DbtTransform",
        activity_type="Dbt",
        pipeline_run_id="run-dbt-1",
        config={"command": "run", "mock_mode": True}
    )
    instance = get_activity_instance(context, db_session)
    assert isinstance(instance, DbtActivity)


def test_dbt_core_simulation_and_expressions():
    """Test dbt Core with dynamic parameter resolution and simulated execution."""
    context = ActivityExecutionContext(
        activity_id="act-dbt-exec",
        activity_name="RunDbtMarts",
        activity_type="Dbt",
        pipeline_run_id="run-dbt-2",
        pipeline_parameters={"env_target": "production", "model_tag": "finance"},
        config={
            "mode": "core",
            "command": "run",
            "target": "@parameters('env_target')",
            "select": "tag:@parameters('model_tag')",
            "mock_mode": True
        }
    )
    activity = DbtActivity(context=context)
    result = activity.execute()

    assert result.status == "Succeeded"
    assert result.output_variables["mode"] == "core"
    assert result.output_variables["command"] == "dbt run"
    assert result.output_variables["models_run"] == 5
    assert result.output_variables["models_passed"] == 5
    assert result.output_variables["models_failed"] == 0


def test_dbt_core_subprocess_stdout_parsing():
    """Test dbt Core stdout regex parsing (PASS, WARN, ERROR) with subprocess mocking."""
    mock_dbt_stdout = (
        "09:15:00 Running with dbt=1.8.0\n"
        "09:15:02 Concurrency: 4 threads (target='prod')\n"
        "09:15:03 1 of 4 START sql table model analytics.dim_customers ... [RUN]\n"
        "09:15:05 1 of 4 OK created sql table model analytics.dim_customers .. [PASS in 2.10s]\n"
        "09:15:06 2 of 4 START test unique_dim_customers_id ................ [RUN]\n"
        "09:15:07 2 of 4 PASS unique_dim_customers_id ...................... [PASS in 0.85s]\n"
        "09:15:08 Finished running 2 table models, 2 tests in 8.5 seconds.\n"
        "09:15:08 Completed successfully\n"
        "09:15:08 Done. PASS=4 WARN=0 ERROR=0 TOTAL=4\n"
    )

    with patch("shutil.which", return_value="/usr/local/bin/dbt"):
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = (mock_dbt_stdout, "")
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            context = ActivityExecutionContext(
                activity_id="act-dbt-parse",
                activity_name="DbtParseLog",
                activity_type="Dbt",
                pipeline_run_id="run-dbt-3",
                config={
                    "mode": "core",
                    "command": "build",
                    "select": "marts",
                    "mock_mode": False
                }
            )
            activity = DbtActivity(context=context)
            result = activity.execute()

            assert result.status == "Succeeded"
            assert result.output_variables["models_passed"] == 4
            assert result.output_variables["models_failed"] == 0
            assert result.output_variables["models_run"] == 4


def test_dbt_core_subprocess_failure_detection():
    """Test that non-zero exit codes from dbt CLI are flagged as Failed."""
    mock_error_stdout = (
        "09:15:05 1 of 2 START sql view model analytics.stg_orders ......... [RUN]\n"
        "09:15:06 1 of 2 ERROR creating sql view model analytics.stg_orders . [ERROR in 1.1s]\n"
        "Database Error in model stg_orders: table 'raw.orders' does not exist\n"
        "09:15:07 Done. PASS=0 WARN=0 ERROR=1 TOTAL=1\n"
    )

    with patch("shutil.which", return_value="/usr/local/bin/dbt"):
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = (mock_error_stdout, "Compilation failed")
            mock_proc.returncode = 1
            mock_popen.return_value = mock_proc

            context = ActivityExecutionContext(
                activity_id="act-dbt-fail",
                activity_name="DbtFailTest",
                activity_type="Dbt",
                pipeline_run_id="run-dbt-4",
                config={"mode": "core", "command": "run", "mock_mode": False}
            )
            activity = DbtActivity(context=context)
            result = activity.execute()

            assert result.status == "Failed"
            assert result.output_variables["models_failed"] == 1
            assert "table 'raw.orders' does not exist" in result.error_message


def test_dbt_cloud_simulation_and_api_flow():
    """Test dbt Cloud API mode (trigger and poll states)."""
    # 1. Test mock / simulation mode
    context_sim = ActivityExecutionContext(
        activity_id="act-dbt-cloud-mock",
        activity_name="TriggerDbtCloudSim",
        activity_type="Dbt",
        pipeline_run_id="run-cloud-1",
        config={
            "mode": "cloud",
            "account_id": "12345",
            "job_id": "67890",
            "mock_mode": True
        }
    )
    act_sim = DbtActivity(context=context_sim)
    res_sim = act_sim.execute()
    assert res_sim.status == "Succeeded"
    assert res_sim.output_variables["mode"] == "cloud"
    assert res_sim.output_variables["status_human"] == "Success"

    # 2. Test live API mock polling: Trigger -> Poll (Running) -> Poll (Success)
    trigger_response = MagicMock()
    trigger_response.read.return_value = json.dumps({"data": {"id": 776655}}).encode("utf-8")
    trigger_response.__enter__.return_value = trigger_response

    poll_running = MagicMock()
    poll_running.read.return_value = json.dumps({"data": {"status": 3, "status_human": "Running"}}).encode("utf-8")
    poll_running.__enter__.return_value = poll_running

    poll_success = MagicMock()
    poll_success.read.return_value = json.dumps({"data": {"status": 10, "status_human": "Success"}}).encode("utf-8")
    poll_success.__enter__.return_value = poll_success

    with patch("urllib.request.urlopen") as mock_url:
        mock_url.side_effect = [trigger_response, poll_running, poll_success]

        context_api = ActivityExecutionContext(
            activity_id="act-dbt-cloud-api",
            activity_name="TriggerDbtCloudLive",
            activity_type="Dbt",
            pipeline_run_id="run-cloud-2",
            config={
                "mode": "cloud",
                "account_id": "999",
                "job_id": "888",
                "api_token": "dbt_token_secret_123",
                "poll_interval_seconds": 1,
                "timeout_seconds": 10,
                "mock_mode": False
            }
        )
        act_api = DbtActivity(context=context_api)
        res_api = act_api.execute()

        assert res_api.status == "Succeeded"
        assert res_api.output_variables["run_id"] == "776655"
        assert res_api.output_variables["status_human"] == "Success"


# ==========================================
# 3. Modern Data Stack Pipeline Workflow
# ==========================================

def test_databricks_snowflake_dbt_pipeline_workflow(db_session: Session, test_project: Project):
    """
    Test End-to-End Enterprise Pipeline DAG:
      1. DatabricksNotebook: Extracts raw data and computes metrics
      2. Dbt: Transforms raw metrics into dimensional data marts
      3. DataQualityCheck: Evaluates custom SQL rulebook against marts
    """
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f_csv:
        csv_path = f_csv.name
        f_csv.write("customer_id,revenue\n1,15000.0\n2,24000.0\n")

    try:
        pipeline_def = [
            {
                "id": "act_databricks_ingest",
                "name": "Databricks Ingest",
                "type": "DatabricksNotebook",
                "depends_on": [],
                "config": {
                    "host": "https://adb-fake.azuredatabricks.net",
                    "token": "dapi_fake_123",
                    "notebook_path": "/Shared/bronze_to_silver",
                    "existing_cluster_id": "1122-334455-cluster",
                    "poll_interval_seconds": 1,
                    "timeout_seconds": 10
                }
            },
            {
                "id": "act_dbt_transform",
                "name": "dbt Silver to Gold",
                "type": "Dbt",
                "depends_on": [{"activity_id": "act_databricks_ingest", "condition": "Succeeded"}],
                "config": {
                    "mode": "core",
                    "command": "run",
                    "select": "marts.finance.*",
                    "mock_mode": True
                }
            },
            {
                "id": "act_dq_check",
                "name": "Data Quality Assurance",
                "type": "DataQualityCheck",
                "depends_on": [{"activity_id": "act_dbt_transform", "condition": "Succeeded"}],
                "config": {
                    "dataset_name": "gold_marts",
                    "file_path": csv_path,
                    "rules": [
                        {
                            "rule_name": "Revenue positive",
                            "rule_type": "CustomSqlCheck",
                            "sql_condition": "revenue >= 0",
                            "threshold_percent": 100.0
                        }
                    ]
                }
            }
        ]

        pipe = Pipeline(
            project_id=test_project.id,
            name="Databricks_Snowflake_Dbt_Enterprise_Pipeline",
            description="End-to-end pipeline connecting Databricks, Snowflake & dbt",
            definition_json={"activities": pipeline_def}
        )
        db_session.add(pipe)
        db_session.commit()
        db_session.refresh(pipe)

        run = PipelineRun(
            pipeline_id=pipe.id,
            run_type="Manual",
            status="Pending",
            parameters={"env": "prod"}
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)

        # Mock Databricks request
        with patch("backend.app.execution.providers.databricks.DatabricksExecutionProvider._make_request") as mock_req:
            mock_req.side_effect = [
                {"run_id": 445566},
                {"state": {"life_cycle_state": "TERMINATED", "result_state": "SUCCESS"}}
            ]

            runner = PipelineRunner(run.id)
            runner.execute_sync()

            db_session.refresh(run)
            assert run.status == "Succeeded", f"Pipeline run failed: {run.error_summary}"

            # Verify all 3 activity runs recorded and succeeded
            act_runs = db_session.query(ActivityRun).filter(ActivityRun.pipeline_run_id == run.id).all()
            assert len(act_runs) == 3
            statuses = {ar.activity_id: ar.status for ar in act_runs}
            assert statuses["act_databricks_ingest"] == "Succeeded"
            assert statuses["act_dbt_transform"] == "Succeeded"
            assert statuses["act_dq_check"] == "Succeeded"
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)
        assert statuses["act_dbt_transform"] == "Succeeded"
        assert statuses["act_dq_check"] == "Succeeded"
