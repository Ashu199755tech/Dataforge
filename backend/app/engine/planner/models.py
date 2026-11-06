import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ExecutionEngineType(str, Enum):
    COPY = "COPY"
    SPARK = "SPARK"
    SQL_PUSHDOWN = "SQL_PUSHDOWN"


class PlannerStrategy(str, Enum):
    AUTO = "AUTO"
    FORCE_COPY = "FORCE_COPY"
    FORCE_SPARK = "FORCE_SPARK"
    FORCE_SQL_PUSHDOWN = "FORCE_SQL_PUSHDOWN"


class WorkloadProfile(BaseModel):
    """Execution characteristics and resource constraints for planner evaluation."""
    workload_id: str = Field(default_factory=lambda: f"wl_{int(time.time()*1000)}")
    estimated_bytes: Optional[int] = None
    estimated_rows: Optional[int] = None
    transformation_complexity_score: int = 0  # 0 to 10 scale
    has_joins: bool = False
    has_aggregations: bool = False
    has_window_functions: bool = False
    has_custom_udf: bool = False
    is_same_database_instance: bool = False
    is_source_database: bool = False
    is_target_database: bool = False
    is_cloud_storage: bool = False
    source_connector_type: Optional[str] = None
    target_connector_type: Optional[str] = None
    spark_available: bool = False
    database_supports_pushdown: bool = False
    max_memory_budget_mb: int = 64


class EngineSuitabilityScore(BaseModel):
    """Detailed multi-factor cost scoring for a specific engine candidate."""
    engine: ExecutionEngineType
    score: float  # Higher score indicates better suitability (0 to 100)
    factors: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)


class PlanDecision(BaseModel):
    """Optimal execution engine selection and rationale produced by the planner."""
    selected_engine: ExecutionEngineType
    strategy_applied: PlannerStrategy
    confidence_score: float  # 0.0 to 1.0
    scores: Dict[str, float] = Field(default_factory=dict)  # Engine -> total score
    explanation: str
    primary_reason: str
    fallback_engine: Optional[ExecutionEngineType] = None
    estimated_duration_seconds: Optional[float] = None
    estimated_egress_bytes: Optional[int] = None
    profile_summary: Dict[str, Any] = Field(default_factory=dict)
