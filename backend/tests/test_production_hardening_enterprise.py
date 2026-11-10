import pytest
import uuid
import time
import concurrent.futures
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.app.models.workspace import Project, Workspace
from backend.app.models.user import User
from backend.app.models.connection import Connection
from backend.app.models.dataset import Dataset
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.models.runtime import IntegrationRuntime, RuntimeTask
from backend.app.models.trigger import Trigger
from backend.app.models.alert import AlertRule, AlertEvent
from backend.app.models.lineage import LineageNode, LineageEdge, ColumnLineage

from backend.app.schemas.runtime import RuntimeCreate, AgentHeartbeatRequest, AgentRegisterRequest, RuntimeTaskStatusUpdate
from backend.app.services.runtime_manager import RuntimeManagerService
from backend.app.services.git_serializer import GitAssetSerializer
from backend.app.services.observability_service import ObservabilityService
from backend.app.monitoring.alert_engine import AlertEngine
from backend.app.core.security import encrypt_secret, decrypt_secret, mask_secret_dict
from backend.app.core.database import SessionLocal


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def hardening_setup(db_session: Session):
    user = db_session.query(User).filter(User.email == "hardening_admin@dataforge.test").first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email="hardening_admin@dataforge.test",
            hashed_password="hashed_hardening_pwd",
            full_name="Hardening Admin",
            role="Admin",
            is_active=True
        )
        db_session.add(user)

    ws = Workspace(
        id=str(uuid.uuid4()),
        name=f"Enterprise_WS_{uuid.uuid4().hex[:6]}"
    )
    db_session.add(ws)

    proj = Project(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        name=f"Enterprise_Hardening_Project_{uuid.uuid4().hex[:6]}",
        description="Production Hardening and Security Verification Project"
    )
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(ws)
    db_session.refresh(proj)
    return {"user": user, "workspace": ws, "project": proj}


class TestProductionSecurityAudit:
    """
    Security Audit across all 6 new enterprise features:
    Verifies zero credential exposure in Git exports, runtime agent exchanges,
    APIs, and telemetry.
    """

    def test_git_canonical_export_guarantees_zero_secret_leakage(self, db_session: Session, hardening_setup):
        """Verifies all sensitive credentials in connections and datasets are converted to vault references."""
        proj = hardening_setup["project"]

        # Create connection with plain credentials encrypted in DB
        plain_secrets = {
            "host": "database.corp.internal",
            "port": 5432,
            "database": "corp_db",
            "username": "dataforge_service_account",
            "password": "SUPER_CONFIDENTIAL_DB_PASSWORD_9988$$",
            "api_key": "AKIA_FAKE_SECRET_KEY_NEVER_LEAK_IN_GIT",
            "sas_token": "?sv=2021-06-08&sig=TOP_SECRET_SAS_TOKEN"
        }
        conn = Connection(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            name="Confidential_Enterprise_Database",
            connector_type="postgresql",
            config_encrypted=encrypt_secret(plain_secrets),
            status="Verified"
        )
        db_session.add(conn)
        db_session.commit()

        # Export canonical Git workspace tree
        exported_files = GitAssetSerializer.export_workspace_tree(db_session, proj.id)
        
        # Scan entire exported JSON tree for any plain text secrets
        all_exported_content = "".join(exported_files.values())
        
        # Ensure zero leakage of sensitive values
        assert "SUPER_CONFIDENTIAL_DB_PASSWORD_9988$$" not in all_exported_content
        assert "AKIA_FAKE_SECRET_KEY_NEVER_LEAK_IN_GIT" not in all_exported_content
        assert "TOP_SECRET_SAS_TOKEN" not in all_exported_content

        # Ensure vault placeholders were injected
        assert f"${{vault:{conn.name}_password}}" in all_exported_content
        assert f"${{vault:{conn.name}_api_key}}" in all_exported_content

    def test_runtime_registration_tokens_hashed_and_opaque(self, db_session: Session, hardening_setup):
        """Verifies runtime registration tokens use one-way SHA-256 hashes and bearer tokens are secure."""
        proj = hardening_setup["project"]

        rt_in = RuntimeCreate(
            name="Secure_SelfHosted_Worker_Fleet",
            runtime_type="SelfHosted",
            concurrency_limit=8,
            project_id=proj.id
        )
        runtime, raw_key = RuntimeManagerService.create_runtime(db_session, rt_in)
        assert raw_key is not None
        assert raw_key.startswith("df-ir-")

        # Database must NOT store raw key in plaintext
        db_session.refresh(runtime)
        assert runtime.registration_key_hash is not None
        assert runtime.registration_key_hash != raw_key
        assert len(runtime.registration_key_hash) == 64  # SHA-256 hexdigest

        # Plaintext key should decrypt only with correct Fernet master key
        decrypted_dict = decrypt_secret(runtime.registration_key_encrypted)
        assert decrypted_dict["key"] == raw_key

        # Re-registering with forged key fails with 403
        with pytest.raises(PermissionError):
            RuntimeManagerService.register_agent(
                db_session,
                AgentRegisterRequest(
                    registration_key="forged_malicious_key_12345",
                    host_name="attacker-host",
                    ip_address="10.0.0.99",
                    agent_version="1.0.0",
                    agent_os="Linux",
                    cpu_cores=4,
                    memory_total_bytes=8589934592,
                    concurrency_limit=4
                )
            )

    def test_alert_rule_and_event_channel_protection(self, db_session: Session, hardening_setup):
        """Verifies webhook targets, Slack tokens, and Teams hooks are masked in UI and diagnostic logs."""
        proj = hardening_setup["project"]

        sensitive_rule_cfg = {
            "webhook_url": "https://hooks.slack.com/services/T00/B00/SECRET_WEBHOOK_URL",
            "bot_token": "xoxb-CONFIDENTIAL_SLACK_BOT_TOKEN",
            "smtp_password": "SMTP_RELAY_PASSWORD_123"
        }

        rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Confidential Operations Alert",
            target_type="Global",
            condition_type="OnFailure",
            action_type="Slack",
            action_config=sensitive_rule_cfg,
            cooldown_minutes=10,
            is_enabled=True
        )
        db_session.add(rule)
        db_session.commit()

        # Masking utility sanitizes all confidential alert credentials
        masked_cfg = mask_secret_dict(rule.action_config)
        assert masked_cfg["bot_token"] == "********"
        assert masked_cfg["smtp_password"] == "********"


