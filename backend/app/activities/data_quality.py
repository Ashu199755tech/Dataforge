import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import polars as pl

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.models.data_quality import DataQualityResult
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.dataquality.engine import DataQualityEngine


class DataQualityActivity(BaseActivity):
    """
    Enterprise Data Quality Activity.
    Validates dataset integrity against business rules:
      - MandatoryFieldCheck
      - NonBlankCheck
      - NullValidation
      - DuplicateCheck
      - PrimaryKeyUniqueness
      - ReferentialIntegrity
      - RangeValidation
      - DateValidation
      - ControlledListValidation
      - SchemaValidation
      - SchemaDriftDetection
      - RowCountValidation
      - PIIDetection
    Calculates composite DQ score, captures quarantine records, and enforces threshold gates.
    """

    def _load_polars_df(self, connection_id: Optional[str], table_name: Optional[str], file_path: Optional[str]) -> pl.DataFrame:
        if file_path:
            norm_path = os.path.abspath(file_path)
            if not os.path.exists(norm_path):
                raise FileNotFoundError(f"Dataset file '{norm_path}' not found")
            if norm_path.endswith(".parquet"):
                return pl.read_parquet(norm_path)
            elif norm_path.endswith(".json"):
                return pl.read_json(norm_path)
            else:
                return pl.read_csv(norm_path)

        if connection_id and table_name:
            conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
            if not conn_record:
                raise ValueError(f"Connection ID '{connection_id}' not found")
            decrypted = decrypt_secret(conn_record.config_encrypted)
            connector = get_connector(conn_record.connector_type, decrypted)
            stream = connector.read_data_stream(table_name=table_name, batch_size=10000)
            rows = []
            for chunk in stream:
                rows.extend(chunk)
            if rows:
                return pl.DataFrame(rows)
            return pl.DataFrame()

        raise ValueError("Either file_path or connection_id + table_name must be provided")

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        table_name = config.get("table_name")
        file_path = config.get("file_path")
        fail_on_error = config.get("fail_pipeline_on_error", True)

        # Resolve rules dynamically from local PC, cloud storage (S3/ADLS/GCS), or database tables (Snowflake)
        from backend.app.dataquality.rulebook_resolver import RulebookResolver
        rules, min_score = RulebookResolver.resolve_rules(
            config=config,
            db=self.db,
            logger_fn=self.log
        )

        ref_conn_id = config.get("reference_connection_id")
        ref_table = config.get("reference_table_name")
        ref_file = config.get("reference_file_path")

        target_name = table_name or file_path or "Dataset"
        self.log("INFO", f"Starting Enterprise Data Quality validation on '{target_name}' with {len(rules)} rules")

        df = self._load_polars_df(connection_id, table_name, file_path)

        # Load optional reference dataset for referential integrity
        ref_df = None
        if ref_conn_id or ref_file:
            try:
                ref_df = self._load_polars_df(ref_conn_id, ref_table, ref_file)
            except Exception as e:
                self.log("WARNING", f"Could not load reference dataset: {str(e)}")

        # Execute rules using DataQualityEngine
        eval_result = DataQualityEngine.evaluate_rules(
            df=df,
            rules=rules,
            min_score_threshold=min_score,
            ref_df=ref_df
        )

        composite_score = eval_result["composite_dq_score"]
        overall_status = eval_result["overall_status"]
        quarantine_count = eval_result["quarantine_count"]

        # Persist rule results
        for r_res in eval_result["rule_results"]:
            dq_rec = DataQualityResult(
                pipeline_run_id=self.context.pipeline_run_id,
                rule_name=r_res["rule_name"],
                rule_type=r_res["rule_type"],
                status=r_res["status"],
                total_records_evaluated=r_res["total_records"],
                failed_records_count=r_res["failed_records_count"],
                pass_percentage=r_res["pass_percentage"],
                sample_failed_records=r_res["sample_failed_records"],
                executed_at=datetime.now(timezone.utc)
            )
            self.db.add(dq_rec)

        self.db.commit()

        # Handle optional quarantine export
        quarantine_path = config.get("quarantine_path")
        if quarantine_path and eval_result["quarantine_records"]:
            try:
                q_df = pl.DataFrame(eval_result["quarantine_records"])
                norm_q_path = os.path.abspath(quarantine_path)
                os.makedirs(os.path.dirname(norm_q_path), exist_ok=True)
                if norm_q_path.endswith(".parquet"):
                    q_df.write_parquet(norm_q_path)
                elif norm_q_path.endswith(".json"):
                    q_df.write_json(norm_q_path)
                else:
                    q_df.write_csv(norm_q_path)
                self.log("INFO", f"Captured {quarantine_count} quarantine records to '{norm_q_path}'")
            except Exception as qe:
                self.log("ERROR", f"Failed to export quarantine dataset: {str(qe)}")

        self.log(
            "INFO" if overall_status == "Passed" else ("WARNING" if overall_status == "Warning" else "ERROR"),
            f"Data Quality validation complete. Composite DQ Score: {composite_score}% (Threshold: {min_score}%). Status: {overall_status}. Quarantine count: {quarantine_count}"
        )

        if overall_status == "Failed" and fail_on_error:
            return ActivityExecutionResult(
                status="Failed",
                rows_read=eval_result["total_records"],
                rows_written=quarantine_count,
                error_message=f"Data Quality threshold failed: Score {composite_score}% < Required {min_score}% or critical rule violated.",
                output_variables={
                    "dq_score": composite_score,
                    "overall_status": overall_status,
                    "rules_evaluated": eval_result["rules_evaluated"],
                    "rules_passed": eval_result["rules_passed"],
                    "rules_failed": eval_result["rules_failed"],
                    "quarantine_count": quarantine_count,
                    "quarantine_sample": eval_result["quarantine_records"][:10],
                    "rule_results": eval_result["rule_results"]
                }
            )

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=eval_result["total_records"],
            rows_written=quarantine_count,
            output_variables={
                "dq_score": composite_score,
                "overall_status": overall_status,
                "rules_evaluated": eval_result["rules_evaluated"],
                "rules_passed": eval_result["rules_passed"],
                "rules_failed": eval_result["rules_failed"],
                "quarantine_count": quarantine_count,
                "quarantine_sample": eval_result["quarantine_records"][:10],
                "rule_results": eval_result["rule_results"]
            }
        )
