from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class RuntimeBase(BaseModel):
    name: str
    description: Optional[str] = None
    runtime_type: str = "Cloud"  # Cloud, SelfHosted, LocalDev
    concurrency_limit: int = 4
    config: Dict[str, Any] = {}


class RuntimeCreate(RuntimeBase):
    project_id: Optional[str] = None


class RuntimeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    concurrency_limit: Optional[int] = None
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class RuntimeResponse(RuntimeBase):
    id: str
    project_id: Optional[str] = None
    status: str
    is_enabled: bool
    registration_key: Optional[str] = None
    agent_version: Optional[str] = None
    agent_os: Optional[str] = None
    host_name: Optional[str] = None
    ip_address: Optional[str] = None
    cpu_cores: int
    cpu_usage_pct: float
    memory_total_bytes: int
    memory_used_bytes: int
    active_task_count: int
    last_heartbeat_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentRegisterRequest(BaseModel):
    registration_key: str
    host_name: str
    agent_version: str = "1.0.0"
    agent_os: str = "Linux"
    cpu_cores: int = 4
    memory_total_bytes: int = 8589934592
    ip_address: Optional[str] = None


class AgentRegisterResponse(BaseModel):
    runtime_id: str
    runtime_name: str
    auth_token: str
    heartbeat_interval_seconds: int = 15


class AgentHeartbeatRequest(BaseModel):
    cpu_usage_pct: float = 0.0
    memory_used_bytes: int = 0
    active_task_count: int = 0
    status: Optional[str] = "Online"


class AgentHeartbeatResponse(BaseModel):
    status: str
    acknowledged_at: datetime
    pending_tasks_count: int = 0


class RuntimeTaskItem(BaseModel):
    task_id: str
    task_type: str
    pipeline_run_id: Optional[str] = None
    activity_run_id: Optional[str] = None
    activity_name: Optional[str] = None
    payload: Dict[str, Any] = {}
    timeout_seconds: int = 3600


class RuntimeTaskStatusUpdate(BaseModel):
    status: str  # Running, Completed, Failed
    rows_read: Optional[int] = 0
    rows_written: Optional[int] = 0
    bytes_processed: Optional[int] = 0
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = {}
    output_variables: Dict[str, Any] = {}


class RuntimeTaskResponse(BaseModel):
    id: str
    runtime_id: str
    pipeline_run_id: Optional[str] = None
    activity_run_id: Optional[str] = None
    task_type: str
    status: str
    retry_count: int
    max_retries: int
    timeout_seconds: int
    task_result: Dict[str, Any]
    queued_at: datetime
    dispatched_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
