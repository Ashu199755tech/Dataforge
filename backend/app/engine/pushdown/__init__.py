"""
DataForge Standalone SQL Pushdown Engine:
Compiles and executes transformations directly inside relational databases,
eliminating network egress and external compute overhead.
"""
from backend.app.engine.pushdown.models import (
    SQLDialect,
    PushdownEligibility,
    PushdownQueryPlan,
    PushdownExecutionResult
)
from backend.app.engine.pushdown.dialect import DialectFormatter
from backend.app.engine.pushdown.analyzer import SQLPushdownAnalyzer
from backend.app.engine.pushdown.transpiler import SQLPushdownTranspiler
from backend.app.engine.pushdown.executor import DataForgeSQLPushdownEngine

__all__ = [
    "SQLDialect",
    "PushdownEligibility",
    "PushdownQueryPlan",
    "PushdownExecutionResult",
    "DialectFormatter",
    "SQLPushdownAnalyzer",
    "SQLPushdownTranspiler",
    "DataForgeSQLPushdownEngine"
]
