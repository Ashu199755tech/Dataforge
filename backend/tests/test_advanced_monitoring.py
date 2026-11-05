import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.models.runtime import IntegrationRuntime
from backend.app.models.alert import AlertRule, AlertEvent
from backend.app.monitoring.alert_engine import AlertEngine
from backend.app.services.observability_service import ObservabilityService
from backend.app.core.security import get_password_hash, create_access_token


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def test_setup(db_session: Session):
    uid = str(uuid.uuid4())[:8]
    user = User(
        id=str(uuid.uuid4()),
        email=f"obs_admin_{uid}@dataflow.enterprise",
        full_name="Observability Test Admin",
        hashed_password=get_password_hash("TestPass123!"),
        role="Admin",
        is_active=True
    )
    ws = Workspace(id=str(uuid.uuid4()), name=f"Obs WS {uid}")
    proj = Project(id=str(uuid.uuid4()), workspace_id=ws.id, name=f"Obs Project {uid}")
    
    pipe = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Telemetry_Pipeline",
        definition_json={"activities": [{"name": "Copy_Telemetry", "type": "CopyData"}]}
    )

    db_session.add_all([user, ws, proj, pipe])
    db_session.commit()

    token = create_access_token({"sub": user.id, "role": user.role})
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    return {
        "user": user,
        "workspace": ws,
        "project": proj,
        "pipeline": pipe,
        "client": client,
        "token": token
    }


def test_copy_data_performance_aggregation(db_session: Session, test_setup):
    """Verifies throughput, bytes transferred, and performance trends for Copy Data."""
    proj = test_setup["project"]
    pipe = test_setup["pipeline"]

    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipe.id,
        status="Succeeded",
        duration_seconds=12.5,
        total_rows_written=50000,
        started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        ended_at=datetime.now(timezone.utc)
    )
    db_session.add(run)
    db_session.flush()

    act1 = ActivityRun(
        id=str(uuid.uuid4()),
        pipeline_run_id=run.id,
        activity_id="act_orders_bronze",
        activity_name="Copy_Orders_Bronze",
        activity_type="CopyData",
        status="Succeeded",
        duration_seconds=5.0,
        rows_read=25000,
        rows_written=25000,
        metrics={
            "bytes_transferred": 20 * 1024 * 1024,  # 20 MB
            "throughput_mb_sec": 4.0,
            "rejected_rows": 0
        },
        started_at=datetime.now(timezone.utc) - timedelta(minutes=8),
        ended_at=datetime.now(timezone.utc) - timedelta(minutes=7)
    )

    act2 = ActivityRun(
        id=str(uuid.uuid4()),
        pipeline_run_id=run.id,
        activity_id="act_customers_bronze",
        activity_name="Copy_Customers_Bronze",
        activity_type="CopyData",
        status="Succeeded",
        duration_seconds=7.5,
        rows_read=25000,
        rows_written=25000,
        metrics={
            "bytes_transferred": 45 * 1024 * 1024,  # 45 MB
            "throughput_mb_sec": 6.0,
            "rejected_rows": 5
        },
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ended_at=datetime.now(timezone.utc)
    )

    db_session.add_all([act1, act2])
    db_session.commit()

    perf = ObservabilityService.get_copy_data_performance(db_session, proj.id)
    assert perf.total_copy_activities >= 2
    assert perf.total_rows_transferred >= 50000
    assert perf.total_bytes_transferred >= 65 * 1024 * 1024
    assert perf.average_throughput_mb_sec > 0.0
    assert perf.peak_throughput_mb_sec >= 6.0
    assert perf.total_rejected_rows >= 5
    assert len(perf.recent_transfers) >= 2


def test_runtime_fleet_health_telemetry(db_session: Session, test_setup):
    """Verifies fleet-wide capacity, CPU/RAM telemetry, active tasks, and online status."""
    proj = test_setup["project"]

    rt1 = IntegrationRuntime(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Prod_Cloud_Cluster_01",
        runtime_type="Cloud",
        status="Online",
        cpu_cores=8,
        cpu_usage_pct=42.5,
        memory_total_bytes=16 * 1024 * 1024 * 1024, # 16 GB
        memory_used_bytes=6 * 1024 * 1024 * 1024,   # 6 GB
        concurrency_limit=8,
        active_task_count=2,
        agent_os="Linux",
        last_heartbeat_at=datetime.now(timezone.utc)
    )

    rt2 = IntegrationRuntime(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="OnPrem_SelfHosted_Agent_01",
        runtime_type="SelfHosted",
        status="Offline",
        cpu_cores=4,
        cpu_usage_pct=10.0,
        memory_total_bytes=8 * 1024 * 1024 * 1024,
        memory_used_bytes=1 * 1024 * 1024 * 1024,
        concurrency_limit=4,
        active_task_count=0,
        agent_os="Windows",
        last_heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=15)
    )

    db_session.add_all([rt1, rt2])
    db_session.commit()

    fleet = ObservabilityService.get_runtime_fleet_overview(db_session, proj.id)
    assert fleet.total_runtimes >= 2
    assert fleet.online_count >= 1
    assert fleet.offline_count >= 1
    assert fleet.fleet_cpu_usage_pct > 0.0
    assert fleet.fleet_memory_usage_pct > 0.0
    assert fleet.active_tasks >= 2
    assert fleet.total_concurrency_capacity >= 12
    assert len(fleet.runtimes) >= 2


