import os
import sys
import shutil
import subprocess
import time
from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.execution.expressions import ExpressionEvaluator


class PySparkJobActivity(BaseActivity):
    """
    PySpark Job Activity:
    Submits a PySpark or Apache Spark distributed job using spark-submit
    with driver/executor memory limits, cluster master URLs, and arguments.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        script_path = config.get("script_path") or config.get("app_file")
        spark_master = config.get("master", "local[*]")
        spark_args = config.get("spark_args", [])
        app_args = config.get("app_args", [])
        timeout_seconds = max(10, min(int(config.get("timeout_seconds", 600)), 7200))

        if not script_path:
            raise ValueError("'script_path' is required for PySparkJobActivity.")

        # Check if spark-submit exists in environment PATH
        spark_submit_bin = shutil.which("spark-submit")
        if not spark_submit_bin:
            # Fall back to python runner if file exists
            if os.path.exists(script_path):
                self.log("WARN", "spark-submit binary not found in system PATH. Executing script via local Python runtime.")
                cmd = [sys.executable, script_path] + [str(a) for a in app_args]
            else:
                raise RuntimeError(
                    f"spark-submit is not installed or available in PATH, and script '{script_path}' was not found locally."
                )
        else:
            cmd = [spark_submit_bin, "--master", spark_master] + spark_args + [script_path] + [str(a) for a in app_args]

        self.log("INFO", f"Submitting Spark job: {' '.join(cmd)}")

        start_time = time.time()
        try:
            proc = subprocess.Popen(
                cmd,
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
                        self.log("INFO", f"[Spark] {line.strip()}")

            if exit_code != 0:
                return ActivityExecutionResult(
                    status="Failed",
                    error_message=f"Spark job exited with code {exit_code}: {stderr_str or stdout_str}",
                    metrics={"duration_seconds": duration, "exit_code": exit_code}
                )

            return ActivityExecutionResult(
                status="Succeeded",
                output_variables={"exit_code": exit_code, "duration_seconds": duration},
                metrics={"duration_seconds": duration}
            )

        except subprocess.TimeoutExpired:
            proc.kill()
            return ActivityExecutionResult(
                status="Failed",
                error_message=f"Spark job timed out after {timeout_seconds} seconds."
            )
