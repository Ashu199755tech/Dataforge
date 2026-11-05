from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class AlertRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    target_type: str = "Pipeline"  # Pipeline, Global, DataQuality, Runtime
    pipeline_id: Optional[str] = None
    condition_type: str  # OnFailure, OnSuccess, DurationExceeded, SLAThreshold, DQScoreThreshold, RuntimeOffline, LongRunningActivity
    threshold_value: Optional[float] = None
    action_type: str = "Log"  # Log, Webhook, Email, Slack, Teams
    action_config: Dict[str, Any] = {}
    cooldown_minutes: int = 5
    is_enabled: bool = True


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_type: Optional[str] = None
    pipeline_id: Optional[str] = None
    condition_type: Optional[str] = None
    threshold_value: Optional[float] = None
    action_type: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None
    cooldown_minutes: Optional[int] = None
    is_enabled: Optional[bool] = None


class AlertRuleResponse(AlertRuleBase):
    id: str
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertEventResponse(BaseModel):
    id: str
    alert_rule_id: str
    pipeline_run_id: Optional[str] = None
    activity_run_id: Optional[str] = None
    title: str
    severity: str
    message: str
    payload: Dict[str, Any] = {}
    status: str
    delivered_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
