from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.dataflow import DataFlow
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.dataflow.engine import DataFlowEngine
from backend.app.engine.planner.planner import IntelligentExecutionPlanner
from backend.app.engine.planner.models import PlannerStrategy, ExecutionEngineType
from backend.app.engine.pushdown.executor import DataForgeSQLPushdownEngine
from backend.app.engine.spark.executor import DataForgeSparkEngine


class ExecuteDataFlowActivity(BaseActivity):
    """
    Execute Data Flow Activity:
    Executes a visual mapping transformation graph (DataFlow) within an orchestration pipeline,
    evaluating the optimal engine (SQL Pushdown, Spark, or Vectorized Copy) via the Intelligent Execution Planner.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        dataflow_id = config.get("dataflow_id")
        dataflow_name = config.get("dataflow_name")

        if not dataflow_id and not dataflow_name:
            # Check if graph_json is passed inline
            graph_json = config.get("graph_json")
            if not graph_json:
                raise ValueError("Either 'dataflow_id', 'dataflow_name', or inline 'graph_json' is required.")
        else:
            query = self.db.query(DataFlow)
            if dataflow_id:
                df_record = query.filter(DataFlow.id == dataflow_id).first()
            else:
                df_record = query.filter(DataFlow.name == dataflow_name).first()

            if not df_record:
                raise ValueError(f"DataFlow with ID '{dataflow_id}' or Name '{dataflow_name}' not found.")

            graph_json = df_record.graph_json

        self.log("INFO", f"Executing Data Flow transformation graph ({len(graph_json.get('nodes', []))} nodes)")

        # Resolve connectors for planner evaluation
        source_connector = None
        target_connector = None
        nodes = graph_json.get("nodes", [])
        src_nodes = [n for n in nodes if n.get("operatorType") == "Source"]
        sink_nodes = [n for n in nodes if n.get("operatorType") == "Sink"]
        
        if src_nodes:
            src_conn_id = src_nodes[0].get("config", {}).get("connection_id")
            if src_conn_id:
                rec = self.db.query(Connection).filter(Connection.id == src_conn_id).first()
                if rec:
                    try:
                        source_connector = get_connector(rec.connector_type, decrypt_secret(rec.config_encrypted))
                    except Exception:
                        pass
        if sink_nodes:
            dst_conn_id = sink_nodes[0].get("config", {}).get("connection_id")
            if dst_conn_id:
                rec = self.db.query(Connection).filter(Connection.id == dst_conn_id).first()
                if rec:
                    try:
                        target_connector = get_connector(rec.connector_type, decrypt_secret(rec.config_encrypted))
                    except Exception:
                        pass

        # Evaluate Intelligent Execution Planner
        strategy_raw = (
            config.get("execution_engine_strategy")
            or config.get("engine_strategy")
            or "AUTO"
        )
        strat_key = str(strategy_raw).upper().replace(" ", "_")
        strategy = getattr(PlannerStrategy, strat_key, PlannerStrategy.AUTO)

        plan = IntelligentExecutionPlanner.plan_dataflow(
            graph_json=graph_json,
            source_connector=source_connector,
            target_connector=target_connector,
            strategy=strategy
        )
        self.log(
            "INFO",
            f"Execution Planner Decision for DataFlow: {plan.selected_engine.value} "
            f"(Strategy: {strategy.value}, Confidence: {plan.confidence_score}) - {plan.explanation}"
        )

        planner_metrics = {
            "execution_engine": plan.selected_engine.value,
            "planner_strategy": strategy.value,
            "planner_confidence": plan.confidence_score,
            "planner_scores": plan.scores,
            "planner_explanation": plan.explanation,
            "primary_reason": plan.primary_reason
        }

        # 1. SQL Pushdown Engine Dispatch
        if plan.selected_engine == ExecutionEngineType.SQL_PUSHDOWN and target_connector:
            try:
                res_pushdown = DataForgeSQLPushdownEngine.execute_in_database(
                    graph_json=graph_json,
                    connector=target_connector
                )
                self.log("INFO", f"SQL Pushdown executed in {res_pushdown.duration_seconds}s with 0 egress bytes.")
                return ActivityExecutionResult(
                    status="Succeeded",
                    rows_read=res_pushdown.rows_affected,
                    rows_written=res_pushdown.rows_affected,
                    bytes_processed=0,
                    output_variables={
                        "total_rows_read": res_pushdown.rows_affected,
                        "total_rows_written": res_pushdown.rows_affected,
                        "duration_seconds": res_pushdown.duration_seconds
                    },
                    metrics={
                        **planner_metrics,
                        "total_rows_read": res_pushdown.rows_affected,
                        "total_rows_written": res_pushdown.rows_affected,
                        "duration_seconds": res_pushdown.duration_seconds,
                        "egress_bytes": 0,
                        "generated_sql": res_pushdown.compiled_sql
                    }
                )
            except Exception as pe:
                self.log("WARN", f"SQL Pushdown attempt failed ({str(pe)}). Falling back to vectorized engine.")

        # 2. Spark Engine Dispatch
        if plan.selected_engine == ExecutionEngineType.SPARK:
            try:
                res_spark = DataForgeSparkEngine.execute_dataflow(
                    graph_json=graph_json,
                    source_connector=source_connector,
                    target_connector=target_connector
                )
                if res_spark.status == "Succeeded":
                    self.log("INFO", f"Spark Engine executed in {res_spark.duration_seconds}s ({res_spark.execution_mode}).")
                    return ActivityExecutionResult(
                        status="Succeeded",
                        rows_read=res_spark.total_rows_read,
                        rows_written=res_spark.total_rows_written,
                        output_variables={
                            "total_rows_read": res_spark.total_rows_read,
                            "total_rows_written": res_spark.total_rows_written,
                            "duration_seconds": res_spark.duration_seconds
                        },
                        metrics={
                            **planner_metrics,
                            "total_rows_read": res_spark.total_rows_read,
                            "total_rows_written": res_spark.total_rows_written,
                            "duration_seconds": res_spark.duration_seconds,
                            "execution_mode": res_spark.execution_mode
                        }
                    )
            except Exception as se:
                self.log("WARN", f"Spark execution failed ({str(se)}). Falling back to vectorized engine.")

        # 3. Vectorized DataFlowEngine Dispatch (Default / Copy Engine)
        engine = DataFlowEngine(db_session=self.db)
        res = engine.execute_graph(graph_json)

        if res.status != "Succeeded":
            self.log("ERROR", f"Data Flow execution failed: {res.error_message}")
            return ActivityExecutionResult(
                status="Failed",
                error_message=res.error_message,
                rows_read=res.total_rows_read,
                rows_written=res.total_rows_written,
                metrics={
                    **planner_metrics,
                    "total_rows_read": res.total_rows_read,
                    "total_rows_written": res.total_rows_written,
                    "duration_seconds": res.duration_seconds
                }
            )

        self.log(
            "INFO",
            f"Data Flow completed successfully in {res.duration_seconds}s (Read: {res.total_rows_read}, Written: {res.total_rows_written})"
        )

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=res.total_rows_read,
            rows_written=res.total_rows_written,
            output_variables={
                "total_rows_read": res.total_rows_read,
                "total_rows_written": res.total_rows_written,
                "duration_seconds": res.duration_seconds,
                "sink_metrics": res.sink_metrics
            },
            metrics={
                **planner_metrics,
                "total_rows_read": res.total_rows_read,
                "total_rows_written": res.total_rows_written,
                "duration_seconds": res.duration_seconds
            }
        )