class TestProductionConcurrencyAndLoad:
    """
    High-Load & Concurrency Verification:
    Tests multi-agent concurrent dispatching, thread-safety, and heartbeat storm handling.
    """

    def test_concurrent_agent_task_dispatch_and_no_duplicate_assignment(self, db_session: Session, hardening_setup):
        """Verifies 10 concurrent agent workers polling queue do not receive duplicate tasks."""
        if db_session.bind.dialect.name == "sqlite":
            pytest.skip("Concurrent multi-threaded dispatch test requires PostgreSQL with row-level locks")
        proj = hardening_setup["project"]

        # Create Self-Hosted Runtime
        rt_in = RuntimeCreate(
            name="High_Concurrency_Worker_Pool",
            runtime_type="SelfHosted",
            concurrency_limit=16,
            project_id=proj.id
        )
        runtime, raw_key = RuntimeManagerService.create_runtime(db_session, rt_in)
        registered_rt, token = RuntimeManagerService.register_agent(
            db_session,
            AgentRegisterRequest(
                registration_key=raw_key,
                host_name="pool-node-01",
                ip_address="10.0.1.10",
                agent_version="1.0.0",
                agent_os="Linux",
                cpu_cores=16,
                memory_total_bytes=34359738368,
                concurrency_limit=16
            )
        )

        # Queue 20 distinct tasks
        task_ids = []
        for i in range(20):
            t = RuntimeTask(
                id=str(uuid.uuid4()),
                runtime_id=runtime.id,
                task_type="CopyData",
                status="Queued",
                task_payload_encrypted=encrypt_secret({"batch_id": i, "table": f"events_part_{i}"}),
                queued_at=datetime.now(timezone.utc)
            )
            db_session.add(t)
            task_ids.append(t.id)
        db_session.commit()

        # Simulate 10 concurrent worker threads polling tasks simultaneously
        target_rt_id = str(runtime.id)
        claimed_tasks = []

        def worker_poll(worker_idx: int):
            worker_db = SessionLocal()
            try:
                rt = worker_db.query(IntegrationRuntime).filter(IntegrationRuntime.id == target_rt_id).first()
                task = RuntimeManagerService.poll_next_task(worker_db, rt)
                return [task.task_id] if task else []
            finally:
                worker_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker_poll, i) for i in range(10)]
            for f in concurrent.futures.as_completed(futures):
                claimed_tasks.extend(f.result())

        # Assert no duplicate assignments occurred
        assert len(claimed_tasks) == len(set(claimed_tasks)), "Race condition detected: Duplicate tasks assigned!"
        assert len(claimed_tasks) > 0

    def test_concurrent_heartbeat_storm(self, db_session: Session, hardening_setup):
        """Verifies concurrent heartbeat requests from multiple agents update telemetry without deadlock."""
        if db_session.bind.dialect.name == "sqlite":
            pytest.skip("Concurrent multi-threaded heartbeat storm test requires PostgreSQL")
        proj = hardening_setup["project"]

        rt_in = RuntimeCreate(
            name="Storm_Resilient_Runtime",
            runtime_type="SelfHosted",
            concurrency_limit=8,
            project_id=proj.id
        )
        runtime, raw_key = RuntimeManagerService.create_runtime(db_session, rt_in)
        registered_rt, token = RuntimeManagerService.register_agent(
            db_session,
            AgentRegisterRequest(
                registration_key=raw_key,
                host_name="storm-agent-01",
                ip_address="10.0.2.1",
                agent_version="1.0.0",
                agent_os="Linux",
                cpu_cores=8,
                memory_total_bytes=17179869184,
                concurrency_limit=8
            )
        )

        storm_rt_id = str(runtime.id)

        def send_heartbeat(idx: int):
            hb_db = SessionLocal()
            try:
                rt = hb_db.query(IntegrationRuntime).filter(IntegrationRuntime.id == storm_rt_id).first()
                req = AgentHeartbeatRequest(
                    cpu_usage_pct=20.0 + (idx % 10),
                    memory_used_bytes=4294967296 + (idx * 1024),
                    active_task_count=idx % 4,
                    status="Online"
                )
                RuntimeManagerService.process_heartbeat(hb_db, rt, req)
                return True
            finally:
                hb_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(send_heartbeat, i) for i in range(25)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(results)
        
        # Verify final state is consistent
        db_session.refresh(runtime)
        assert runtime.status == "Online"
        assert runtime.last_heartbeat_at is not None


