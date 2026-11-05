from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.api.deps import get_current_user
from backend.app.models.runtime import IntegrationRuntime, RuntimeTask
from backend.app.services.runtime_manager import RuntimeManagerService
from backend.app.schemas.runtime import (
    RuntimeCreate,
    RuntimeUpdate,
    RuntimeResponse,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    RuntimeTaskItem,
    RuntimeTaskStatusUpdate,
    RuntimeTaskResponse
)


router = APIRouter(prefix="/runtimes", tags=["Integration Runtimes"])


def _extract_agent_token(
    x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> str:
    """Extracts agent session token from headers."""
    if x_agent_token:
        return x_agent_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing agent session credentials in headers (X-Agent-Token or Authorization)."
    )


def _to_runtime_response(rt: IntegrationRuntime) -> RuntimeResponse:
    reg_key = RuntimeManagerService.get_registration_key(rt) if rt.runtime_type == "SelfHosted" else None
    return RuntimeResponse(
        id=rt.id,
        project_id=rt.project_id,
        name=rt.name,
        description=rt.description,
        runtime_type=rt.runtime_type,
        status=rt.status,
        is_enabled=rt.is_enabled,
        registration_key=reg_key,
        agent_version=rt.agent_version,
        agent_os=rt.agent_os,
        host_name=rt.host_name,
        ip_address=rt.ip_address,
        cpu_cores=rt.cpu_cores,
        cpu_usage_pct=rt.cpu_usage_pct,
        memory_total_bytes=rt.memory_total_bytes,
        memory_used_bytes=rt.memory_used_bytes,
        concurrency_limit=rt.concurrency_limit,
        active_task_count=rt.active_task_count,
        last_heartbeat_at=rt.last_heartbeat_at,
        config=rt.config,
        created_at=rt.created_at,
        updated_at=rt.updated_at
    )


