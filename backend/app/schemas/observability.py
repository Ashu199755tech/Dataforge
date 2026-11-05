from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class CopyDataPerformanceMetrics(BaseModel):
    """Aggregated performance metrics for Copy Data activities."""
    total_copy_activities: int
    total_rows_transferred: int
    total_bytes_transferred: int
    average_throughput_mb_sec: float
    peak_throughput_mb_sec: float
    total_rejected_rows: int
    average_duration_seconds: float
    throughput_trend: List[Dict[str, Any]] = Field(default_factory=list)
    recent_transfers: List[Dict[str, Any]] = Field(default_factory=list)


class RuntimeFleetOverview(BaseModel):
    """Fleet-wide health and capacity telemetry across all integration runtimes."""
    total_runtimes: int
    online_count: int
    offline_count: int
    fleet_cpu_usage_pct: float
    fleet_memory_total_bytes: int
    fleet_memory_used_bytes: int
    fleet_memory_usage_pct: float
    active_tasks: int
    total_concurrency_capacity: int
    runtimes: List[Dict[str, Any]] = Field(default_factory=list)


class ErrorCluster(BaseModel):
    """Categorized cluster of similar pipeline / activity failures."""
    cluster_id: str
    error_category: str
    representative_message: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    affected_pipelines: List[str] = Field(default_factory=list)
    affected_activities: List[str] = Field(default_factory=list)
    suggested_remediation: str


class FailureDiagnosticsResponse(BaseModel):
    """Root cause diagnostics and failure clustering analysis."""
    total_failures: int
    failure_rate_pct: float
    clusters: List[ErrorCluster] = Field(default_factory=list)


class OtelSpan(BaseModel):
    """OpenTelemetry-compatible span representation."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    kind: str = "INTERNAL"
    start_time_unix_nano: int
    end_time_unix_nano: int
    attributes: Dict[str, Any] = Field(default_factory=dict)
    status: Dict[str, Any] = Field(default_factory=dict)


class OtelTraceResponse(BaseModel):
    """OpenTelemetry trace representation for a pipeline run."""
    trace_id: str
    spans: List[OtelSpan] = Field(default_factory=list)


class ObservabilityOverview(BaseModel):
    """Comprehensive observability dashboard payload."""
    project_id: str
    total_pipeline_runs: int
    active_runs: int
    success_rate_pct: float
    copy_performance: CopyDataPerformanceMetrics
    fleet_overview: RuntimeFleetOverview
    failure_diagnostics: FailureDiagnosticsResponse
