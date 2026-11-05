from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class ConnectionBase(BaseModel):
    name: str
    connector_type: str  # postgres, mysql, sqlite
    description: Optional[str] = None


class ConnectionCreate(ConnectionBase):
    project_id: str
    config: Dict[str, Any]  # host, port, user, password, database


class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class ConnectionResponse(ConnectionBase):
    id: str
    project_id: str
    status: str
    config_masked: Dict[str, Any]
    last_tested_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None
    server_version: Optional[str] = None