def test_failure_diagnostics_and_error_clustering(db_session: Session, test_setup):
    """Verifies clustering of recurring failure patterns and root cause diagnostics."""
    proj = test_setup["project"]
    pipe = test_setup["pipeline"]

    run_fail = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipe.id,
        status="Failed",
        duration_seconds=3.0,
        error_summary="psycopg2.OperationalError: Connection timed out to host prod-db.internal:5432",
        started_at=datetime.now(timezone.utc)
    )
    db_session.add(run_fail)
    db_session.flush()

    act_fail1 = ActivityRun(
        id=str(uuid.uuid4()),
        pipeline_run_id=run_fail.id,
        activity_id="act_fail_1",
        activity_name="Extract_SQL",
        activity_type="CopyData",
        status="Failed",
        error_message="psycopg2.OperationalError: Connection timed out to host prod-db.internal:5432",
        started_at=datetime.now(timezone.utc)
    )

    act_fail2 = ActivityRun(
        id=str(uuid.uuid4()),
        pipeline_run_id=run_fail.id,
        activity_id="act_fail_2",
        activity_name="Write_S3",
        activity_type="CopyData",
        status="Failed",
        error_message="botocore.exceptions.ClientError: An error occurred (403 AccessDenied) when calling PutObject",
        started_at=datetime.now(timezone.utc)
    )

    act_fail3 = ActivityRun(
        id=str(uuid.uuid4()),
        pipeline_run_id=run_fail.id,
        activity_id="act_fail_3",
        activity_name="Validate_Schema",
        activity_type="Script",
        status="Failed",
        error_message="SchemaDriftError: Column 'country_code' not found in destination table schema",
        started_at=datetime.now(timezone.utc)
    )

    db_session.add_all([act_fail1, act_fail2, act_fail3])
    db_session.commit()

    diag = ObservabilityService.get_failure_clustering(db_session, proj.id)
    assert diag.total_failures >= 1
    assert len(diag.clusters) >= 2

    cat_names = [c.error_category for c in diag.clusters]
    assert any("Timeout" in cat for cat in cat_names)
    assert any("Authentication" in cat or "Access" in cat for cat in cat_names)

    timeout_cluster = next(c for c in diag.clusters if "Timeout" in c.error_category)
    assert timeout_cluster.suggested_remediation is not None
    assert "firewall" in timeout_cluster.suggested_remediation.lower() or "timeout" in timeout_cluster.suggested_remediation.lower()


def test_multichannel_alert_dispatch_and_cooldown_suppression(db_session: Session, test_setup):
    """Verifies Microsoft Teams/Email formatting, alert firing, and cooldown deduplication."""
    proj = test_setup["project"]
    pipe = test_setup["pipeline"]

    # 1. Create Alert Rule with 10 minute cooldown
    rule = AlertRule(
        id=str(uuid.uuid4()),
        name="Critical_Failure_Alert",
        target_type="Pipeline",
        pipeline_id=pipe.id,
        condition_type="OnFailure",
        action_type="Teams",
        action_config={"webhook_url": "https://outlook.office.com/webhook/test-mock"},
        cooldown_minutes=10,
        is_enabled=True
    )
    db_session.add(rule)
    db_session.commit()

    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipe.id,
        status="Failed",
        error_summary="Fatal memory allocation failure",
        started_at=datetime.now(timezone.utc)
    )
    db_session.add(run)
    db_session.commit()

    # 2. First trigger: Must generate alert event
    events1 = AlertEngine.evaluate_pipeline_run(run, db_session)
    assert len(events1) >= 1
    ev = events1[0]
    assert ev.severity == "Critical"
    assert ev.status in ["Delivered", "Failed"]  # delivered / simulated

    # 3. Second trigger within cooldown: Must be suppressed
    events2 = AlertEngine.evaluate_pipeline_run(run, db_session)
    assert len(events2) == 0  # suppressed due to cooldown!

    # 4. Runtime Offline alert rule
    rt_rule = AlertRule(
        id=str(uuid.uuid4()),
        name="Runtime_Agent_Offline_Alert",
        target_type="Runtime",
        condition_type="RuntimeOffline",
        action_type="Email",
        action_config={"recipients": ["ops@dataforge.internal"], "smtp_host": "localhost"},
        cooldown_minutes=5,
        is_enabled=True
    )
    db_session.add(rt_rule)
    db_session.commit()

    offline_rt = IntegrationRuntime(
        id=str(uuid.uuid4()),
        name="Unresponsive_Worker",
        runtime_type="SelfHosted",
        status="Offline",
        last_heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=2)
    )
    db_session.add(offline_rt)
    db_session.commit()

    rt_event = AlertEngine.evaluate_runtime_offline(offline_rt, db_session)
    assert rt_event is not None
    assert rt_event.severity == "Critical"
    assert "Offline" in rt_event.title


