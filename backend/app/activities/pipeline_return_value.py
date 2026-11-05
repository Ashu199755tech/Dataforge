from typing import Dict, Any
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class PipelineReturnValueActivity(BaseActivity):
    """
    Pipeline Return Value Activity:
    Defines key-value pairs or structured payloads returned by a child pipeline
    to its parent calling pipeline or external trigger caller.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )

        raw_value = config.get("value", {})
        resolved_value = evaluator.evaluate(raw_value)

        self.log("INFO", f"Pipeline return value set: {resolved_value}")

        output_vars = {
            "pipelineReturnValue": resolved_value
        }
        if isinstance(resolved_value, dict):
            output_vars.update(resolved_value)

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables=output_vars
        )
