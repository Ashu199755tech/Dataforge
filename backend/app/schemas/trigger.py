from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class TriggerBase(BaseModel):
    name: str
    trigger_type: str = "cron"  # cron, tumbling_window, manual
    cron_expression: Optional[str] = "0 * * * *"  # e.g., every hour
    is_active: bool = True
    parameters: Dict[str, Any] = {}


class TriggerCreate(TriggerBase):
    pipeline_id: str


class TriggerUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None
    parameters: Optional[Dict[str, Any]] = None


class TriggerResponse(TriggerBase):
    id: str
    pipeline_id: str
    last_fired_at: Optional[datetime] = None
    next_fire_time: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
