import os
import time
from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.execution.expressions import ExpressionEvaluator


class ValidationActivity(BaseActivity):
    """
    Validation Activity:
    Validates that a dataset, file, or table exists and meets minimum size
    or row thresholds. Polling loops until criteria are satisfied or timeout expires.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        dataset_name = config.get("dataset_name") or config.get("table_name")
        file_path = config.get("file_path")
        timeout_seconds = max(1, min(int(config.get("timeout_seconds", 60)), 3600))
        sleep_interval = max(1, min(int(config.get("sleep_interval_seconds", 5)), 60))
        min_size = int(config.get("minimum_size_bytes", 0))
        min_rows = int(config.get("minimum_row_count", 0))

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        if dataset_name:
            dataset_name = evaluator.evaluate(dataset_name)
        if file_path:
            file_path = evaluator.evaluate(file_path)

        if not dataset_name and not file_path:
            raise ValueError("Either 'dataset_name' or 'file_path' is required for ValidationActivity.")

        connector = None
        if connection_id and self.db:
            conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
            if conn_record:
                decrypted = decrypt_secret(conn_record.config_encrypted)
                connector = get_connector(conn_record.connector_type, decrypted)

        self.log(
            "INFO",
            f"Beginning validation on '{dataset_name or file_path}' (timeout: {timeout_seconds}s, interval: {sleep_interval}s)"
        )

        start_time = time.time()
        attempts = 0

        while True:
            attempts += 1
            exists = False
            size_bytes = 0
            row_count = 0

            # 1. Direct local file validation
            if file_path and os.path.exists(file_path):
                exists = True
                size_bytes = os.path.getsize(file_path)

            # 2. Connector metadata validation
            elif connector and dataset_name:
                try:
                    meta = connector.get_metadata(dataset_name)
                    exists = bool(meta.get("exists", False))
                    size_bytes = int(meta.get("sizeInBytes", 0))
                    row_count = int(meta.get("rowCount", 0))
                except Exception as e:
                    self.log("WARN", f"Validation probe {attempts} failed: {str(e)}")
                    exists = False

            # Evaluate criteria
            criteria_met = exists and (size_bytes >= min_size) and (row_count >= min_rows)
            if criteria_met:
                duration = round(time.time() - start_time, 2)
                self.log(
                    "INFO",
                    f"Validation successful on attempt #{attempts} (size: {size_bytes}B, rows: {row_count}, duration: {duration}s)"
                )
                return ActivityExecutionResult(
                    status="Succeeded",
                    output_variables={
                        "exists": True,
                        "size_bytes": size_bytes,
                        "row_count": row_count,
                        "attempts": attempts,
                        "duration_seconds": duration
                    },
                    metrics={"attempts": attempts, "duration_seconds": duration}
                )

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout_seconds:
                duration = round(elapsed, 2)
                error_msg = (
                    f"Validation timed out after {duration}s ({attempts} attempts). "
                    f"Dataset exists={exists}, size={size_bytes}B (min: {min_size}B), rows={row_count} (min: {min_rows})"
                )
                self.log("ERROR", error_msg)
                return ActivityExecutionResult(
                    status="Failed",
                    error_message=error_msg,
                    output_variables={
                        "exists": exists,
                        "size_bytes": size_bytes,
                        "row_count": row_count,
                        "attempts": attempts,
                        "duration_seconds": duration
                    },
                    metrics={"attempts": attempts, "duration_seconds": duration}
                )

            # Sleep before next attempt
            time.sleep(sleep_interval)
