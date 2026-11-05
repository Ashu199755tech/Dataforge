from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionContext, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class SwitchActivity(BaseActivity):
    """
    Switch Activity:
    Evaluates an expression and routes execution to a matching case branch,
    or executes default sub-activities if no cases match.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        raw_expr = config.get("expression")
        cases = config.get("cases", [])
        default_activities = config.get("default_activities", [])

        if not raw_expr:
            raise ValueError("Expression is required for SwitchActivity.")

        # Evaluate switch expression
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        evaluated_val = str(evaluator.evaluate(raw_expr)).strip()

        self.log("INFO", f"Switch condition evaluated to: '{evaluated_val}'")

        # Find matching case
        selected_activities = None
        matched_case_name = None

        for case_item in cases:
            case_val = str(case_item.get("value", "")).strip()
            if case_val == evaluated_val:
                selected_activities = case_item.get("activities", [])
                matched_case_name = case_val
                break

        if selected_activities is None:
            self.log("INFO", "No matching case found. Routing to default branch.")
            selected_activities = default_activities
            matched_case_name = "default"
        else:
            self.log("INFO", f"Matched case: '{matched_case_name}'. Executing {len(selected_activities)} sub-activities.")

        # Execute selected branch sub-activities
        from backend.app.activities.factory import get_activity_instance
        for idx, sub_act_cfg in enumerate(selected_activities):
            sub_evaluator = ExpressionEvaluator(
                parameters=self.context.pipeline_parameters,
                variables=self.context.pipeline_variables
            )
            resolved_sub_cfg = sub_evaluator.evaluate(sub_act_cfg.get("config", {}))

            sub_ctx = ActivityExecutionContext(
                pipeline_run_id=self.context.pipeline_run_id,
                activity_id=f"{self.context.activity_id}_{matched_case_name}_{idx}_{sub_act_cfg.get('id', 'sub')}",
                activity_name=f"{sub_act_cfg.get('name', 'sub')} [{matched_case_name}]",
                activity_type=sub_act_cfg.get("type", "Wait"),
                config=resolved_sub_cfg,
                pipeline_parameters=self.context.pipeline_parameters,
                pipeline_variables=self.context.pipeline_variables
            )

            executor = get_activity_instance(sub_ctx, self.db)
            res = executor.execute()
            if res.status == "Failed":
                return ActivityExecutionResult(
                    status="Failed",
                    error_message=f"Sub-activity '{sub_act_cfg.get('name')}' in case '{matched_case_name}' failed: {res.error_message}"
                )

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables={
                "matched_case": matched_case_name,
                "evaluated_value": evaluated_val
            }
        )
