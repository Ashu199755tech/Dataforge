import pytest
import time
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.models.runtime import IntegrationRuntime, RuntimeTask
from backend.app.models.pipeline import Pipeline
from backend.app.models.workspace import Project
from backend.app.models.user import User
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.core.security import create_access_token
from backend.app.schemas.runtime import (
    RuntimeCreate,
    RuntimeUpdate,
    AgentRegisterRequest,
    AgentHeartbeatRequest,
    RuntimeTaskStatusUpdate
)
from backend.app.services.runtime_manager import RuntimeManagerService
from backend.app.execution.runner import PipelineRunner


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


def test_runtime_creation_and_registration_key(db_session: Session):
    """Test creating Cloud, SelfHosted, and LocalDev runtimes and key generation."""
    # 1. Cloud Runtime
    rt_cloud_in = RuntimeCreate(
        name=f"test-cloud-{uuid.uuid4().hex[:6]}",
        runtime_type="Cloud",
        description="Managed cloud runtime",
        concurrency_limit=10
    )
    cloud_rt, key = RuntimeManagerService.create_runtime(db_session, rt_cloud_in)
    assert cloud_rt.id is not None
    assert cloud_rt.status == "Online"
    assert key is None
    assert cloud_rt.registration_key_encrypted is None

    # 2. Self-Hosted Runtime
    rt_sh_in = RuntimeCreate(
        name=f"test-sh-{uuid.uuid4().hex[:6]}",
        runtime_type="SelfHosted",
        description="On-premises private gateway",
        concurrency_limit=5
    )
    sh_rt, raw_key = RuntimeManagerService.create_runtime(db_session, rt_sh_in)
    assert sh_rt.id is not None
    assert sh_rt.status == "Registering"
    assert raw_key is not None
    assert raw_key.startswith("df-ir-")
    assert sh_rt.registration_key_encrypted is not None
    assert sh_rt.registration_key_hash is not None

    # Verify decrypt key matches
    decrypted_key = RuntimeManagerService.get_registration_key(sh_rt)
    assert decrypted_key == raw_key


def test_agent_registration_lifecycle(db_session: Session):
    """Test full agent registration flow with valid and invalid registration keys."""
    # Create Self-Hosted runtime
    sh_rt, raw_key = RuntimeManagerService.create_runtime(
        db_session,
        RuntimeCreate(name=f"sh-reg-{uuid.uuid4().hex[:6]}", runtime_type="SelfHosted")
    )

    # 1. Reject invalid key
    with pytest.raises(PermissionError):
        RuntimeManagerService.register_agent(
            db_session,
            AgentRegisterRequest(
                registration_key="invalid-bogus-key",
                host_name="test-box",
                agent_version="1.0.0",
                agent_os="Linux"
            )
        )

    # 2. Accept valid key
    reg_req = AgentRegisterRequest(
        registration_key=raw_key,
        host_name="edge-node-01",
        agent_version="1.0.0",
        agent_os="Linux",
        cpu_cores=8,
        memory_total_bytes=17179869184
    )
    registered_rt, token = RuntimeManagerService.register_agent(db_session, reg_req)
    assert registered_rt.id == sh_rt.id
    assert registered_rt.status == "Online"
    assert registered_rt.host_name == "edge-node-01"
    assert registered_rt.cpu_cores == 8
    assert token.startswith("df-session-")

    # 3. Authenticate agent using session token
    auth_rt = RuntimeManagerService.authenticate_agent(db_session, token)
    assert auth_rt.id == sh_rt.id

    # 4. Reject bogus session token
    with pytest.raises(PermissionError):
        RuntimeManagerService.authenticate_agent(db_session, "df-session-fake-token")


def test_agent_heartbeat_and_offline_detection(db_session: Session):
    """Test agent heartbeat updates telemetry and stale heartbeats mark runtime Offline."""
    sh_rt, raw_key = RuntimeManagerService.create_runtime(
        db_session,
        RuntimeCreate(name=f"sh-hb-{uuid.uuid4().hex[:6]}", runtime_type="SelfHosted")
    )
    reg_req = AgentRegisterRequest(
        registration_key=raw_key,
        host_name="worker-linux",
        agent_version="1.0.0",
        agent_os="Linux"
    )
    registered_rt, token = RuntimeManagerService.register_agent(db_session, reg_req)

    # Send heartbeat
    hb_req = AgentHeartbeatRequest(
        cpu_usage_pct=42.5,
        memory_used_bytes=4294967296,
        active_task_count=2,
        status="Online"
    )
    pending = RuntimeManagerService.process_heartbeat(db_session, registered_rt, hb_req)
    assert pending == 0
    assert registered_rt.cpu_usage_pct == 42.5
    assert registered_rt.memory_used_bytes == 4294967296
    assert registered_rt.active_task_count == 2
    assert registered_rt.status == "Online"

    # Simulate heartbeat timeout
    registered_rt.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db_session.commit()

    offline_count = RuntimeManagerService.check_offline_runtimes(db_session)
    assert offline_count >= 1

    db_session.refresh(registered_rt)
    assert registered_rt.status == "Offline"


