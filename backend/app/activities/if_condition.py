from typing import Dict, Any, List
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class IfConditionActivity(BaseActivity):
    """
    If Condition Activity: Evaluates a boolean expression and determines
    whether downstream True or False branches should execute.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        expression = config.get("expression")

        if not expression:
            raise ValueError("IfCondition activity requires an 'expression' to evaluate.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        evaluated_outcome = evaluator.evaluate(expression)
        condition_bool = bool(evaluated_outcome)

        self.log("INFO", f"Evaluated condition '{expression}' => {condition_bool}")

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables={
                "outcome": condition_bool,
                "branch_taken": "True" if condition_bool else "False"
            },
            metrics={
                "expression": expression,
                "outcome": condition_bool
            }
        )
