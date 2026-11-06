import time
from typing import Dict, Any, Optional, List
from backend.app.connectors.base import BaseConnector
from backend.app.engine.copy.models import CancellationToken
from backend.app.engine.pushdown.models import (
    SQLDialect,
    PushdownQueryPlan,
    PushdownExecutionResult
)
from backend.app.engine.pushdown.analyzer import SQLPushdownAnalyzer
from backend.app.engine.pushdown.transpiler import SQLPushdownTranspiler
from backend.app.engine.pushdown.dialect import DialectFormatter


class DataForgeSQLPushdownEngine:
    """
    DataForge Standalone SQL Pushdown Engine.
    Executes transformation DAGs directly inside source or destination databases
    (PostgreSQL, MySQL, SQLite, DuckDB, Snowflake), eliminating network egress
    and external compute cluster overhead.
    """

    @classmethod
    def execute_pushdown(
        cls,
        connector: BaseConnector,
        graph_json: Dict[str, Any],
        dialect: Optional[SQLDialect] = None,
        write_mode: str = "ctas",
        target_table: Optional[str] = None,
        schema_name: Optional[str] = None,
        if_not_exists: bool = False,
        cancellation_token: Optional[CancellationToken] = None
    ) -> PushdownExecutionResult:
        """
        Transpiles and executes a Data Flow graph in-database via multi-CTE ANSI SQL.
        Zero-egress contract: Data never leaves the database engine.
        """
        start_time = time.time()
        token = cancellation_token or CancellationToken()

        resolved_dialect = dialect or SQLPushdownAnalyzer.detect_dialect_from_connector(connector)

        # 1. Eligibility Analysis
        eligibility = SQLPushdownAnalyzer.analyze_graph(graph_json, target_connector=connector)
        if not eligibility.can_pushdown:
            return PushdownExecutionResult(
                success=False,
                dialect=resolved_dialect.value,
                duration_seconds=0.0,
                egress_bytes=0,
                compiled_sql="",
                error_message=f"SQL pushdown ineligible: {eligibility.reason}"
            )

        # 2. Transpile to multi-CTE plan
        plan = SQLPushdownTranspiler.compile_graph(
            graph_json=graph_json,
            dialect=resolved_dialect,
            write_mode=write_mode,
            target_table=target_table,
            target_schema=schema_name,
            if_not_exists=if_not_exists
        )

        effective_target = plan.target_table or target_table

        try:
            token.raise_if_cancelled()

            # 3. Execute in-database
            connector.execute_query(plan.final_query)

            duration = max(0.001, time.time() - start_time)
            rows_affected = 0

            # 4. Measure rows produced in target table if applicable
            if effective_target:
                try:
                    target_q = DialectFormatter.qualify_table(effective_target, schema_name, resolved_dialect)
                    count_res = connector.execute_query(f"SELECT COUNT(*) AS row_cnt FROM {target_q};")
                    if count_res and isinstance(count_res, list) and len(count_res) > 0:
                        rows_affected = int(count_res[0].get("row_cnt") or count_res[0].get("ROW_CNT") or 0)
                except Exception:
                    pass

            return PushdownExecutionResult(
                success=True,
                dialect=resolved_dialect.value,
                rows_affected=rows_affected,
                duration_seconds=round(duration, 3),
                egress_bytes=0,  # Zero network egress
                compiled_sql=plan.final_query,
                target_table=effective_target
            )

        except InterruptedError as ie:
            return PushdownExecutionResult(
                success=False,
                dialect=resolved_dialect.value,
                duration_seconds=round(time.time() - start_time, 3),
                egress_bytes=0,
                compiled_sql=plan.final_query,
                cancelled=True,
                error_message=str(ie)
            )
        except Exception as ex:
            return PushdownExecutionResult(
                success=False,
                dialect=resolved_dialect.value,
                duration_seconds=round(time.time() - start_time, 3),
                egress_bytes=0,
                compiled_sql=plan.final_query,
                error_message=str(ex)
            )