# ---------------------------------------------------------------------------
# Control Plane CRUD Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[RuntimeResponse])
@router.get("/", response_model=List[RuntimeResponse])
def list_runtimes(
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists all integration runtimes for a project, triggering offline detection."""
    RuntimeManagerService.check_offline_runtimes(db)
    query = db.query(IntegrationRuntime)
    if project_id:
        query = query.filter(IntegrationRuntime.project_id == project_id)
    runtimes = query.order_by(IntegrationRuntime.name.asc()).all()
    return [_to_runtime_response(rt) for rt in runtimes]


@router.post("", response_model=RuntimeResponse)
@router.post("/", response_model=RuntimeResponse)
def create_runtime(
    runtime_in: RuntimeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new Cloud, SelfHosted, or LocalDev integration runtime."""
    runtime, raw_key = RuntimeManagerService.create_runtime(db, runtime_in)
    resp = _to_runtime_response(runtime)
    if raw_key:
        resp.registration_key = raw_key
    return resp


@router.get("/{runtime_id}", response_model=RuntimeResponse)
def get_runtime(
    runtime_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gets details and live health metrics of an integration runtime."""
    RuntimeManagerService.check_offline_runtimes(db)
    runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == runtime_id).first()
    if not runtime:
        raise HTTPException(status_code=404, detail="Integration Runtime not found")
    return _to_runtime_response(runtime)


@router.put("/{runtime_id}", response_model=RuntimeResponse)
def update_runtime(
    runtime_id: str,
    runtime_in: RuntimeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Updates runtime limits, configuration, or enabled status."""
    runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == runtime_id).first()
    if not runtime:
        raise HTTPException(status_code=404, detail="Integration Runtime not found")

    if runtime_in.name is not None:
        runtime.name = runtime_in.name
    if runtime_in.description is not None:
        runtime.description = runtime_in.description
    if runtime_in.concurrency_limit is not None:
        runtime.concurrency_limit = runtime_in.concurrency_limit
    if runtime_in.is_enabled is not None:
        runtime.is_enabled = runtime_in.is_enabled
        if not runtime_in.is_enabled:
            runtime.status = "Disabled"
    if runtime_in.config is not None:
        runtime.config = runtime_in.config

    runtime.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(runtime)
    return _to_runtime_response(runtime)


@router.delete("/{runtime_id}")
def delete_runtime(
    runtime_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes an integration runtime and cascades removal of associated tasks."""
    runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == runtime_id).first()
    if not runtime:
        raise HTTPException(status_code=404, detail="Integration Runtime not found")
    db.delete(runtime)
    db.commit()
    return {"status": "deleted", "message": "Integration Runtime deleted successfully"}


@router.post("/{runtime_id}/regenerate-key", response_model=RuntimeResponse)
def regenerate_runtime_key(
    runtime_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Regenerates registration key for a SelfHosted runtime, invalidating existing sessions."""
    try:
        runtime, raw_key = RuntimeManagerService.regenerate_key(db, runtime_id)
        resp = _to_runtime_response(runtime)
        resp.registration_key = raw_key
        return resp
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{runtime_id}/tasks", response_model=List[RuntimeTaskResponse])
def get_runtime_tasks(
    runtime_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists recent tasks dispatched to this runtime."""
    tasks = db.query(RuntimeTask).filter(
        RuntimeTask.runtime_id == runtime_id
    ).order_by(RuntimeTask.queued_at.desc()).limit(limit).all()
    return tasks


# ---------------------------------------------------------------------------
# Copyable Shell Install Scripts (Linux & Windows)
# ---------------------------------------------------------------------------

@router.get("/{runtime_id}/install-script/linux")
def get_linux_install_script(
    runtime_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates a one-line copyable bash script to install and register the agent on Linux."""
    runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == runtime_id).first()
    if not runtime:
        raise HTTPException(status_code=404, detail="Integration Runtime not found")

    reg_key = RuntimeManagerService.get_registration_key(runtime) or "YOUR_REGISTRATION_KEY"
    base_url = str(request.base_url).rstrip("/")

    script = f"""#!/bin/bash
# DataForge Self-Hosted Integration Runtime Agent Installer (Linux)
set -e

DATAFORGE_URL="{base_url}"
REGISTRATION_KEY="{reg_key}"

echo "=========================================================="
echo "  DataForge Self-Hosted Integration Runtime Agent Setup"
echo "  Runtime: {runtime.name} ({runtime.id})"
echo "=========================================================="

# Check Python 3.10+
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is required. Please install python3 and python3-venv."
    exit 1
fi

AGENT_DIR="/opt/dataforge-agent"
sudo mkdir -p "$AGENT_DIR"
sudo chown -R $USER "$AGENT_DIR"
cd "$AGENT_DIR"

python3 -m venv venv
./venv/bin/pip install --upgrade pip requests psutil

# Download and run agent
cat << 'EOF' > run_agent.py
import os, sys, time, json, requests, socket, psutil

BASE_URL = os.environ.get("DATAFORGE_URL", "{base_url}")
KEY = os.environ.get("DATAFORGE_REG_KEY", "{reg_key}")

print(f"[AGENT] Registering with DataForge Control Plane at {{BASE_URL}}...")
reg_payload = {{
    "registration_key": KEY,
    "host_name": socket.gethostname(),
    "agent_version": "1.0.0",
    "agent_os": "Linux",
    "cpu_cores": psutil.cpu_count(logical=True) or 4,
    "memory_total_bytes": psutil.virtual_memory().total
}}

res = requests.post(f"{{BASE_URL}}/api/v1/runtimes/agent/register", json=reg_payload)
if not res.ok:
    print(f"[ERROR] Registration failed ({{res.status_code}}): {{res.text}}")
    sys.exit(1)

token = res.json()["auth_token"]
headers = {{"X-Agent-Token": token}}
print("[AGENT] Successfully registered! Starting heartbeat & task execution loop...")

while True:
    try:
        hb_payload = {{
            "cpu_usage_pct": psutil.cpu_percent(),
            "memory_used_bytes": psutil.virtual_memory().used,
            "active_task_count": 0
        }}
        requests.post(f"{{BASE_URL}}/api/v1/runtimes/agent/heartbeat", json=hb_payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"[WARN] Heartbeat error: {{e}}")
    time.sleep(15)
EOF

DATAFORGE_URL="$DATAFORGE_URL" DATAFORGE_REG_KEY="$REGISTRATION_KEY" ./venv/bin/python3 run_agent.py
"""
    return {"script": script}


@router.get("/{runtime_id}/install-script/windows")
def get_windows_install_script(
    runtime_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates a one-line copyable PowerShell script to install and register the agent on Windows."""
    runtime = db.query(IntegrationRuntime).filter(IntegrationRuntime.id == runtime_id).first()
    if not runtime:
        raise HTTPException(status_code=404, detail="Integration Runtime not found")

    reg_key = RuntimeManagerService.get_registration_key(runtime) or "YOUR_REGISTRATION_KEY"
    base_url = str(request.base_url).rstrip("/")

    script = f"""# DataForge Self-Hosted Integration Runtime Agent Installer (Windows PowerShell)
$ErrorActionPreference = "Stop"

$DATAFORGE_URL = "{base_url}"
$REGISTRATION_KEY = "{reg_key}"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  DataForge Self-Hosted Integration Runtime Agent Setup" -ForegroundColor Cyan
Write-Host "  Runtime: {runtime.name} ({runtime.id})" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$agentDir = "C:\\DataForgeAgent"
if (!(Test-Path -Path $agentDir)) {{
    New-Item -ItemType Directory -Path $agentDir | Out-Null
}}
Set-Location -Path $agentDir

Write-Host "[AGENT] Registering host '$($env:COMPUTERNAME)' with DataForge..." -ForegroundColor Green
$regBody = @{{
    registration_key = $REGISTRATION_KEY
    host_name = $env:COMPUTERNAME
    agent_version = "1.0.0"
    agent_os = "Windows"
    cpu_cores = [Environment]::ProcessorCount
    memory_total_bytes = (Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum
}} | ConvertTo-Json

$regResp = Invoke-RestMethod -Uri "$DATAFORGE_URL/api/v1/runtimes/agent/register" -Method Post -Body $regBody -ContentType "application/json"
$authToken = $regResp.auth_token

Write-Host "[AGENT] Registered successfully! Session token established." -ForegroundColor Green
Write-Host "[AGENT] Heartbeat & Execution worker listening on background daemon..." -ForegroundColor Yellow

while ($true) {{
    try {{
        $hbBody = @{{
            cpu_usage_pct = (Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1).CounterSamples[0].CookedValue
            memory_used_bytes = 0
            active_task_count = 0
        }} | ConvertTo-Json

        Invoke-RestMethod -Uri "$DATAFORGE_URL/api/v1/runtimes/agent/heartbeat" -Method Post -Body $hbBody -ContentType "application/json" -Headers @{{ "X-Agent-Token" = $authToken }} | Out-Null
    }} catch {{
        Write-Warning "Heartbeat dispatch error: $_"
    }}
    Start-Sleep -Seconds 15
}}
"""
    return {"script": script}


# ---------------------------------------------------------------------------
# Agent Protocol Endpoints (Polled by Remote Agent Nodes)
# ---------------------------------------------------------------------------

@router.post("/agent/register", response_model=AgentRegisterResponse)
def agent_register(req: AgentRegisterRequest, db: Session = Depends(get_db)):
    """Remote agent initial registration exchange using registration key."""
    try:
        runtime, session_token = RuntimeManagerService.register_agent(db, req)
        return AgentRegisterResponse(
            runtime_id=runtime.id,
            runtime_name=runtime.name,
            auth_token=session_token,
            heartbeat_interval_seconds=15
        )
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))


@router.post("/agent/heartbeat", response_model=AgentHeartbeatResponse)
def agent_heartbeat(
    req: AgentHeartbeatRequest,
    token: str = Depends(_extract_agent_token),
    db: Session = Depends(get_db)
):
    """Remote agent regular heartbeat emitting host metrics and capacity."""
    try:
        runtime = RuntimeManagerService.authenticate_agent(db, token)
        pending_count = RuntimeManagerService.process_heartbeat(db, runtime, req)
        return AgentHeartbeatResponse(
            status="Acknowledged",
            acknowledged_at=datetime.now(timezone.utc),
            pending_tasks_count=pending_count
        )
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))


@router.post("/agent/poll-tasks", response_model=Optional[RuntimeTaskItem])
def agent_poll_tasks(
    token: str = Depends(_extract_agent_token),
    db: Session = Depends(get_db)
):
    """Remote agent polls for queued execution tasks."""
    try:
        runtime = RuntimeManagerService.authenticate_agent(db, token)
        task_item = RuntimeManagerService.poll_next_task(db, runtime)
        return task_item
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))


@router.post("/agent/tasks/{task_id}/status", response_model=RuntimeTaskResponse)
def agent_update_task_status(
    task_id: str,
    update: RuntimeTaskStatusUpdate,
    token: str = Depends(_extract_agent_token),
    db: Session = Depends(get_db)
):
    """Remote agent reports progress or completion of an assigned task."""
    try:
        runtime = RuntimeManagerService.authenticate_agent(db, token)
        task = RuntimeManagerService.update_task_status(db, runtime, task_id, update)
        return task
    except PermissionError as pe:
        raise HTTPException(status_code=401, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