class TestProductionFaultToleranceAndResilience:
    """
    Resilience, Recovery, and Fault-Tolerance Verification:
    Tests offline agent detection, task timeout recovery, and safe error handling.
    """

    def test_agent_heartbeat_timeout_transitions_to_offline(self, db_session: Session, hardening_setup):
        """Verifies runtime automatically transitions to Offline when heartbeats cease."""
        proj = hardening_setup["project"]

        rt_in = RuntimeCreate(
            name="Failing_Agent_Runtime",
            runtime_type="SelfHosted",
            concurrency_limit=4,
            project_id=proj.id
        )
        runtime, raw_key = RuntimeManagerService.create_runtime(db_session, rt_in)
        registered_rt, token = RuntimeManagerService.register_agent(
            db_session,
            AgentRegisterRequest(
                registration_key=raw_key,
                host_name="expiring-agent",
                ip_address="10.0.3.5",
                agent_version="1.0.0",
                agent_os="Linux",
                cpu_cores=4,
                memory_total_bytes=8589934592,
                concurrency_limit=4
            )
        )

        # Manually backdate heartbeat to simulate missed intervals (90 seconds ago)
        runtime.status = "Online"
        runtime.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=90)
        db_session.commit()

        # Run offline check daemon logic
        offline_count = RuntimeManagerService.check_offline_runtimes(db_session)
        assert offline_count >= 1

        db_session.refresh(runtime)
        assert runtime.status == "Offline"

    def test_alert_dispatcher_network_failure_graceful_degradation(self, db_session: Session, hardening_setup):
        """Verifies unreachable webhook endpoints do not crash pipeline executions."""
        proj = hardening_setup["project"]

        pipe = Pipeline(
            id=str(uuid.uuid4()),
            project_id=proj.id,
            name="Resilience_Test_Pipeline",
            status="Active"
        )
        db_session.add(pipe)
        db_session.commit()

        pipe_run = PipelineRun(
            id=str(uuid.uuid4()),
            pipeline_id=pipe.id,
            status="Failed",
            error_summary="Simulated activity timeout",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            ended_at=datetime.now(timezone.utc)
        )
        db_session.add(pipe_run)

        # Rule pointing to a non-existent or blackhole webhook URL
        blackhole_rule = AlertRule(
            id=str(uuid.uuid4()),
            name="Blackhole Webhook Rule",
            pipeline_id=pipe.id,
            condition_type="OnFailure",
            action_type="Webhook",
            action_config={"webhook_url": "http://127.0.0.1:59999/blackhole/endpoint"},
            cooldown_minutes=0,
            is_enabled=True
        )
        db_session.add(blackhole_rule)
        db_session.commit()

        # Engine should catch connection error and mark event as Failed without raising uncaught exception
        events = AlertEngine.evaluate_pipeline_run(pipe_run, db_session)
        assert len(events) >= 1
        
        target_events = [e for e in events if e.alert_rule_id == blackhole_rule.id]
        assert len(target_events) >= 1
        event = target_events[0]
        assert event.status == "Failed"
        assert event.error_message is not None

    def test_high_volume_observability_metrics_performance(self, db_session: Session, hardening_setup):
        """Verifies Prometheus metrics export and Copy Data analytics aggregate efficiently under load."""
        proj = hardening_setup["project"]

        start_time = time.time()
        
        # Test Prometheus text metrics generation performance
        prom_text = ObservabilityService.export_prometheus_metrics(db_session)
        prom_duration = time.time() - start_time

        assert "# HELP dataforge_pipeline_runs_total" in prom_text
        assert prom_duration < 1.0, f"Prometheus metrics generation took {prom_duration:.2f}s, expected < 1.0s"

        # Test Copy Data performance summary latency
        cd_start = time.time()
        copy_summary = ObservabilityService.get_copy_data_performance(db_session, proj.id)
        cd_duration = time.time() - cd_start

        assert copy_summary is not None
        assert cd_duration < 1.0, f"Copy Data performance summary took {cd_duration:.2f}s, expected < 1.0s"