def test_runtime_task_queueing_and_polling(db_session: Session):
    """Test enqueuing encrypted tasks, agent polling, and status synchronization."""
    sh_rt, raw_key = RuntimeManagerService.create_runtime(
        db_session,
        RuntimeCreate(name=f"sh-task-{uuid.uuid4().hex[:6]}", runtime_type="SelfHosted", concurrency_limit=2)
    )
    registered_rt, token = RuntimeManagerService.register_agent(
        db_session,
        AgentRegisterRequest(registration_key=raw_key, host_name="node-task", agent_version="1.0.0", agent_os="Linux")
    )

    # Enqueue task
    task_payload = {
        "activity_name": "CopyFromPostgresToS3",
        "source": "PostgreSQL",
        "sink": "S3",
        "rows_to_transfer": 500
    }
    task = RuntimeManagerService.enqueue_task(
        db=db_session,
        runtime_id=registered_rt.id,
        task_type="CopyData",
        payload=task_payload
    )
    assert task.id is not None
    assert task.status == "Queued"

    # Agent polls next task
    polled_task = RuntimeManagerService.poll_next_task(db_session, registered_rt)
    assert polled_task is not None
    assert polled_task.task_id == task.id
    assert polled_task.task_type == "CopyData"
    assert polled_task.payload["source"] == "PostgreSQL"
    assert polled_task.payload["rows_to_transfer"] == 500

    db_session.refresh(task)
    assert task.status == "Dispatched"

    # Agent updates task to Running
    RuntimeManagerService.update_task_status(
        db_session,
        registered_rt,
        task.id,
        RuntimeTaskStatusUpdate(status="Running")
    )
    db_session.refresh(task)
    assert task.status == "Running"

    # Agent updates task to Completed
    RuntimeManagerService.update_task_status(
        db_session,
        registered_rt,
        task.id,
        RuntimeTaskStatusUpdate(
            status="Completed",
            rows_read=500,
            rows_written=500,
            bytes_processed=20480,
            metrics={"speed_mbps": 12.5}
        )
    )
    db_session.refresh(task)
    assert task.status == "Completed"
    assert task.task_result["rows_written"] == 500
    assert task.task_result["metrics"]["speed_mbps"] == 12.5


def test_key_regeneration(db_session: Session):
    """Test regenerating registration key revokes active sessions."""
    sh_rt, raw_key1 = RuntimeManagerService.create_runtime(
        db_session,
        RuntimeCreate(name=f"sh-regen-{uuid.uuid4().hex[:6]}", runtime_type="SelfHosted")
    )
    registered_rt, token1 = RuntimeManagerService.register_agent(
        db_session,
        AgentRegisterRequest(registration_key=raw_key1, host_name="host-1", agent_version="1.0.0", agent_os="Linux")
    )
    assert registered_rt.status == "Online"

    # Regenerate key
    rt_after, raw_key2 = RuntimeManagerService.regenerate_key(db_session, registered_rt.id)
    assert raw_key2 != raw_key1
    assert rt_after.status == "Registering"
    assert rt_after.auth_token_hash is None

    # Old token is now invalid
    with pytest.raises(PermissionError):
        RuntimeManagerService.authenticate_agent(db_session, token1)


