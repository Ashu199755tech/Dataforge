import os
import re
import time
import json
import shutil
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.core.security import decrypt_secret
from backend.app.execution.expressions import ExpressionEvaluator


class DbtActivity(BaseActivity):
    """
    Enterprise dbt (Data Build Tool) Activity.
    Orchestrates transformation pipelines across two distinct modes:
      1. dbt Core: Invokes local CLI (dbt run, dbt test, dbt build, dbt seed)
         inside sandboxed subprocesses with model selectors, profile targets, and vars.
      2. dbt Cloud: Submits remote jobs via the official dbt Cloud REST API v2,
         polls execution progress, and captures run telemetry and artifacts.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        mode = str(config.get("mode", "core")).strip().lower()

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )

        if mode in ("cloud", "dbt_cloud", "api"):
            return self._execute_dbt_cloud(config, evaluator)
        else:
            return self._execute_dbt_core(config, evaluator)

    def _execute_dbt_core(self, config: Dict[str, Any], evaluator: ExpressionEvaluator) -> ActivityExecutionResult:
        """Executes dbt Core CLI operations."""
        start_time = time.time()
        command = str(evaluator.evaluate(config.get("command", "run"))).lower().strip()
        project_dir = str(evaluator.evaluate(config.get("project_dir", ".")))
        profiles_dir = str(evaluator.evaluate(config.get("profiles_dir", "")))
        select = str(evaluator.evaluate(config.get("select") or config.get("models") or ""))
        target = str(evaluator.evaluate(config.get("target", "")))
        custom_vars = config.get("vars", {})
        timeout_seconds = int(config.get("timeout_seconds", 3600))
        mock_mode = config.get("mock_mode", False)

        resolved_vars = evaluator.evaluate(custom_vars) if isinstance(custom_vars, dict) else custom_vars

        self.log("INFO", f"Starting dbt Core: 'dbt {command}' (Project: '{project_dir}', Select: '{select or 'all'}')")

        if mock_mode or config.get("simulate", False):
            duration = 1.85
            self.log("INFO", f"[Mock] dbt {command} finished successfully in {duration}s")
            return ActivityExecutionResult(
                status="Succeeded",
                rows_read=50,
                rows_written=50,
                duration_seconds=duration,
                output_variables={
                    "mode": "core",
                    "command": f"dbt {command}",
                    "models_run": 5,
                    "models_passed": 5,
                    "models_failed": 0,
                    "duration_seconds": duration,
                    "logs_summary": f"Completed 5 models with 0 errors via dbt {command}"
                }
            )

        dbt_executable = shutil.which("dbt")
        if not dbt_executable:
            return ActivityExecutionResult(
                status="Failed",
                error_message="dbt CLI executable not found on host. Install dbt-core and the required adapter (e.g. dbt-snowflake, dbt-postgres)."
            )

        cmd = [dbt_executable, command]
        if project_dir and os.path.exists(project_dir):
            cmd.extend(["--project-dir", os.path.abspath(project_dir)])
        if profiles_dir and os.path.exists(profiles_dir):
            cmd.extend(["--profiles-dir", os.path.abspath(profiles_dir)])
        if select:
            cmd.extend(["--select", str(select)])
        if target:
            cmd.extend(["--target", str(target)])
        if resolved_vars:
            cmd.extend(["--vars", json.dumps(resolved_vars)])

        self.log("DEBUG", f"Running command: {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.path.abspath(project_dir) if os.path.exists(project_dir) else None
            )
            stdout_output, _ = proc.communicate(timeout=timeout_seconds)
            duration = round(time.time() - start_time, 2)

            # Parse dbt console output
            models_run = 0
            models_passed = 0
            models_failed = 0
            pass_match = re.search(r"PASS=(\d+)", stdout_output)
            warn_match = re.search(r"WARN=(\d+)", stdout_output)
            err_match = re.search(r"ERROR=(\d+)", stdout_output)
            total_match = re.search(r"TOTAL=(\d+)", stdout_output)

            if total_match:
                models_run = int(total_match.group(1))
            if pass_match:
                models_passed = int(pass_match.group(1))
            if err_match:
                models_failed = int(err_match.group(1))

            if proc.returncode != 0:
                self.log("ERROR", f"dbt execution failed with code {proc.returncode}:\n{stdout_output[-1000:]}")
                err_snippet = (stdout_output[-500:].strip() or stderr_output[-500:].strip()) if (stdout_output or stderr_output) else ""
                err_msg = f"dbt command exited with non-zero status code {proc.returncode}."
                if err_snippet:
                    err_msg += f" {err_snippet}"
                return ActivityExecutionResult(
                    status="Failed",
                    error_message=err_msg,
                    duration_seconds=duration,
                    output_variables={
                        "mode": "core",
                        "command": " ".join(cmd),
                        "return_code": proc.returncode,
                        "models_run": models_run,
                        "models_passed": models_passed,
                        "models_failed": models_failed or 1,
                        "logs_summary": stdout_output[-2000:]
                    }
                )

            self.log("INFO", f"dbt {command} finished successfully in {duration}s")
            return ActivityExecutionResult(
                status="Succeeded",
                duration_seconds=duration,
                output_variables={
                    "mode": "core",
                    "command": " ".join(cmd),
                    "return_code": 0,
                    "models_run": models_run,
                    "models_passed": models_passed,
                    "models_failed": 0,
                    "logs_summary": stdout_output[-2000:]
                }
            )

        except subprocess.TimeoutExpired:
            proc.kill()
            return ActivityExecutionResult(
                status="Failed",
                error_message=f"dbt execution exceeded timeout threshold of {timeout_seconds} seconds."
            )
        except Exception as ex:
            return ActivityExecutionResult(
                status="Failed",
                error_message=f"Failed to execute dbt CLI subprocess: {str(ex)}"
            )

    def _execute_dbt_cloud(self, config: Dict[str, Any], evaluator: ExpressionEvaluator) -> ActivityExecutionResult:
        """Executes dbt Cloud remote job triggers and status polling."""
        start_time = time.time()
        account_id = str(config.get("account_id", "")).strip()
        job_id = str(config.get("job_id", "")).strip()
        token = config.get("api_token") or config.get("token")
        connection_id = config.get("connection_id")
        git_branch = config.get("git_branch")
        poll_interval = max(5, int(config.get("poll_interval_seconds", 10)))
        timeout_seconds = max(60, int(config.get("timeout_seconds", 3600)))
        mock_mode = config.get("mock_mode", False)

        if connection_id:
            conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
            if conn_record:
                decrypted = decrypt_secret(conn_record.config_encrypted)
                account_id = decrypted.get("account_id", account_id)
                job_id = decrypted.get("job_id", job_id)
                token = decrypted.get("api_token") or decrypted.get("token", token)

        if mock_mode or config.get("simulate", False):
            duration = 2.4
            self.log("INFO", f"[Mock] Triggered dbt Cloud Job #{job_id or 1234} for Account #{account_id or 5678}")
            return ActivityExecutionResult(
                status="Succeeded",
                duration_seconds=duration,
                output_variables={
                    "mode": "cloud",
                    "run_id": "mock_dbt_run_9988",
                    "account_id": account_id or "5678",
                    "job_id": job_id or "1234",
                    "status_human": "Success",
                    "duration_seconds": duration,
                    "logs_summary": "dbt Cloud job run #mock_dbt_run_9988 completed successfully."
                }
            )

        if not account_id or not job_id or not token:
            raise ValueError("dbt Cloud execution requires 'account_id', 'job_id', and 'api_token'.")

        self.log("INFO", f"Triggering dbt Cloud Job #{job_id} for Account #{account_id}")

        trigger_url = f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/jobs/{job_id}/run/"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "DataForge/1.0"
        }
        trigger_body = {"cause": f"Triggered by DataForge Activity: {self.context.activity_name}"}
        if git_branch:
            trigger_body["git_branch"] = git_branch

        req = urllib.request.Request(
            trigger_url,
            data=json.dumps(trigger_body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                run_id = str(data.get("data", {}).get("id"))
                self.log("INFO", f"dbt Cloud Run #{run_id} triggered successfully. Awaiting completion...")
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8")
            raise RuntimeError(f"dbt Cloud API Trigger Error ({e.code}): {err}")
        except Exception as e:
            raise RuntimeError(f"Failed to trigger dbt Cloud job: {str(e)}")

        # Poll run status
        poll_url = f"https://cloud.getdbt.com/api/v2/accounts/{account_id}/runs/{run_id}/"
        while (time.time() - start_time) < timeout_seconds:
            time.sleep(poll_interval)
            try:
                poll_req = urllib.request.Request(poll_url, headers=headers, method="GET")
                with urllib.request.urlopen(poll_req, timeout=30) as p_resp:
                    p_data = json.loads(p_resp.read().decode("utf-8")).get("data", {})
                    status_code = p_data.get("status")
                    status_human = p_data.get("status_human", str(status_code))

                    self.log("INFO", f"dbt Cloud Run #{run_id} status: {status_human}")

                    # dbt Cloud status: 10 = Success, 20 = Error, 30 = Canceled
                    if status_code == 10:
                        duration = round(time.time() - start_time, 2)
                        return ActivityExecutionResult(
                            status="Succeeded",
                            duration_seconds=duration,
                            output_variables={
                                "mode": "cloud",
                                "run_id": run_id,
                                "status_human": status_human,
                                "duration_seconds": duration,
                                "logs_summary": f"dbt Cloud Run #{run_id} finished with status Success"
                            }
                        )
                    elif status_code in (20, 30):
                        return ActivityExecutionResult(
                            status="Failed",
                            error_message=f"dbt Cloud job run #{run_id} failed with status: {status_human}",
                            output_variables={
                                "mode": "cloud",
                                "run_id": run_id,
                                "status_human": status_human
                            }
                        )
            except Exception as pe:
                self.log("WARNING", f"Error polling dbt Cloud status: {str(pe)}")

        return ActivityExecutionResult(
            status="Failed",
            error_message=f"dbt Cloud run #{run_id} timed out after {timeout_seconds} seconds."
        )
