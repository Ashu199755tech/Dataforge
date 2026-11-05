from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class FailActivity(BaseActivity):
    """
    Fail Activity:
    Deliberately triggers an activity failure with a user-defined error code
    and message. Enables explicit error handling and conditional pipeline termination.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        raw_message = config.get("message", "User deliberate failure triggered")
        error_code = config.get("error_code", "UserError")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_msg = evaluator.evaluate(raw_message)

        full_error = f"[{error_code}] {resolved_msg}"
        self.log("ERROR", f"FailActivity executing: {full_error}")

        return ActivityExecutionResult(
            status="Failed",
            error_message=full_error,
            output_variables={"error_code": error_code, "message": str(resolved_msg)}
        )
