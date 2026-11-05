from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class FilterActivity(BaseActivity):
    """
    Filter Activity:
    Takes an input array and filters elements using a boolean predicate expression.
    Exposes filtered results in @activity('Filter').output.value and count.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        raw_items = config.get("items", [])
        condition_expr = config.get("condition")

        if not condition_expr:
            raise ValueError("Condition expression is required for FilterActivity.")

        # Evaluate input array
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        if isinstance(raw_items, str):
            items = evaluator.evaluate(raw_items)
        else:
            items = raw_items

        if not isinstance(items, list):
            items = [items] if items is not None else []

        self.log("INFO", f"Filtering array of {len(items)} items using condition: '{condition_expr}'")

        filtered = []
        for itm in items:
            item_evaluator = ExpressionEvaluator(
                parameters=self.context.pipeline_parameters,
                variables=self.context.pipeline_variables,
                item=itm
            )
            cond_res = item_evaluator.evaluate(condition_expr)
            if bool(cond_res):
                filtered.append(itm)

        self.log("INFO", f"Filtering complete: {len(filtered)} of {len(items)} items passed condition.")

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables={
                "value": filtered,
                "count": len(filtered)
            },
            metrics={
                "input_count": len(items),
                "filtered_count": len(filtered)
            }
        )
