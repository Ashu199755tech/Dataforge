from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.dataflow import DataFlow
from backend.app.dataflow.engine import DataFlowEngine


class ExecuteDataFlowActivity(BaseActivity):
    """
    Execute Data Flow Activity:
    Executes a visual mapping transformation graph (DataFlow) within an orchestration pipeline,
    streaming records from sources through vectorized Polars operations into sinks.
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
                "total_rows_read": res.total_rows_read,
                "total_rows_written": res.total_rows_written,
                "duration_seconds": res.duration_seconds
            }
        )
