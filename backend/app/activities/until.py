from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionContext, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class UntilActivity(BaseActivity):
    """
    Until Activity:
    Executes a set of sub-activities repeatedly until a boolean expression
    evaluates to True, or until the maximum iteration threshold is reached.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        expression = config.get("expression")
        sub_activities = config.get("activities", [])
        max_iterations = max(1, min(int(config.get("max_iterations", 10)), 100))

        if not expression:
            raise ValueError("Expression is required for UntilActivity.")

        self.log("INFO", f"Until loop initialized with break condition: '{expression}' (max iterations: {max_iterations})")

        from backend.app.activities.factory import get_activity_instance
        iteration = 0
        condition_met = False

        while iteration < max_iterations:
            iteration += 1
            self.log("INFO", f"Until loop iteration #{iteration} started.")

            # Execute sub-activities
            for sub_act_cfg in sub_activities:
                evaluator = ExpressionEvaluator(
                    parameters=self.context.pipeline_parameters,
                    variables=self.context.pipeline_variables
                )
                resolved_cfg = evaluator.evaluate(sub_act_cfg.get("config", {}))

                sub_ctx = ActivityExecutionContext(
                    pipeline_run_id=self.context.pipeline_run_id,
                    activity_id=f"{self.context.activity_id}_iter{iteration}_{sub_act_cfg.get('id', 'sub')}",
                    activity_name=f"{sub_act_cfg.get('name', 'sub')} [Iter {iteration}]",
                    activity_type=sub_act_cfg.get("type", "Wait"),
                    config=resolved_cfg,
                    pipeline_parameters=self.context.pipeline_parameters,
                    pipeline_variables=self.context.pipeline_variables
                )

                executor = get_activity_instance(sub_ctx, self.db)
                res = executor.execute()
                if res.status == "Failed":
                    return ActivityExecutionResult(
                        status="Failed",
                        error_message=f"Sub-activity '{sub_act_cfg.get('name')}' in Until loop failed: {res.error_message}"
                    )
                # Merge output variables
                self.context.pipeline_variables.update(res.output_variables)

            # Evaluate break condition
            evaluator = ExpressionEvaluator(
                parameters=self.context.pipeline_parameters,
                variables=self.context.pipeline_variables
            )
            cond_val = evaluator.evaluate(expression)
            if bool(cond_val):
                self.log("INFO", f"Until break condition met at iteration #{iteration}.")
                condition_met = True
                break

        if not condition_met:
            self.log("WARN", f"Until loop reached maximum iteration threshold ({max_iterations}) without condition being met.")

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables={
                "iterations_completed": iteration,
                "condition_met": condition_met
            },
            metrics={"iterations": iteration}
        )
