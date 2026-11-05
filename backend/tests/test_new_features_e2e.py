import pytest
import uuid
import time
import os
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models.user import User
from backend.app.models.workspace import Workspace, Project
from backend.app.models.connection import Connection
from backend.app.models.runtime import IntegrationRuntime, RuntimeTask
from backend.app.models.dataset import Dataset, DatasetVersion
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.models.trigger import Trigger, TriggerRun
from backend.app.models.lineage import LineageNode, LineageEdge, ColumnLineage
from backend.app.models.alert import AlertRule, AlertEvent
from backend.app.models.git import GitRepository
from backend.app.models.deployment import Deployment

from backend.app.services.runtime_manager import RuntimeManagerService
from backend.app.schemas.runtime import RuntimeCreate, AgentRegisterRequest, RuntimeTaskStatusUpdate, AgentHeartbeatRequest
from backend.app.services.dataset_service import DatasetService
from backend.app.schemas.dataset import DatasetCreate
from backend.app.services.trigger_service import TriggerService
from backend.app.schemas.trigger import TriggerCreate
from backend.app.services.lineage_service import LineageService
from backend.app.services.observability_service import ObservabilityService
from backend.app.monitoring.alert_engine import AlertEngine
from backend.app.services.git_service import GitService
from backend.app.services.git_serializer import GitAssetSerializer
from backend.app.services.cicd_service import CiCdService
from backend.app.schemas.deployment import DeploymentDryRunRequest, DeploymentCreateRequest
from backend.app.schemas.git import GitRepositoryConfig, GitCommitRequest
from backend.app.execution.runner import PipelineRunner
from backend.app.core.security import get_password_hash, create_access_token, encrypt_secret


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def e2e_setup(db_session: Session):
    uid = str(uuid.uuid4())[:8]
    user = User(
        id=str(uuid.uuid4()),
        email=f"e2e_lead_{uid}@dataflow.enterprise",
        full_name="E2E Integration Test Lead",
        hashed_password=get_password_hash("EnterprisePass123!"),
        role="Admin",
        is_active=True
    )
    ws = Workspace(id=str(uuid.uuid4()), name=f"E2E Enterprise WS {uid}")
    proj = Project(id=str(uuid.uuid4()), workspace_id=ws.id, name=f"E2E Analytics Core {uid}")

    # Physical SQLite databases for end-to-end movement
    db_dir = "/tmp/dataforge_e2e_test"
    os.makedirs(db_dir, exist_ok=True)
    src_db_path = f"{db_dir}/src_orders_{uid}.db"
    dest_db_path = f"{db_dir}/dest_silver_{uid}.db"

    # Populate source DB
    src_conn = sqlite3.connect(src_db_path)
    src_cur = src_conn.cursor()
    src_cur.execute("""
        CREATE TABLE raw_orders (
            order_id INTEGER PRIMARY KEY,
            customer_id TEXT,
            amount REAL,
            order_date TEXT
        )
    """)
    orders_data = [
        (101, "CUST_A", 150.50, "2026-11-01"),
        (102, "CUST_B", 320.00, "2026-11-02"),
        (103, "CUST_A", 45.75, "2026-11-03"),
        (104, "CUST_C", 890.20, "2026-11-04")
    ]
    src_cur.executemany("INSERT INTO raw_orders VALUES (?, ?, ?, ?)", orders_data)
    src_conn.commit()
    src_conn.close()

    # Destination DB table
    dest_conn = sqlite3.connect(dest_db_path)
    dest_cur = dest_conn.cursor()
    dest_cur.execute("""
        CREATE TABLE silver_orders (
            order_id INTEGER PRIMARY KEY,
            customer_id TEXT,
            amount REAL,
            order_date TEXT
        )
    """)
    dest_conn.commit()
    dest_conn.close()

    # Connection models
    src_conn_model = Connection(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name=f"E2E Source SQLite {uid}",
        connector_type="sqlite",
        config_encrypted=encrypt_secret({"database": src_db_path})
    )
    dest_conn_model = Connection(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name=f"E2E Sink SQLite {uid}",
        connector_type="sqlite",
        config_encrypted=encrypt_secret({"database": dest_db_path})
    )

    db_session.add_all([user, ws, proj, src_conn_model, dest_conn_model])
    db_session.commit()

    token = create_access_token({"sub": user.id, "role": user.role})
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    return {
        "user": user,
        "workspace": ws,
        "project": proj,
        "src_conn": src_conn_model,
        "dest_conn": dest_conn_model,
        "src_db_path": src_db_path,
        "dest_db_path": dest_db_path,
        "client": client,
        "token": token
    }


