from typing import Dict, Any, Optional
from datetime import datetime, timezone
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.execution.expressions import ExpressionEvaluator


class ExecutePipelineActivity(BaseActivity):
    """
    Execute Pipeline Activity:
    Invokes a child pipeline by ID or name with parameter mapping,
    waits for execution to complete, and bubbles up execution status and outputs.
    """

    def execute(self) -> ActivityExecutionResult:
        from backend.app.execution.runner import PipelineRunner
        config = self.context.config
        target_pipe_ref = config.get("pipeline_id") or config.get("pipeline_name")
        child_parameters = config.get("parameters", {})
        wait_on_completion = bool(config.get("wait_on_completion", True))

        if not target_pipe_ref:
            raise ValueError("Either 'pipeline_id' or 'pipeline_name' must be configured for ExecutePipelineActivity.")

        # Resolve pipeline
        child_pipeline = (
            self.db.query(Pipeline)
            .filter((Pipeline.id == target_pipe_ref) | (Pipeline.name == target_pipe_ref))
            .first()
        )
        if not child_pipeline:
            raise ValueError(f"Child pipeline '{target_pipe_ref}' not found in metadata database.")

        self.log("INFO", f"Invoking child pipeline '{child_pipeline.name}' (ID: {child_pipeline.id})")

        # Evaluate parameter expressions
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_child_params = evaluator.evaluate(child_parameters)

        # Create child PipelineRun record
        child_run = PipelineRun(
            pipeline_id=child_pipeline.id,
            status="Pending",
            run_type="ChildPipeline",
            parameters=resolved_child_params
        )
        self.db.add(child_run)
        self.db.commit()
        self.db.refresh(child_run)

        self.log("INFO", f"Child PipelineRun created with ID: {child_run.id}")

        if not wait_on_completion:
            return ActivityExecutionResult(
                status="Succeeded",
                output_variables={"child_run_id": child_run.id, "status": "Dispatched"}
            )

        # Execute child pipeline synchronously
        child_runner = PipelineRunner(child_run.id)
        child_runner.execute_sync()

        # Reload updated child run state
        self.db.refresh(child_run)
        self.log(
            "INFO" if child_run.status == "Succeeded" else "ERROR",
            f"Child pipeline '{child_pipeline.name}' completed with status: {child_run.status}"
        )

        if child_run.status == "Succeeded":
            child_metrics = child_run.execution_metrics or {}
            child_output_vars = child_metrics.get("output_variables", {})
            pipeline_return_val = child_output_vars.get("pipelineReturnValue", child_output_vars)

            combined_outputs = {
                "child_run_id": child_run.id,
                "child_status": child_run.status,
                "child_pipeline_name": child_pipeline.name,
                "duration_seconds": child_run.duration_seconds or 0,
                "pipelineReturnValue": pipeline_return_val,
                **child_output_vars
            }

            return ActivityExecutionResult(
                status="Succeeded",
                rows_read=child_run.total_rows_read or 0,
                rows_written=child_run.total_rows_written or 0,
                output_variables=combined_outputs,
                metrics={
                    "child_rows_read": child_run.total_rows_read or 0,
                    "child_rows_written": child_run.total_rows_written or 0,
                    "child_duration_seconds": child_run.duration_seconds or 0
                }
            )
        else:
            return ActivityExecutionResult(
                status="Failed",
                error_message=f"Child pipeline '{child_pipeline.name}' failed: {child_run.error_summary or 'Unknown error'}",
                output_variables={"child_run_id": child_run.id, "child_status": child_run.status}
            )
