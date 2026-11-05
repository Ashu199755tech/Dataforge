from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class LogResponse(BaseModel):
    id: int
    level: str
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ActivityRunResponse(BaseModel):
    id: str
    pipeline_run_id: str
    activity_id: str
    activity_name: str
    activity_type: str
    status: str
    retry_attempt: int
    rows_read: int
    rows_written: int
    bytes_processed: int
    duration_seconds: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    metrics: Dict[str, Any] = {}
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class PipelineRunResponse(BaseModel):
    id: str
    pipeline_id: str
    run_type: str
    status: str
    parameters: Dict[str, Any]
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_seconds: int
    total_activities: int
    succeeded_activities: int
    failed_activities: int
    total_rows_read: int
    total_rows_written: int
    error_summary: Optional[str] = None
    activity_runs: List[ActivityRunResponse] = []

    class Config:
        from_attributes = True