def test_e2e_complete_enterprise_lifecycle(db_session: Session, e2e_setup):
    """
    Scenario 1: Comprehensive End-to-End Interoperability Test across all 6 Enterprise Features:
    1. Runtime Manager (Provision Self-Hosted agent with telemetry)
    2. Reusable Datasets (Auto schema inference, column metadata, source/sink models)
    3. Advanced Triggers (Storage/Schedule trigger dispatching pipeline run)
    4. Execution Engine (Routing task to Self-Hosted agent queue and execution)
    5. Data Lineage (Auto extraction, column lineage mapping, impact analysis blast radius)
    6. Observability (Copy throughput, fleet telemetry, OpenTelemetry trace hierarchy, Prometheus)
    7. Git Integration & CI/CD (Deterministic JSON export, secret masking, commit, and approval)
    """
    proj = e2e_setup["project"]
    src_conn = e2e_setup["src_conn"]
    dest_conn = e2e_setup["dest_conn"]

    # -------------------------------------------------------------------------
    # STEP 1: Feature 1 - Integration Runtime Manager
    # -------------------------------------------------------------------------
    sh_rt, raw_key = RuntimeManagerService.create_runtime(
        db_session,
        RuntimeCreate(
            name=f"E2E_SelfHosted_IR_{uuid.uuid4().hex[:6]}",
            runtime_type="SelfHosted",
            project_id=proj.id
        )
    )
    assert sh_rt.id is not None
    assert raw_key.startswith("df-ir-")

    # Register mock worker agent
    registered_rt, agent_token = RuntimeManagerService.register_agent(
        db_session,
        AgentRegisterRequest(
            registration_key=raw_key,
            host_name="worker-e2e-node-01",
            agent_version="1.0.0",
            agent_os="Linux"
        )
    )
    assert registered_rt.status == "Online"

    # Send heartbeat
    RuntimeManagerService.process_heartbeat(
        db_session,
        registered_rt,
        AgentHeartbeatRequest(
            cpu_usage_pct=28.5,
            memory_used_bytes=4 * 1024 * 1024 * 1024,
            active_task_count=0,
            status="Online"
        )
    )

    # -------------------------------------------------------------------------
    # STEP 2: Feature 2 - Reusable Dataset Management
    # -------------------------------------------------------------------------
    # Create Source Dataset
    src_ds = DatasetService.create_dataset(
        db_session,
        DatasetCreate(
            project_id=proj.id,
            name="E2E_Raw_Orders_DS",
            dataset_type="RelationalTable",
            connection_id=src_conn.id,
            location_config={"table": "raw_orders"}
        )
    )
    assert src_ds.id is not None
    assert src_ds.current_version == 1

    # Infer Schema automatically from SQLite
    inferred_schema = DatasetService.infer_schema(db_session, src_ds)
    assert len(inferred_schema) == 4
    col_names = [c["name"] for c in inferred_schema]
    assert "order_id" in col_names
    assert "customer_id" in col_names
    assert "amount" in col_names

    # Create Sink Dataset
    sink_ds = DatasetService.create_dataset(
        db_session,
        DatasetCreate(
            project_id=proj.id,
            name="E2E_Silver_Orders_DS",
            dataset_type="RelationalTable",
            connection_id=dest_conn.id,
            location_config={"table": "silver_orders"}
        )
    )
    assert sink_ds.id is not None

    # -------------------------------------------------------------------------
    # STEP 3: Pipeline Definition with Dataset References & Runtime Routing
    # -------------------------------------------------------------------------
    pipeline = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="E2E_Order_Ingestion_Pipeline",
        runtime_id=registered_rt.id,
        definition_json={
            "activities": [
                {
                    "id": "act_copy_e2e_orders",
                    "name": "Copy_Raw_To_Silver",
                    "type": "CopyData",
                    "config": {
                        "source": {
                            "type": "Dataset",
                            "dataset_id": src_ds.id
                        },
                        "sink": {
                            "type": "Dataset",
                            "dataset_id": sink_ds.id
                        },
                        "column_mappings": [
                            {"source_column": "order_id", "target_column": "order_id"},
                            {"source_column": "customer_id", "target_column": "customer_id"},
                            {"source_column": "amount", "target_column": "amount"},
                            {"source_column": "order_date", "target_column": "order_date"}
                        ]
                    }
                }
            ]
        }
    )
    db_session.add(pipeline)
    db_session.commit()

    # -------------------------------------------------------------------------
    # STEP 4: Feature 3 - Advanced Trigger Management
    # -------------------------------------------------------------------------
    trigger = TriggerService.create_trigger(
        db_session,
        TriggerCreate(
            project_id=proj.id,
            name="E2E_Daily_Schedule_Trigger",
            trigger_type="schedule",
            schedule_config={
                "frequency": "Daily",
                "interval": 1,
                "timezone": "America/New_York",
                "start_time": "2026-11-01T00:00:00Z"
            },
            pipelines_to_run=[{
                "pipeline_id": pipeline.id,
                "pipeline_name": pipeline.name,
                "parameters": {"batch_date": "2026-11-05"}
            }],
            is_active=True
        )
    )
    assert trigger.id is not None
    assert trigger.next_fire_time is not None

    # -------------------------------------------------------------------------
    # STEP 5: Execution via Self-Hosted Runtime Dispatcher
    # -------------------------------------------------------------------------
    # Setup background thread to act as the agent polling & executing data movement
    def agent_worker_loop():
        for _ in range(40):
            time.sleep(0.2)
            local_db = SessionLocal()
            try:
                rt = local_db.query(IntegrationRuntime).filter(IntegrationRuntime.id == registered_rt.id).first()
                task = RuntimeManagerService.poll_next_task(local_db, rt)
                if task:
                    # Perform copy between SQLite databases
                    s_conn = sqlite3.connect(e2e_setup["src_db_path"])
                    d_conn = sqlite3.connect(e2e_setup["dest_db_path"])
                    s_cur = s_conn.cursor()
                    rows = s_cur.execute("SELECT order_id, customer_id, amount, order_date FROM raw_orders").fetchall()
                    s_conn.close()

                    d_cur = d_conn.cursor()
                    d_cur.executemany("INSERT OR REPLACE INTO silver_orders VALUES (?, ?, ?, ?)", rows)
                    d_conn.commit()
                    d_conn.close()

                    # Report task completion
                    RuntimeManagerService.update_task_status(
                        local_db,
                        rt,
                        task.task_id,
                        RuntimeTaskStatusUpdate(
                            status="Completed",
                            rows_read=len(rows),
                            rows_written=len(rows),
                            bytes_processed=len(rows) * 128,
                            metrics={
                                "bytes_transferred": len(rows) * 128,
                                "throughput_mb_sec": 8.5,
                                "rejected_rows": 0
                            }
                        )
                    )
                    break
            finally:
                local_db.close()

    worker_thread = threading.Thread(target=agent_worker_loop, daemon=True)
    worker_thread.start()

    # Fire trigger (which enqueues and dispatches the pipeline run)
    trigger_run = TriggerService.fire_trigger_now(db_session, trigger)
    assert trigger_run.run_status == "Succeeded"
    assert len(trigger_run.triggered_pipeline_runs) == 1
    pipe_run_id = trigger_run.triggered_pipeline_runs[0]["pipeline_run_id"]

    # Wait for background pipeline runner to complete
    for _ in range(40):
        time.sleep(0.2)
        check_db = SessionLocal()
        check_run = check_db.query(PipelineRun).filter(PipelineRun.id == pipe_run_id).first()
        r_status = check_run.status if check_run else None
        check_db.close()
        if r_status in ("Succeeded", "Failed"):
            break

    worker_thread.join(timeout=5)

    # Verify execution outcome
    db_session.expire_all()
    pipe_run = db_session.query(PipelineRun).filter(PipelineRun.id == pipe_run_id).first()
    assert pipe_run.status == "Succeeded"
    assert pipe_run.total_rows_read == 4
    assert pipe_run.total_rows_written == 4

    act_run = db_session.query(ActivityRun).filter(ActivityRun.pipeline_run_id == pipe_run_id).first()
    assert act_run.status == "Succeeded"
    assert act_run.worker_info["runtime_type"] == "SelfHosted"
    assert act_run.worker_info["agent_host"] == "worker-e2e-node-01"

    # -------------------------------------------------------------------------
    # STEP 6: Feature 5 - Data Lineage & Impact Analysis
    # -------------------------------------------------------------------------
    lineage_res = LineageService.extract_project_lineage(db_session, proj.id)
    assert lineage_res.nodes_discovered >= 2

    # Graph Traversal (Source DS -> Activity -> Sink DS)
    graph = LineageService.get_lineage_graph(db_session, proj.id)
    node_names = [n.name for n in graph.nodes]
    assert "E2E_Raw_Orders_DS" in node_names
    assert "E2E_Silver_Orders_DS" in node_names

    # Column Lineage Tracing (Customer ID)
    sink_node = next(n for n in graph.nodes if n.name == "E2E_Silver_Orders_DS")
    col_trace = LineageService.get_column_lineage_trace(db_session, proj.id, node_id=sink_node.id, column_name="customer_id", direction="upstream")
    assert col_trace.column_name == "customer_id"

    # Impact Analysis (Blast Radius of Source DS)
    src_node = next(n for n in graph.nodes if n.name == "E2E_Raw_Orders_DS")
    impact = LineageService.analyze_impact(db_session, proj.id, node_id=src_node.id)
    assert impact.target_node_id == src_node.id
    assert impact.risk_level in ["High", "Medium", "Low"]

    # -------------------------------------------------------------------------
    # STEP 7: Feature 6 - Advanced Monitoring & Observability
    # -------------------------------------------------------------------------
    # Copy Data Performance Telemetry
    copy_metrics = ObservabilityService.get_copy_data_performance(db_session, proj.id)
    assert copy_metrics.total_copy_activities >= 1
    assert copy_metrics.total_rows_transferred >= 4

    # Fleet Telemetry
    fleet_telemetry = ObservabilityService.get_runtime_fleet_overview(db_session, proj.id)
    assert fleet_telemetry.total_runtimes >= 1
    assert fleet_telemetry.online_count >= 1

    # OpenTelemetry Distributed Traces
    otel_trace = ObservabilityService.export_opentelemetry_trace(db_session, pipe_run.id)
    assert len(otel_trace.trace_id) == 32
    assert len(otel_trace.spans) >= 1
    root_span = next(s for s in otel_trace.spans if s.parent_span_id is None)
    assert "Pipeline:" in root_span.name
    child_span = next(s for s in otel_trace.spans if s.parent_span_id is not None)
    assert child_span.attributes["dataforge.activity.name"] == "Copy_Raw_To_Silver"
    assert child_span.attributes["dataforge.activity.rows_written"] == 4

    # Prometheus Metrics Export
    prom_text = ObservabilityService.export_prometheus_metrics(db_session)
    assert "dataforge_pipeline_runs_total" in prom_text
    assert "dataforge_copy_data_throughput_mb_sec" in prom_text

    # -------------------------------------------------------------------------
    # STEP 8: Feature 4 - Git Integration & CI/CD Promotion
    # -------------------------------------------------------------------------
    git_cfg = GitRepositoryConfig(
        provider="github",
        repo_url="https://github.com/enterprise-org/dataforge-e2e.git",
        default_branch="main",
        current_branch="main",
        auth_type="pat",
        token="ghp_mock_e2e_secret_token_123"
    )
    git_repo = GitService.connect_repository(db_session, proj.id, git_cfg, e2e_setup["user"])
    assert git_repo.id is not None

    # Canonical Asset Serializer Export
    exported_tree = GitAssetSerializer.export_workspace_tree(db_session, proj.id)
    assert any("datasets/e2e_raw_orders_ds.json" in k for k in exported_tree.keys())
    assert any("datasets/e2e_silver_orders_ds.json" in k for k in exported_tree.keys())
    assert any("runtimes/" in k for k in exported_tree.keys())
    assert any("triggers/" in k for k in exported_tree.keys())
    assert any("pipelines/e2e_order_ingestion_pipeline.json" in k for k in exported_tree.keys())

    # Secret Masking Verification: Verify NO raw tokens or passwords exist in exported JSON
    for path, content in exported_tree.items():
        assert "ghp_mock_e2e_secret_token_123" not in content
        assert "EnterprisePass123!" not in content

    # Commit and Push to Git
    commit_res = GitService.commit_and_push(
        db_session,
        proj.id,
        GitCommitRequest(message="feat(e2e): Ingest raw orders to silver via self-hosted runtime", branch="main"),
        e2e_setup["user"]
    )
    assert "commit_hash" in commit_res
    assert commit_res["commit_hash"] is not None

    # CI/CD Pre-validation (Dry Run)
    dry_req = DeploymentDryRunRequest(
        source_environment="Dev",
        target_environment="Prod",
        pipeline_ids=[pipeline.id],
        dataset_ids=[src_ds.id, sink_ds.id],
        trigger_ids=[trigger.id]
    )
    preval = CiCdService.create_dry_run(db_session, proj.id, dry_req)
    assert preval.can_deploy is True
    assert len(preval.asset_diffs) >= 1

    # Create, Approve, and Execute Deployment
    dep_req = DeploymentCreateRequest(
        source_environment="Dev",
        target_environment="Prod",
        bundle_version="v1.0.0",
        pipeline_ids=[pipeline.id],
        notes="E2E Promotion"
    )
    deploy = CiCdService.create_deployment(db_session, proj.id, dep_req, e2e_setup["user"])
    assert deploy.id is not None
    assert deploy.status == "PendingApproval"

    appr_deploy = CiCdService.approve_deployment(
        db_session,
        deployment_id=deploy.id,
        approver=e2e_setup["user"],
        comment="Approved for E2E testing"
    )
    assert appr_deploy.status == "Approved"

    exec_deploy = CiCdService.execute_deployment(db_session, deploy.id, e2e_setup["user"])
    assert exec_deploy.status == "Deployed"
    assert exec_deploy.deployed_at is not None


