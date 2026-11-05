from typing import Dict, Any
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class SetVariableActivity(BaseActivity):
    """
    Set Variable Activity: Assigns or computes the value of an existing
    pipeline variable dynamically during execution.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        var_name = config.get("variable_name")
        val_expr = config.get("value")

        if not var_name:
            raise ValueError("SetVariable activity requires 'variable_name'.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_value = evaluator.evaluate(val_expr)

        self.log("INFO", f"Setting pipeline variable '{var_name}' = '{resolved_value}'")

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables={var_name: resolved_value},
            metrics={"variable_name": var_name, "value": str(resolved_value)}
        )
