import os
import subprocess
import time
from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class CustomActivity(BaseActivity):
    """
    Custom Activity:
    Executes a custom CLI command, script, or batch executable in an
    isolated environment with timeout management and live log streaming.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        command = config.get("command")
        args = config.get("arguments", [])
        working_dir = config.get("working_dir") or "."
        timeout_seconds = max(1, min(int(config.get("timeout_seconds", 120)), 7200))
        env_vars = config.get("environment_variables", {})

        if not command:
            raise ValueError("Command is required for CustomActivity.")

        # Evaluate arguments with expressions
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_cmd = evaluator.evaluate(command)
        resolved_args = evaluator.evaluate(args)

        full_cmd_list = [resolved_cmd] + [str(a) for a in resolved_args]
        self.log("INFO", f"Executing custom command: {' '.join(full_cmd_list)} (timeout: {timeout_seconds}s)")

        merged_env = os.environ.copy()
        if env_vars:
            merged_env.update(env_vars)

        start_time = time.time()
        try:
            proc = subprocess.Popen(
                full_cmd_list,
                cwd=working_dir,
                env=merged_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            stdout_str, stderr_str = proc.communicate(timeout=timeout_seconds)
            exit_code = proc.returncode
            duration = round(time.time() - start_time, 2)

            if stdout_str:
                for line in stdout_str.strip().split("\n"):
                    if line.strip():
                        self.log("INFO", f"[stdout] {line.strip()}")

            if stderr_str:
                for line in stderr_str.strip().split("\n"):
                    if line.strip():
                        self.log("WARN" if exit_code == 0 else "ERROR", f"[stderr] {line.strip()}")

            if exit_code != 0:
                return ActivityExecutionResult(
                    status="Failed",
                    error_message=f"Command exited with code {exit_code}: {stderr_str or stdout_str}",
                    metrics={"duration_seconds": duration, "exit_code": exit_code}
                )

            return ActivityExecutionResult(
                status="Succeeded",
                output_variables={"exit_code": exit_code, "duration_seconds": duration},
                metrics={"duration_seconds": duration, "exit_code": exit_code}
            )

        except subprocess.TimeoutExpired:
            proc.kill()
            duration = round(time.time() - start_time, 2)
            self.log("ERROR", f"Custom command timed out after {timeout_seconds}s.")
            return ActivityExecutionResult(
                status="Failed",
                error_message=f"Command timed out after {timeout_seconds} seconds.",
                metrics={"duration_seconds": duration}
            )
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            return ActivityExecutionResult(
                status="Failed",
                error_message=str(e),
                metrics={"duration_seconds": duration}
            )
