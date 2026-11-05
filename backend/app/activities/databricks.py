import time
from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.core.security import decrypt_secret
from backend.app.execution.providers.databricks import DatabricksExecutionProvider
from backend.app.execution.expressions import ExpressionEvaluator


class DatabricksNotebookActivity(BaseActivity):
    """
    Databricks Notebook Activity:
    Submits a remote Databricks notebook run via the Databricks Jobs REST API 2.1,
    monitors execution progress, and captures notebook return values.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        notebook_path = config.get("notebook_path")
        cluster_id = config.get("existing_cluster_id")
        base_parameters = config.get("base_parameters", {})
        poll_interval_seconds = max(5, int(config.get("poll_interval_seconds", 10)))
        timeout_seconds = max(60, int(config.get("timeout_seconds", 3600)))

        # Direct credentials fallback or connection lookup
        host = config.get("host")
        token = config.get("token")

        if connection_id:
            conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
            if conn_record:
                decrypted = decrypt_secret(conn_record.config_encrypted)
                host = decrypted.get("host", host)
                token = decrypted.get("token", token)

        if not host or not token or not notebook_path:
            raise ValueError("Databricks 'host', 'token', and 'notebook_path' are required.")

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_params = evaluator.evaluate(base_parameters)

        self.log("INFO", f"Submitting Databricks notebook: '{notebook_path}' to host '{host}'")

        provider = DatabricksExecutionProvider(host=host, token=token)
        job_spec = {
            "run_name": f"DataFlow_Run_{self.context.activity_name}",
            "notebook_task": {
                "notebook_path": notebook_path,
                "base_parameters": resolved_params
            }
        }
        if cluster_id:
            job_spec["existing_cluster_id"] = cluster_id
        else:
            job_spec["new_cluster"] = config.get("new_cluster", {
                "spark_version": "13.3.x-scala2.12",
                "node_type_id": "i3.xlarge",
                "num_workers": 1
            })

        handle = provider.submit_job(job_spec)
        self.log("INFO", f"Databricks Run submitted with Run ID: {handle.run_id}")

        start_clock = time.time()
        while time.time() - start_clock < timeout_seconds:
            status_handle = provider.get_job_status(job_id=handle.job_id, run_id=handle.run_id)
            self.log("INFO", f"Databricks Run #{handle.run_id} status: {status_handle.status} (result: {status_handle.result_state})")

            if status_handle.status in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
                if status_handle.result_state == "SUCCESS":
                    return ActivityExecutionResult(
                        status="Succeeded",
                        output_variables={
                            "run_id": handle.run_id,
                            "result_state": status_handle.result_state,
                            "duration_seconds": round(time.time() - start_clock, 2)
                        }
                    )
                else:
                    return ActivityExecutionResult(
                        status="Failed",
                        error_message=f"Databricks job ended with state {status_handle.result_state}: {status_handle.error_message}",
                        output_variables={"run_id": handle.run_id, "result_state": status_handle.result_state}
                    )

            time.sleep(poll_interval_seconds)

        provider.cancel_job(job_id=handle.job_id, run_id=handle.run_id)
        return ActivityExecutionResult(
            status="Failed",
            error_message=f"Databricks notebook execution timed out after {timeout_seconds} seconds."
        )
