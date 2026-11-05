from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class LineageNodeResponse(BaseModel):
    """Public representation of a lineage node."""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    project_id: str
    node_type: str  # Dataset, Table, StorageFile, Pipeline, Activity, DataFlow
    name: str
    qualified_name: str
    provider: str
    location_uri: Optional[str] = None
    dataset_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    connection_id: Optional[str] = None
    schema_columns: List[Dict[str, Any]] = Field(default_factory=list, validation_alias="schema_json", serialization_alias="schema_json")
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ColumnLineageResponse(BaseModel):
    """Public representation of a column-level transformation linkage."""
    id: str
    edge_id: str
    source_column: str
    target_column: str
    transformation_type: str  # direct, derived, aggregate, passthrough, mask
    expression: Optional[str] = None
    confidence: str          # exact, derived, partial, unknown
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LineageEdgeResponse(BaseModel):
    """Public representation of a directed lineage relationship."""
    id: str
    project_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    pipeline_id: Optional[str] = None
    activity_name: Optional[str] = None
    confidence: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LineageGraphResponse(BaseModel):
    """Full or filtered lineage graph structure ready for React Flow visualization."""
    nodes: List[LineageNodeResponse] = Field(default_factory=list)
    edges: List[LineageEdgeResponse] = Field(default_factory=list)
    column_lineage: List[ColumnLineageResponse] = Field(default_factory=list)


class ColumnTraceStep(BaseModel):
    """Single step in an upstream or downstream column lineage chain."""
    edge_id: str
    source_node_id: str
    source_node_name: str
    source_column: str
    target_node_id: str
    target_node_name: str
    target_column: str
    transformation_type: str
    expression: Optional[str] = None
    confidence: str


class ColumnTraceResponse(BaseModel):
    """Trace report of origin roots or downstream targets for a specific column."""
    column_name: str
    node_id: str
    node_name: str
    direction: str  # upstream, downstream
    trace_steps: List[ColumnTraceStep] = Field(default_factory=list)


class ImpactAnalysisRequest(BaseModel):
    """Request to assess downstream impact of altering or deleting an entity or column."""
    node_id: Optional[str] = None
    qualified_name: Optional[str] = None
    column_name: Optional[str] = None


class ImpactAnalysisResponse(BaseModel):
    """Report detailing all downstream dependencies affected by a change."""
    target_node_id: str
    target_node_name: str
    target_column: Optional[str] = None
    risk_level: str  # High, Medium, Low
    summary_message: str
    affected_pipelines_count: int
    affected_datasets_count: int
    affected_columns_count: int
    affected_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    impact_graph: LineageGraphResponse


class LineageExtractResponse(BaseModel):
    """Summary of lineage extraction results."""
    status: str
    message: str
    nodes_discovered: int
    edges_discovered: int
    columns_mapped: int