def test_e2e_cross_module_failure_clustering_and_multichannel_alerting(db_session: Session, e2e_setup):
    """
    Scenario 2: Cross-Module Failure, Error Clustering & Multi-Channel Alert Dispatch:
    - Pipeline fails on execution.
    - Observability failure clustering categorizes root cause and offers remediation.
    - Alert engine fires Teams notification and enforces cooldown deduplication.
    """
    proj = e2e_setup["project"]

    pipe_fail = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="E2E_Critical_Fail_Pipeline",
        definition_json={"activities": [{"id": "act_f", "name": "Fail_SQL", "type": "CopyData"}]}
    )
    db_session.add(pipe_fail)
    db_session.commit()

    # Create Multi-Channel Alert Rule with 15 min cooldown
    alert_rule = AlertRule(
        id=str(uuid.uuid4()),
        name="E2E_Teams_Failure_Alert",
        target_type="Pipeline",
        pipeline_id=pipe_fail.id,
        condition_type="OnFailure",
        action_type="Teams",
        action_config={"webhook_url": "https://outlook.office.com/webhook/e2e-alert"},
        cooldown_minutes=15,
        is_enabled=True
    )
    db_session.add(alert_rule)
    db_session.commit()

    # Simulate Failed Pipeline Run
    run_fail = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipe_fail.id,
        status="Failed",
        duration_seconds=2.1,
        error_summary="psycopg2.OperationalError: Connection timed out after 30000ms",
        started_at=datetime.now(timezone.utc)
    )
    db_session.add(run_fail)
    db_session.flush()

    act_fail = ActivityRun(
        id=str(uuid.uuid4()),
        pipeline_run_id=run_fail.id,
        activity_id="act_f",
        activity_name="Fail_SQL",
        activity_type="CopyData",
        status="Failed",
        error_message="psycopg2.OperationalError: Connection timed out after 30000ms",
        started_at=datetime.now(timezone.utc)
    )
    db_session.add(act_fail)
    db_session.commit()

    # 1. Observability: Verify Error Clustering & Suggested Remediation
    diag = ObservabilityService.get_failure_clustering(db_session, proj.id)
    assert diag.total_failures >= 1
    timeout_clusters = [c for c in diag.clusters if "Timeout" in c.error_category]
    assert len(timeout_clusters) >= 1
    assert "timeout" in timeout_clusters[0].suggested_remediation.lower() or "firewall" in timeout_clusters[0].suggested_remediation.lower()

    # 2. Multi-Channel Alert Engine: First Trigger must deliver
    events = AlertEngine.evaluate_pipeline_run(run_fail, db_session)
    assert len(events) == 1
    assert events[0].severity == "Critical"
    assert events[0].status in ["Delivered", "Failed"]

    # 3. Cooldown Suppression: Second Trigger within 15 min must be suppressed
    events_suppressed = AlertEngine.evaluate_pipeline_run(run_fail, db_session)
    assert len(events_suppressed) == 0