def test_runtime_rest_api_endpoints(client: TestClient, db_session: Session):
    """Test FastAPI REST endpoints for integration runtimes."""
    user = db_session.query(User).first()
    token = create_access_token({"sub": user.id if user else "admin", "role": "Admin"})
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. List runtimes
    resp = client.get("/api/v1/runtimes", headers=auth_headers)
    assert resp.status_code == 200
    runtimes = resp.json()
    assert isinstance(runtimes, list)
    assert any(r["name"] == "AutoResolveIntegrationRuntime" for r in runtimes)

    # 2. Create Self-Hosted runtime via API
    rt_name = f"api-sh-rt-{uuid.uuid4().hex[:6]}"
    create_resp = client.post(
        "/api/v1/runtimes",
        json={"name": rt_name, "runtime_type": "SelfHosted", "description": "Via REST API"},
        headers=auth_headers
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    rt_id = created["id"]
    reg_key = created.get("registration_key")
    assert reg_key is not None
    assert reg_key.startswith("df-ir-")

    # 3. Get Install scripts
    linux_script_resp = client.get(f"/api/v1/runtimes/{rt_id}/install-script/linux", headers=auth_headers)
    assert linux_script_resp.status_code == 200
    linux_json = linux_script_resp.json()
    assert "curl" in linux_json["script"] or "bash" in linux_json["script"]
    assert reg_key in linux_json["script"]

    win_script_resp = client.get(f"/api/v1/runtimes/{rt_id}/install-script/windows", headers=auth_headers)
    assert win_script_resp.status_code == 200
    win_json = win_script_resp.json()
    assert "Invoke-RestMethod" in win_json["script"]
    assert reg_key in win_json["script"]

    # 4. Agent Register via API (agent endpoints don't require user token, they use reg_key)
    agent_reg_resp = client.post(
        "/api/v1/runtimes/agent/register",
        json={
            "registration_key": reg_key,
            "host_name": "agent-test-host",
            "agent_version": "1.0.0",
            "agent_os": "Linux"
        }
    )
    assert agent_reg_resp.status_code == 200
    agent_reg_data = agent_reg_resp.json()
    agent_token = agent_reg_data["auth_token"]
    assert agent_token.startswith("df-session-")

    # 5. Agent Heartbeat via API
    headers = {"X-Agent-Token": agent_token}
    hb_resp = client.post(
        "/api/v1/runtimes/agent/heartbeat",
        json={"cpu_usage_pct": 15.0, "memory_used_bytes": 1048576, "active_task_count": 0, "status": "Online"},
        headers=headers
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "Acknowledged"

    # 6. Delete runtime
    del_resp = client.delete(f"/api/v1/runtimes/{rt_id}", headers=auth_headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"


def test_pipeline_runner_self_hosted_execution(db_session: Session):
    """Test end-to-end PipelineRunner dispatching an activity to a SelfHosted agent."""
    # 1. Setup Self-Hosted Runtime and register agent
    sh_rt, raw_key = RuntimeManagerService.create_runtime(
        db_session,
        RuntimeCreate(name=f"sh-runner-{uuid.uuid4().hex[:6]}", runtime_type="SelfHosted")
    )
    registered_rt, token = RuntimeManagerService.register_agent(
        db_session,
        AgentRegisterRequest(registration_key=raw_key, host_name="mock-worker", agent_version="1.0.0", agent_os="Linux")
    )

    # 2. Setup pipeline targeting this runtime
    proj = db_session.query(Project).first()
    pipeline = Pipeline(
        project_id=proj.id if proj else None,
        name=f"pipeline-sh-{uuid.uuid4().hex[:6]}",
        runtime_id=registered_rt.id,
        definition_json={
            "activities": [
                {
                    "id": "act_sh_1",
                    "name": "SelfHostedCopy",
                    "type": "CopyData",
                    "config": {
                        "source": {"type": "Inline", "format": "json"},
                        "sink": {"type": "Inline", "format": "json"}
                    }
                }
            ]
        }
    )
    db_session.add(pipeline)
    db_session.commit()
    db_session.refresh(pipeline)

    pipe_run = PipelineRun(
        pipeline_id=pipeline.id,
        status="Pending",
        parameters={}
    )
    db_session.add(pipe_run)
    db_session.commit()
    db_session.refresh(pipe_run)

    # Start a background thread to act as the agent worker fulfilling the task
    import threading
    def mock_agent_loop():
        # Wait for task to appear, poll and complete it
        time.sleep(0.5)
        local_db = SessionLocal()
        try:
            rt = local_db.query(IntegrationRuntime).filter(IntegrationRuntime.id == registered_rt.id).first()
            task_item = RuntimeManagerService.poll_next_task(local_db, rt)
            if task_item:
                RuntimeManagerService.update_task_status(
                    local_db,
                    rt,
                    task_item.task_id,
                    RuntimeTaskStatusUpdate(
                        status="Completed",
                        rows_read=150,
                        rows_written=150,
                        bytes_processed=6000,
                        metrics={"agent": "mock-worker"}
                    )
                )
        finally:
            local_db.close()

    agent_thread = threading.Thread(target=mock_agent_loop, daemon=True)
    agent_thread.start()

    # 3. Execute pipeline runner
    runner = PipelineRunner(pipe_run.id)
    runner.execute_sync()

    agent_thread.join(timeout=5)

    # 4. Verify pipeline run and activity run status
    db_session.refresh(pipe_run)
    assert pipe_run.status == "Succeeded"
    assert pipe_run.total_rows_read == 150
    assert pipe_run.total_rows_written == 150

    act_run = db_session.query(ActivityRun).filter(ActivityRun.pipeline_run_id == pipe_run.id).first()
    assert act_run.status == "Succeeded"
    assert act_run.rows_read == 150
    assert act_run.worker_info["runtime_id"] == registered_rt.id
    assert act_run.worker_info["runtime_name"] == registered_rt.name
    assert act_run.worker_info["runtime_type"] == "SelfHosted"
    assert act_run.worker_info["agent_host"] == "mock-worker"
