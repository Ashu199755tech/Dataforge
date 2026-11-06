import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun, ExecutionLog
from backend.app.models.alert import AlertRule, AlertEvent
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.execution.runner import PipelineRunner
from backend.app.monitoring.diagnostics import classify_error, get_worker_telemetry, extract_stack_trace
from backend.app.monitoring.metrics import build_timeline, build_metrics_summary, generate_execution_report
from backend.app.monitoring.alert_engine import AlertEngine


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(scope="module")
def auth_headers():
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == "monitor_tester@enterprise.io").first()
    if not user:
        user = User(
            email="monitor_tester@enterprise.io",
            full_name="Monitoring Tester",
            hashed_password=get_password_hash("TestSecret123!"),
            role="Admin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(data={"sub": user.id})
    db.close()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def test_setup():
    db: Session = SessionLocal()
    ws = db.query(Workspace).filter(Workspace.name == "Monitoring Workspace").first()
    if not ws:
        ws = Workspace(name="Monitoring Workspace", description="Workspace for observability testing")
        db.add(ws)
        db.commit()
        db.refresh(ws)

    project = db.query(Project).filter(Project.name == "Observability Project").first()
    if not project:
        project = Project(name="Observability Project", workspace_id=ws.id)
        db.add(project)
        db.commit()
        db.refresh(project)

    pipeline = db.query(Pipeline).filter(Pipeline.name == "Monitoring Telemetry Pipeline").first()
    if pipeline:
        db.delete(pipeline)
        db.commit()

    pipeline = Pipeline(
        name="Monitoring Telemetry Pipeline",
        project_id=project.id,
        definition_json={
            "variables": {
                "batch_status": "",
                "event_log": []
            },
            "activities": [
                {
                    "id": "act_set_var",
                    "name": "Initialize Telemetry Variables",
                    "type": "SetVariable",
                    "config": {
                        "variable_name": "batch_status",
                        "value": "IN_PROGRESS"
                    }
                },
                {
                    "id": "act_append_var",
                    "name": "Append Execution Telemetry",
                    "type": "AppendVariable",
                    "depends_on": [{"activity_id": "act_set_var", "condition": "Succeeded"}],
                    "config": {
                        "variable_name": "event_log",
                        "value": "Step 2 executed"
                    }
                }
            ]
        }
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    pipeline_id = pipeline.id

    # Create and execute a baseline run for observability tests
    run = PipelineRun(
        pipeline_id=pipeline_id,
        run_type="Manual",
        status="Pending",
        parameters={"env": "test"}
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    runner = PipelineRunner(run.id)
    runner.execute_sync()
    db.refresh(run)

    run_id = run.id
    db.close()
    return {"pipeline_id": pipeline_id, "run_id": run_id}


def test_diagnostics_error_classification():
    """Verify clean error classification into standard diagnostic domains."""
    conn_err = "psycopg2.OperationalError: could not connect to server: Connection refused"
    assert classify_error(conn_err) == "ConnectionError"

    timeout_err = TimeoutError("Request timed out after 30 seconds")
    assert classify_error(timeout_err) == "TimeoutError"

    dq_err = "AssertionError: Schema drift detected in source payload"
    assert classify_error(dq_err) == "DataQualityError"

    user_err = KeyError("Missing required parameter 'destination_table'")
    assert classify_error(user_err) == "UserError"

    sys_err = RuntimeError("Fatal memory segmentation or unhandled engine condition")
    assert classify_error(sys_err) == "SystemError"

    assert classify_error(None) == "Unknown"


def test_worker_telemetry_collection():
    """Verify worker telemetry captures host, pid, and process info."""
    telemetry = get_worker_telemetry()
    assert "hostname" in telemetry
    assert "pid" in telemetry
    assert "thread_id" in telemetry
    assert "platform" in telemetry
    assert telemetry["process_title"] == "DataFlow-Worker-Runner"


def test_pipeline_execution_with_telemetry_capture(test_setup):
    """Executes a pipeline and verifies activity runs record worker_info, duration, and metrics."""
    db: Session = SessionLocal()
    pipeline_id = test_setup["pipeline_id"]

    run = PipelineRun(
        pipeline_id=pipeline_id,
        run_type="Manual",
        status="Pending",
        parameters={"env": "test"}
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    runner = PipelineRunner(run.id)
    runner.execute_sync()

    db.refresh(run)
    assert run.status == "Succeeded"
    assert run.total_activities == 2
    assert run.succeeded_activities == 2
    assert run.failed_activities == 0
    assert run.worker_info is not None
    assert "hostname" in run.worker_info
    assert run.execution_metrics is not None
    assert "data_movement" in run.execution_metrics

    # Verify activity records
    act_runs = db.query(ActivityRun).filter(ActivityRun.pipeline_run_id == run.id).all()
    assert len(act_runs) == 2
    for act in act_runs:
        assert act.status == "Succeeded"
        assert act.worker_info is not None
        assert "pid" in act.worker_info
        assert isinstance(act.retry_history, list)
        assert len(act.retry_history) >= 1
        assert act.retry_history[0]["status"] == "Succeeded"

    db.close()


def test_timeline_and_metrics_api(client, auth_headers, test_setup):
    """Test GET /api/v1/runs/{id}/timeline and GET /api/v1/runs/{id}/metrics."""
    run_id = test_setup["run_id"]

    # Timeline
    t_res = client.get(f"/api/v1/runs/{run_id}/timeline", headers=auth_headers)
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert t_data["pipeline_run_id"] == run_id
    assert "timeline" in t_data
    assert len(t_data["timeline"]) == 2
    for item in t_data["timeline"]:
        assert "offset_seconds" in item
        assert "start_percentage" in item
        assert "width_percentage" in item
        assert item["status"] == "Succeeded"

    # Metrics
    m_res = client.get(f"/api/v1/runs/{run_id}/metrics", headers=auth_headers)
    assert m_res.status_code == 200
    m_data = m_res.json()
    assert m_data["pipeline_run_id"] == run_id
    assert "data_movement" in m_data
    assert "activity_summary" in m_data
    assert m_data["activity_summary"]["success_rate_percentage"] == 100.0


def test_downloadable_execution_reports(client, auth_headers, test_setup):
    """Verify downloadable reports across JSON, CSV, and Text formats."""
    run_id = test_setup["run_id"]

    # JSON format
    json_res = client.get(f"/api/v1/runs/{run_id}/report?format=json", headers=auth_headers)
    assert json_res.status_code == 200
    j_data = json_res.json()
    assert j_data["run_id"] == run_id
    assert "metrics" in j_data
    assert "timeline" in j_data
    assert len(j_data["activities"]) == 2

    # CSV format
    csv_res = client.get(f"/api/v1/runs/{run_id}/report?format=csv", headers=auth_headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    csv_text = csv_res.text
    assert "# DATAFLOW ENTERPRISE EXECUTION REPORT" in csv_text
    assert "Activity ID,Activity Name,Type,Status" in csv_text
    assert "act_set_var" in csv_text

    # Text format
    txt_res = client.get(f"/api/v1/runs/{run_id}/report?format=text", headers=auth_headers)
    assert txt_res.status_code == 200
    assert "text/plain" in txt_res.headers.get("content-type", "")
    assert "PIPELINE EXECUTION LEDGER REPORT" in txt_res.text
    assert "act_set_var" in txt_res.text


def test_activity_diagnostics_endpoint(client, auth_headers, test_setup):
    """Verify GET /api/v1/runs/{run_id}/activities/{activity_id}/diagnostics returns deep observability."""
    run_id = test_setup["run_id"]

    diag_res = client.get(f"/api/v1/runs/{run_id}/activities/act_set_var/diagnostics", headers=auth_headers)
    assert diag_res.status_code == 200
    diag_data = diag_res.json()
    assert diag_data["activity_id"] == "act_set_var"
    assert diag_data["status"] == "Succeeded"
    assert "worker_info" in diag_data
    assert "retry_history" in diag_data
    assert "output_variables" in diag_data


def test_alert_rules_crud_and_events(client, auth_headers, test_setup):
    """Test full lifecycle of Alert Rules and Alert Events."""
    pipeline_id = test_setup["pipeline_id"]

    # 1. Create OnFailure Alert Rule
    create_res = client.post(
        "/api/v1/alerts/rules",
        headers=auth_headers,
        json={
            "name": "Pipeline Failure Alert",
            "description": "Triggered when telemetry pipeline fails",
            "target_type": "Pipeline",
            "pipeline_id": pipeline_id,
            "condition_type": "OnFailure",
            "action_type": "Log",
            "action_config": {"channel": "ops-alerts"},
            "is_enabled": True
        }
    )
    assert create_res.status_code == 201
    rule = create_res.json()
    rule_id = rule["id"]
    assert rule["name"] == "Pipeline Failure Alert"
    assert rule["condition_type"] == "OnFailure"

    # 2. Create SLA Duration Alert Rule
    sla_res = client.post(
        "/api/v1/alerts/rules",
        headers=auth_headers,
        json={
            "name": "SLA Breach Alert",
            "description": "Triggered if pipeline exceeds 10s",
            "target_type": "Pipeline",
            "pipeline_id": pipeline_id,
            "condition_type": "DurationExceeded",
            "threshold_value": 10.0,
            "action_type": "Log",
            "is_enabled": True
        }
    )
    assert sla_res.status_code == 201

    # 3. List Alert Rules
    list_res = client.get(f"/api/v1/alerts/rules?pipeline_id={pipeline_id}", headers=auth_headers)
    assert list_res.status_code == 200
    rules_list = list_res.json()
    assert len(rules_list) >= 2

    # 4. Test trigger alert rule endpoint
    test_trig_res = client.post(f"/api/v1/alerts/rules/{rule_id}/test", headers=auth_headers)
    assert test_trig_res.status_code == 200
    event_data = test_trig_res.json()
    assert event_data["alert_rule_id"] == rule_id
    assert event_data["status"] == "Delivered"

    # 5. Query alert events
    events_res = client.get("/api/v1/alerts/events", headers=auth_headers)
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) >= 1

    # 6. Delete alert rule
    del_res = client.delete(f"/api/v1/alerts/rules/{rule_id}", headers=auth_headers)
    assert del_res.status_code == 200


def test_alert_engine_evaluates_on_pipeline_failure(test_setup):
    """Verify AlertEngine automatically fires OnFailure alert when a run fails."""
    db: Session = SessionLocal()
    pipeline_id = test_setup["pipeline_id"]
    rule = AlertRule(
        name="Auto Failure Guard",
        target_type="Global",
        condition_type="OnFailure",
        action_type="Log",
        is_enabled=True
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    failed_run = PipelineRun(
        pipeline_id=pipeline_id,
        run_type="Manual",
        status="Failed",
        error_summary="Connection timed out while writing records"
    )
    db.add(failed_run)
    db.commit()
    db.refresh(failed_run)

    triggered_events = AlertEngine.evaluate_pipeline_run(failed_run, db)
    assert len(triggered_events) >= 1
    fired = next((e for e in triggered_events if e.alert_rule_id == rule.id), None)
    assert fired is not None
    assert fired.severity == "Critical"
    assert "Connection timed out" in fired.message

    # Cleanup
    db.delete(rule)
    db.delete(failed_run)
    db.commit()
    db.close()


def test_pipeline_cancel_and_rerun(client, auth_headers, test_setup):
    """Test POST /api/v1/runs/{id}/cancel and POST /api/v1/runs/{id}/rerun."""
    db: Session = SessionLocal()
    pipeline_id = test_setup["pipeline_id"]
    run = PipelineRun(
        pipeline_id=pipeline_id,
        run_type="Manual",
        status="Running",
        parameters={"batch": 101}
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    run_id = run.id
    db.close()

    # Cancel
    cancel_res = client.post(f"/api/v1/runs/{run_id}/cancel", headers=auth_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "Cancelled"

    # Rerun
    rerun_res = client.post(f"/api/v1/runs/{run_id}/rerun", headers=auth_headers)
    assert rerun_res.status_code == 200
    new_run = rerun_res.json()
    assert new_run["pipeline_id"] == pipeline_id
    assert new_run["run_type"] == "Rerun"


def test_timeline_and_metrics_engine_analytics(test_setup):
    """Test Phase 8 timeline engine fields, metrics summary engine analytics, and report generation."""
    db: Session = SessionLocal()
    pipeline_id = test_setup["pipeline_id"]

    run = PipelineRun(
        pipeline_id=pipeline_id,
        run_type="Manual",
        status="Succeeded",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_seconds=12.5,
        total_activities=3,
        succeeded_activities=3,
        failed_activities=0,
        total_rows_read=15000,
        total_rows_written=15000,
        total_bytes_processed=17825792
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    act_pushdown = ActivityRun(
        pipeline_run_id=run.id,
        activity_id="act_pushdown_1",
        activity_name="In-Database Transform",
        activity_type="CopyData",
        status="Succeeded",
        retry_attempt=0,
        rows_read=5000,
        rows_written=5000,
        bytes_processed=5242880,  # 5 MB
        duration_seconds=2.1,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        metrics={
            "execution_engine": "SQL_PUSHDOWN",
            "planner_strategy": "AUTO",
            "planner_confidence": 0.98,
            "planner_explanation": "Zero-egress in-database SQL transformation",
            "pushdown_dialect": "PostgreSQL",
            "generated_sql": "INSERT INTO target SELECT * FROM source WHERE active = true"
        }
    )
    act_spark = ActivityRun(
        pipeline_run_id=run.id,
        activity_id="act_spark_1",
        activity_name="Distributed Aggregation",
        activity_type="ExecuteDataFlow",
        status="Succeeded",
        retry_attempt=0,
        rows_read=7000,
        rows_written=7000,
        bytes_processed=10485760,  # 10 MB
        duration_seconds=6.4,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        metrics={
            "execution_engine": "SPARK",
            "planner_strategy": "FORCE_SPARK",
            "planner_confidence": 1.0,
            "spark_master": "local[*]",
            "spark_app_id": "spark-app-test-8"
        }
    )
    act_copy = ActivityRun(
        pipeline_run_id=run.id,
        activity_id="act_copy_1",
        activity_name="Parallel Copy Slices",
        activity_type="CopyData",
        status="Succeeded",
        retry_attempt=0,
        rows_read=3000,
        rows_written=3000,
        bytes_processed=2097152,  # 2 MB
        duration_seconds=3.8,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        metrics={
            "execution_engine": "COPY",
            "planner_strategy": "AUTO",
            "partition_column": "customer_id",
            "concurrency_limit": 4
        }
    )
    db.add_all([act_pushdown, act_spark, act_copy])
    db.commit()

    try:
        # Refresh run with activity_runs relation or direct access
        db.refresh(run)
        # 1. Timeline verification
        timeline_result = build_timeline(run)
        items = timeline_result
        assert len(items) == 3

        pd_item = next(i for i in items if i["activity_id"] == "act_pushdown_1")
        assert pd_item["execution_engine"] == "SQL_PUSHDOWN"
        assert pd_item["planner_strategy"] == "AUTO"

        sp_item = next(i for i in items if i["activity_id"] == "act_spark_1")
        assert sp_item["execution_engine"] == "SPARK"
        assert sp_item["planner_strategy"] == "FORCE_SPARK"

        cp_item = next(i for i in items if i["activity_id"] == "act_copy_1")
        assert cp_item["execution_engine"] == "COPY"
        assert cp_item["partition_column"] == "customer_id"

        # 2. Metrics summary & Engine Analytics verification
        summary = build_metrics_summary(run)
        assert "engine_analytics" in summary
        ea = summary["engine_analytics"]
        assert ea["engine_distribution"]["SQL_PUSHDOWN"] == 1
        assert ea["engine_distribution"]["SPARK"] == 1
        assert ea["engine_distribution"]["COPY"] == 1
        assert ea["egress_avoided_bytes"] == 5242880
        assert ea["egress_avoided_mb"] == 5.0
        assert ea["total_partition_slices"] == 4

        # 3. Execution report verification
        csv_report = generate_execution_report(run, "csv")
        assert "Execution Engine" in csv_report
        assert "Planner Strategy" in csv_report
        assert "SQL_PUSHDOWN" in csv_report
        assert "SPARK" in csv_report
        assert "COPY" in csv_report

        txt_report = generate_execution_report(run, "text")
        assert "ENGINE" in txt_report
        assert "SQL_PUSHDOWN" in txt_report
        assert "SPARK" in txt_report
        assert "COPY" in txt_report
    finally:
        db.delete(act_pushdown)
        db.delete(act_spark)
        db.delete(act_copy)
        db.delete(run)
        db.commit()
        db.close()


def test_observability_service_engine_metrics_and_spans(test_setup):
    """Test Phase 8 Prometheus metric counters and OpenTelemetry span attributes."""
    from backend.app.services.observability_service import ObservabilityService

    db: Session = SessionLocal()
    pipeline_id = test_setup["pipeline_id"]

    run = PipelineRun(
        pipeline_id=pipeline_id,
        run_type="Manual",
        status="Succeeded",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_seconds=5.0
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    act = ActivityRun(
        pipeline_run_id=run.id,
        activity_id="act_pd_telemetry_1",
        activity_name="Pushdown In-Database Aggregate",
        activity_type="CopyData",
        status="Succeeded",
        rows_read=1000,
        rows_written=1000,
        bytes_processed=204800,
        duration_seconds=1.2,
        metrics={
            "execution_engine": "SQL_PUSHDOWN",
            "planner_strategy": "AUTO",
            "planner_confidence": 0.96,
            "records_transferred": 1000
        }
    )
    db.add(act)
    db.commit()

    try:
        # 1. Prometheus Engine Metrics
        prom_metrics = ObservabilityService.export_prometheus_metrics(db)
        assert "dataforge_engine_activities_total" in prom_metrics
        assert 'dataforge_engine_activities_total{engine="SQL_PUSHDOWN"}' in prom_metrics
        assert "dataforge_sql_pushdown_egress_bytes_avoided" in prom_metrics
        assert "dataforge_copy_engine_partitions_total" in prom_metrics

        # 2. OpenTelemetry Trace Attributes
        otel_trace = ObservabilityService.export_opentelemetry_trace(db, run.id)
        assert otel_trace is not None
        assert otel_trace.trace_id is not None
        assert len(otel_trace.spans) >= 2  # Root span + activity span

        act_span = next((s for s in otel_trace.spans if s.name.startswith("Activity: ")), None)
        assert act_span is not None
        assert act_span.attributes["dataforge.engine.selected"] == "SQL_PUSHDOWN"
        assert act_span.attributes["dataforge.engine.strategy"] == "AUTO"
        assert act_span.attributes["dataforge.engine.confidence"] == 0.96
    finally:
        db.delete(act)
        db.delete(run)
        db.commit()
        db.close()

