from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class PipelineTarget(BaseModel):
    """Target pipeline to run with dedicated parameter mappings."""
    pipeline_id: str
    pipeline_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ScheduleConfig(BaseModel):
    """Configuration for timezone-aware recurrence schedules."""
    timezone: str = "UTC"
    frequency: str = "Hour"  # Minute, Hour, Day, Week, Month
    interval: int = 1
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TumblingWindowConfig(BaseModel):
    """Configuration for tumbling non-overlapping time slices."""
    frequency: str = "Hour"  # Minute, Hour
    interval: int = 1
    start_time: datetime
    end_time: Optional[datetime] = None
    delay_minutes: int = 0
    max_concurrency: int = 1
    retry_count: int = 3
    retry_interval_seconds: int = 60
    depends_on_prior_window: bool = True


class StorageEventConfig(BaseModel):
    """Configuration for cloud/local storage event triggers."""
    connection_id: str
    container: str
    prefix: str = ""
    suffix: str = ""
    blob_path_regex: Optional[str] = None
    event_types: List[str] = Field(default_factory=lambda: ["created"])
    ignore_empty_blobs: bool = True


class PipelineDependencyConfig(BaseModel):
    """Configuration for triggers that fire on upstream pipeline completion."""
    upstream_pipeline_id: str
    upstream_pipeline_name: Optional[str] = None
    fire_on_status: List[str] = Field(default_factory=lambda: ["Succeeded"])
    forward_parameters: bool = True
    timeout_minutes: int = 60


class TriggerBase(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str = "cron"  # manual, schedule, cron, tumbling_window, storage_event, pipeline_dependency
    pipeline_id: Optional[str] = None
    pipelines_to_run: List[PipelineTarget] = Field(default_factory=list)
    cron_expression: Optional[str] = None
    schedule_config: Optional[ScheduleConfig] = None
    tumbling_window_config: Optional[TumblingWindowConfig] = None
    storage_event_config: Optional[StorageEventConfig] = None
    pipeline_dependency_config: Optional[PipelineDependencyConfig] = None
    is_active: bool = True
    parameters: Dict[str, Any] = Field(default_factory=dict)


class TriggerCreate(TriggerBase):
    pipeline_id: Optional[str] = None


class TriggerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    pipeline_id: Optional[str] = None
    pipelines_to_run: Optional[List[PipelineTarget]] = None
    cron_expression: Optional[str] = None
    schedule_config: Optional[ScheduleConfig] = None
    tumbling_window_config: Optional[TumblingWindowConfig] = None
    storage_event_config: Optional[StorageEventConfig] = None
    pipeline_dependency_config: Optional[PipelineDependencyConfig] = None
    is_active: Optional[bool] = None
    parameters: Optional[Dict[str, Any]] = None


class TriggerResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    trigger_type: str
    pipeline_id: Optional[str] = None
    pipelines_to_run: List[Dict[str, Any]] = Field(default_factory=list)
    cron_expression: Optional[str] = None
    schedule_config: Dict[str, Any] = Field(default_factory=dict)
    tumbling_window_config: Dict[str, Any] = Field(default_factory=dict)
    storage_event_config: Dict[str, Any] = Field(default_factory=dict)
    pipeline_dependency_config: Dict[str, Any] = Field(default_factory=dict)
    window_state: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    parameters: Dict[str, Any] = Field(default_factory=dict)
    last_fired_at: Optional[datetime] = None
    next_fire_time: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TriggerRunResponse(BaseModel):
    id: str
    trigger_id: str
    run_status: str
    fired_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: int
    triggered_pipeline_runs: List[Dict[str, Any]] = Field(default_factory=list)
    event_payload: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
