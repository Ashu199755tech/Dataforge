from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class SQLDialect(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    DUCKDB = "duckdb"
    SNOWFLAKE = "snowflake"
    ANSI = "ansi"


class PushdownEligibility(BaseModel):
    """Assessment of whether a dataflow graph can be pushed down to target database."""
    can_pushdown: bool
    dialect: SQLDialect
    eligible_nodes: List[str] = Field(default_factory=list)
    ineligible_nodes: List[str] = Field(default_factory=list)
    boundary_nodes: List[str] = Field(default_factory=list)
    estimated_egress_saved_bytes: int = 0
    reason: Optional[str] = None


class PushdownQueryPlan(BaseModel):
    """Compiled multi-CTE SQL query plan ready for in-database execution."""
    dialect: SQLDialect
    cte_chain: List[Tuple[str, str]] = Field(default_factory=list)  # [(cte_name, select_sql)]
    final_query: str
    target_table: Optional[str] = None
    target_schema: Optional[str] = None
    write_mode: str = "ctas"  # ctas, insert, select


class PushdownExecutionResult(BaseModel):
    """Summary of in-database SQL Pushdown execution."""
    success: bool
    dialect: str
    rows_affected: int = 0
    duration_seconds: float = 0.0
    egress_bytes: int = 0  # Zero egress contract
    compiled_sql: str
    target_table: Optional[str] = None
    error_message: Optional[str] = None
    cancelled: bool = False
