from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class AppendVariableActivity(BaseActivity):
    """
    Append Variable Activity:
    Appends an evaluated value or object to an existing array variable
    in the pipeline execution state.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        var_name = config.get("variable_name")
        raw_val = config.get("value")

        if not var_name:
            raise ValueError("Variable name is required for AppendVariableActivity.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_val = evaluator.evaluate(raw_val)

        # Get existing variable or initialize as list
        existing_val = self.context.pipeline_variables.get(var_name, [])
        if not isinstance(existing_val, list):
            existing_val = [existing_val]

        existing_val.append(resolved_val)
        self.context.pipeline_variables[var_name] = existing_val

        self.log("INFO", f"Appended value to variable '{var_name}'. New length: {len(existing_val)}")

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables={var_name: existing_val, "appended_value": resolved_val}
        )