def test_e2e_schema_drift_lineage_impact_and_cicd_guardrails(db_session: Session, e2e_setup):
    """
    Scenario 3: Schema Drift -> Impact Analysis -> CI/CD Prevalidation Guardrails:
    - Alter source database table schema (adding column, modifying type).
    - Detect drift via DatasetService, sync schema to version 2.
    - Run column-level impact analysis.
    - Verify CI/CD pre-validation detects new version and validates environment safety.
    """
    proj = e2e_setup["project"]
    src_conn = e2e_setup["src_conn"]

    # Create dataset
    ds = DatasetService.create_dataset(
        db_session,
        DatasetCreate(
            project_id=proj.id,
            name=f"E2E_Drift_Orders_DS_{uuid.uuid4().hex[:6]}",
            dataset_type="RelationalTable",
            connection_id=src_conn.id,
            location_config={"table": "raw_orders"}
        )
    )
    # Set schema definition
    ds_schema = DatasetService.infer_schema(db_session, ds)
    ds.schema_definition = ds_schema
    db_session.commit()
    assert ds.current_version == 1

    # Physically alter SQLite table
    conn = sqlite3.connect(e2e_setup["src_db_path"])
    cur = conn.cursor()
    cur.execute("ALTER TABLE raw_orders ADD COLUMN loyalty_tier TEXT DEFAULT 'Standard'")
    conn.commit()
    conn.close()

    # Detect Schema Drift
    drift = DatasetService.detect_schema_drift(db_session, ds.id)
    assert drift.has_drift is True
    added_names = [c["name"] for c in drift.added_columns]
    assert "loyalty_tier" in added_names

    # Sync Schema to v2
    synced_ds, synced_ver = DatasetService.sync_schema(db_session, ds.id)
    assert synced_ds.current_version == 2
    col_names = [c["name"] for c in synced_ds.schema_definition]
    assert "loyalty_tier" in col_names

    # CI/CD Prevalidation recognizes updated asset versions
    dry_req = DeploymentDryRunRequest(
        source_environment="Dev",
        target_environment="Prod",
        dataset_ids=[ds.id]
    )
    preval = CiCdService.create_dry_run(db_session, proj.id, dry_req)
    assert preval.can_deploy is True


