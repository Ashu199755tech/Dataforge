from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ColumnSchema(BaseModel):
    name: str
    type: str = "VARCHAR"
    nullable: bool = True
    description: Optional[str] = None
    precision: Optional[int] = None
    scale: Optional[int] = None


class DatasetBase(BaseModel):
    name: str
    description: Optional[str] = None
    dataset_type: str = "RelationalTable"  # RelationalTable, RelationalQuery, DelimitedText, Json, Parquet, Avro, Orc, Excel, Binary
    connection_id: str
    project_id: Optional[str] = None
    location_config: Dict[str, Any] = Field(default_factory=dict)
    format_settings: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    schema_definition: List[Dict[str, Any]] = Field(default_factory=list)


class DatasetCreate(DatasetBase):
    auto_discover_schema: bool = True


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    location_config: Optional[Dict[str, Any]] = None
    format_settings: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    schema_definition: Optional[List[Dict[str, Any]]] = None


class DatasetResponse(DatasetBase):
    id: str
    current_version: int = 1
    schema_status: str = "Current"  # Current, DriftDetected, NeedsSync
    last_drift_check_at: Optional[datetime] = None
    last_drift_summary: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    connection_name: Optional[str] = None
    connector_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DatasetVersionResponse(BaseModel):
    id: str
    dataset_id: str
    version_number: int
    schema_snapshot: List[Dict[str, Any]]
    location_snapshot: Dict[str, Any]
    format_snapshot: Dict[str, Any]
    change_summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchemaDriftReport(BaseModel):
    has_drift: bool
    status: str  # Current, DriftDetected
    added_columns: List[Dict[str, Any]] = []
    removed_columns: List[Dict[str, Any]] = []
    altered_columns: List[Dict[str, Any]] = []
    current_physical_schema: List[Dict[str, Any]] = []
    stored_schema: List[Dict[str, Any]] = []


class DatasetPreviewRequest(BaseModel):
    row_limit: int = 50
    parameter_values: Dict[str, Any] = Field(default_factory=dict)


class DatasetPreviewResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    total_rows_previewed: int
    bytes_sampled: int
    duration_ms: int


class DatasetUsageResponse(BaseModel):
    dataset_id: str
    pipeline_count: int
    pipelines: List[Dict[str, Any]] = []
