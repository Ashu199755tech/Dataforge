from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.worker import IsolatedSubprocessWorker
from backend.app.execution.expressions import ExpressionEvaluator


class PythonScriptActivity(BaseActivity):
    """
    Python Script Activity:
    Executes Python data science transformations, API enrichments, or custom scripts
    within an isolated child worker process with strict timeout guards and stdout/stderr capture.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        script_code = config.get("script") or config.get("code")
        raw_parameters = config.get("parameters", {})
        timeout_seconds = max(1, min(int(config.get("timeout_seconds", 60)), 3600))
        env_vars = config.get("environment_variables", {})

        if not script_code:
            raise ValueError("Script code is required for PythonScriptActivity.")

        # Dynamically evaluate input parameter expressions
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_params = evaluator.evaluate(raw_parameters)

        self.log(
            "INFO",
            f"Launching sandboxed Python execution (timeout: {timeout_seconds}s, parameters: {list(resolved_params.keys())})"
        )

        worker = IsolatedSubprocessWorker(timeout_seconds=timeout_seconds)
        result = worker.execute_python_script(
            script_code=script_code,
            parameters=resolved_params,
            environment_variables=env_vars,
            log_callback=self.log
        )

        self.log(
            "INFO" if result.exit_code == 0 else "ERROR",
            f"Python execution finished in {result.duration_seconds}s with exit code {result.exit_code}"
        )

        if result.is_timeout:
            return ActivityExecutionResult(
                status="Failed",
                error_message=f"Python script timed out after {timeout_seconds} seconds.",
                metrics={"duration_seconds": result.duration_seconds}
            )

        if result.exit_code != 0:
            error_details = result.stderr or result.stdout or f"Process exited with non-zero exit code: {result.exit_code}"
            return ActivityExecutionResult(
                status="Failed",
                error_message=error_details,
                output_variables=result.output_variables,
                metrics={"duration_seconds": result.duration_seconds}
            )

        return ActivityExecutionResult(
            status="Succeeded",
            output_variables=result.output_variables,
            metrics={
                "duration_seconds": result.duration_seconds,
                "output_keys_count": len(result.output_variables)
            }
        )
