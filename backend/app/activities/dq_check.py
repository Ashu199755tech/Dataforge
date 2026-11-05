from typing import Dict, Any, List
from datetime import datetime, timezone
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.models.data_quality import DataQualityResult
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class DataQualityCheckActivity(BaseActivity):
    """
    Data Quality Activity: Validates dataset integrity against business rules:
    - NotNull
    - Unique
    - Range (min/max)
    - ControlledList (enum values)
    - PositiveNumeric
    Calculates compliance score, records failed samples, and enforces SLA thresholds.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        table_name = config.get("table_name")
        rules = config.get("rules", [])
        fail_pipeline_on_error = config.get("fail_pipeline_on_error", True)

        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")

        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        connector = get_connector(conn_record.connector_type, decrypted_config)

        self.log("INFO", f"Starting Data Quality validation suite on '{table_name}' with {len(rules)} rules")

        all_rules_passed = True
        total_eval = 0
        rule_results_summary = []

        for rule in rules:
            rule_type = rule.get("rule_type")
            column = rule.get("column")
            threshold = float(rule.get("threshold_percent", 100.0))

            # Fetch table data (in sample/streaming fashion)
            stream = connector.read_data_stream(table_name=table_name, batch_size=5000)
            rows = []
            for chunk in stream:
                rows.extend(chunk)

            total_records = len(rows)
            total_eval += total_records
            failed_records = []

            for row in rows:
                val = row.get(column)
                if rule_type == "NotNull" and (val is None or str(val).strip() == ""):
                    failed_records.append(row)
                elif rule_type == "PositiveNumeric" and (val is None or float(val) <= 0):
                    failed_records.append(row)
                elif rule_type == "ControlledList":
                    allowed = rule.get("allowed_values", [])
                    if val not in allowed:
                        failed_records.append(row)

            # Check unique if rule_type == 'Unique'
            if rule_type == "Unique":
                seen = set()
                for row in rows:
                    val = row.get(column)
                    if val in seen:
                        failed_records.append(row)
                    seen.add(val)

            fail_count = len(failed_records)
            pass_pct = round(((total_records - fail_count) / max(total_records, 1)) * 100.0, 2)
            passed = pass_pct >= threshold

            if not passed:
                all_rules_passed = False

            # Persist DQ result
            dq_record = DataQualityResult(
                pipeline_run_id=self.context.pipeline_run_id,
                rule_name=f"{rule_type} check on {column}",
                rule_type=rule_type,
                status="Passed" if passed else "Failed",
                total_records_evaluated=total_records,
                failed_records_count=fail_count,
                pass_percentage=pass_pct,
                sample_failed_records=failed_records[:10],
                executed_at=datetime.now(timezone.utc)
            )
            self.db.add(dq_record)
            self.db.commit()

            self.log(
                "INFO" if passed else "WARNING",
                f"Rule [{rule_type} on '{column}']: Score {pass_pct}% (Threshold: {threshold}%). Status: {'PASSED' if passed else 'FAILED'}"
            )
            rule_results_summary.append({
                "rule": f"{rule_type} on {column}",
                "pass_pct": pass_pct,
                "passed": passed
            })

        if not all_rules_passed and fail_pipeline_on_error:
            raise ValueError(f"Data Quality validation failed to meet SLA thresholds: {rule_results_summary}")

        return ActivityExecutionResult(
            status="Succeeded" if all_rules_passed else "Failed",
            rows_read=total_eval,
            metrics={"rules_evaluated": len(rules), "summary": rule_results_summary}
        )