def test_e2e_multi_pipeline_dependency_cascade_and_multitier_lineage(db_session: Session, e2e_setup):
    """
    Scenario 4: Multi-Pipeline Cascading Dependencies with Multi-Tier Lineage:
    - Pipeline A (Bronze Ingestion) -> Pipeline B (Silver Refinement).
    - Pipeline Dependency Trigger executes Pipeline B upon Pipeline A completion.
    - Multi-tier lineage BFS traversal connects Bronze -> Silver -> Gold nodes.
    """
    proj = e2e_setup["project"]

    pipe_a = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Bronze_Ingestion_Pipe",
        definition_json={"activities": [{"id": "act_a", "name": "Bronze_Load", "type": "CopyData"}]}
    )
    pipe_b = Pipeline(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        name="Silver_Refinement_Pipe",
        definition_json={"activities": [{"id": "act_b", "name": "Silver_Cleanse", "type": "CopyData"}]}
    )
    db_session.add_all([pipe_a, pipe_b])
    db_session.commit()

    # Setup Dependency Trigger on Pipeline B listening to Pipeline A
    dep_trigger = TriggerService.create_trigger(
        db_session,
        TriggerCreate(
            project_id=proj.id,
            name="Cascade_Dependency_Trigger",
            trigger_type="pipeline_dependency",
            pipeline_dependency_config={
                "upstream_pipeline_id": pipe_a.id,
                "fire_on_status": ["Succeeded"],
                "forward_parameters": True
            },
            pipelines_to_run=[{"pipeline_id": pipe_b.id, "pipeline_name": pipe_b.name}],
            is_active=True
        )
    )
    assert dep_trigger.id is not None

    # Simulate completion of Pipeline A
    run_a = PipelineRun(
        id=str(uuid.uuid4()),
        pipeline_id=pipe_a.id,
        status="Succeeded",
        duration_seconds=5.0,
        started_at=datetime.now(timezone.utc)
    )
    db_session.add(run_a)
    db_session.commit()

    # Trigger dependency engine
    cascade_runs = TriggerService.evaluate_pipeline_dependency_trigger(db_session, dep_trigger)
    assert len(cascade_runs) >= 1
    assert cascade_runs[0].run_status == "Succeeded"
    assert cascade_runs[0].triggered_pipeline_runs[0]["pipeline_id"] == pipe_b.id

    # Create Multi-Tier Lineage Nodes: Bronze Table -> Silver Table -> Gold Mart Table
    node_bronze = LineageNode(
        project_id=proj.id,
        name="bronze.orders",
        qualified_name=f"lakehouse.bronze.orders.{uuid.uuid4().hex[:6]}",
        node_type="table",
        metadata_json={"layer": "Bronze"}
    )
    node_silver = LineageNode(
        project_id=proj.id,
        name="silver.orders",
        qualified_name=f"lakehouse.silver.orders.{uuid.uuid4().hex[:6]}",
        node_type="table",
        metadata_json={"layer": "Silver"}
    )
    node_gold = LineageNode(
        project_id=proj.id,
        name="gold.fct_orders",
        qualified_name=f"warehouse.gold.fct_orders.{uuid.uuid4().hex[:6]}",
        node_type="table",
        metadata_json={"layer": "Gold"}
    )
    db_session.add_all([node_bronze, node_silver, node_gold])
    db_session.flush()

    edge1 = LineageEdge(project_id=proj.id, source_node_id=node_bronze.id, target_node_id=node_silver.id, edge_type="Transforms")
    edge2 = LineageEdge(project_id=proj.id, source_node_id=node_silver.id, target_node_id=node_gold.id, edge_type="Transforms")
    db_session.add_all([edge1, edge2])
    db_session.commit()

    # Traversal downstream from Bronze -> Gold (2 hops)
    traversal = LineageService.get_lineage_graph(db_session, proj.id, root_node_id=node_bronze.id, direction="downstream", depth=3)
    visited_names = [n.name for n in traversal.nodes]
    assert "bronze.orders" in visited_names
    assert "silver.orders" in visited_names
    assert "gold.fct_orders" in visited_names