def test_opentelemetry_distributed_trace_generation(db_session: Session, test_setup):
    """Verifies W3C traceparent conformity and root/child span hierarchy for OpenTelemetry."""
    pipe = test_setup["pipeline"]

    run = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipe.id,
        status="Succeeded",
        duration_seconds=15.0,
        total_rows_written=10000,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=15),
        ended_at=datetime.now(timezone.utc)
    )
    db_session.add(run)
    db_session.flush()

    act = ActivityRun(
        id=str(uuid.uuid4()),
        pipeline_run_id=run.id,
        activity_id="act_transform_stage",
        activity_name="ETL_Transform_Stage",
        activity_type="CopyData",
        status="Succeeded",
        duration_seconds=10.0,
        rows_read=10000,
        rows_written=10000,
        metrics={"partition_count": 4},
        started_at=datetime.now(timezone.utc) - timedelta(seconds=12),
        ended_at=datetime.now(timezone.utc) - timedelta(seconds=2)
    )
    db_session.add(act)
    db_session.commit()

    trace = ObservabilityService.export_opentelemetry_trace(db_session, run.id)
    assert len(trace.trace_id) == 32
    assert len(trace.spans) == 2

    # Root span
    root = next(s for s in trace.spans if s.parent_span_id is None)
    assert root.kind == "SERVER"
    assert "Pipeline:" in root.name
    assert root.attributes["dataforge.pipeline.id"] == pipe.id

    # Child span
    child = next(s for s in trace.spans if s.parent_span_id == root.span_id)
    assert child.kind == "INTERNAL"
    assert "Activity: ETL_Transform_Stage" in child.name
    assert child.attributes["dataforge.activity.type"] == "CopyData"
    assert child.attributes["partition_count"] == 4


def test_prometheus_metrics_export_endpoints(test_setup):
    """Verifies standard Prometheus scraping text export format."""
    client: TestClient = test_setup["client"]

    # 1. Root /metrics
    res_root = client.get("/metrics")
    assert res_root.status_code == 200
    assert "text/plain" in res_root.headers.get("content-type", "")
    content = res_root.text
    assert "dataforge_pipeline_runs_total" in content
    assert "dataforge_copy_data_throughput_mb_sec" in content
    assert "dataforge_runtime_fleet_agents_total" in content

    # 2. API /api/v1/observability/metrics
    res_api = client.get("/api/v1/observability/metrics")
    assert res_api.status_code == 200
    assert "dataforge_pipeline_runs_total" in res_api.text


def test_observability_rest_api_endpoints(test_setup):
    """Verifies all FastAPI endpoints under /api/v1/observability."""
    client: TestClient = test_setup["client"]
    proj = test_setup["project"]
    pipe = test_setup["pipeline"]

    # 1. Overview endpoint
    res_overview = client.get(f"/api/v1/observability/overview?project_id={proj.id}")
    assert res_overview.status_code == 200
    ov = res_overview.json()
    assert "copy_performance" in ov
    assert "fleet_overview" in ov
    assert "failure_diagnostics" in ov

    # 2. Copy Data performance endpoint
    res_copy = client.get(f"/api/v1/observability/copy-performance?project_id={proj.id}&limit=50")
    assert res_copy.status_code == 200
    cp = res_copy.json()
    assert "average_throughput_mb_sec" in cp
    assert "throughput_trend" in cp

    # 3. Fleet Health endpoint
    res_fleet = client.get(f"/api/v1/observability/fleet-health?project_id={proj.id}")
    assert res_fleet.status_code == 200
    fh = res_fleet.json()
    assert "fleet_cpu_usage_pct" in fh
    assert "fleet_memory_usage_pct" in fh

    # 4. Failure diagnostics endpoint
    res_fail = client.get(f"/api/v1/observability/failure-diagnostics?project_id={proj.id}&days=7")
    assert res_fail.status_code == 200
    fd = res_fail.json()
    assert "clusters" in fd

    # 5. OpenTelemetry trace endpoint
    # First get a valid run id
    db = SessionLocal()
    run = db.query(PipelineRun).first()
    db.close()
    if run:
        res_trace = client.get(f"/api/v1/observability/traces/{run.id}")
        assert res_trace.status_code == 200
        tr = res_trace.json()
        assert "trace_id" in tr
        assert "spans" in tr
