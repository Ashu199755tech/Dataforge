import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import polars as pl

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.models.data_quality import ReconciliationResult
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.dataquality.engine import DataQualityEngine


class ReconciliationActivity(BaseActivity):
    """
    Source-to-Target Data Reconciliation Activity.
    Validates row parity, key mismatch counts, and numeric sum/average checksums
    between source and target systems.
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

        # Source config
        s_conn = config.get("source_connection_id")
        s_tbl = config.get("source_table_name")
        s_file = config.get("source_file_path")
        source_name = s_tbl or s_file or "Source"

        # Target config
        t_conn = config.get("target_connection_id")
        t_tbl = config.get("target_table_name")
        t_file = config.get("target_file_path")
        target_name = t_tbl or t_file or "Target"

        key_columns = config.get("key_columns", [])
        numeric_sum_cols = config.get("numeric_sum_columns", [])
        fail_on_discrepancy = config.get("fail_on_discrepancy", True)

        self.log("INFO", f"Starting Reconciliation: Source '{source_name}' vs Target '{target_name}'")

        source_df = self._load_polars_df(s_conn, s_tbl, s_file)
        target_df = self._load_polars_df(t_conn, t_tbl, t_file)

        recon_result = DataQualityEngine.reconcile(
            source_df=source_df,
            target_df=target_df,
            key_columns=key_columns,
            numeric_sum_columns=numeric_sum_cols
        )

        status = recon_result["reconciliation_status"]

        # Persist reconciliation record
        rec_record = ReconciliationResult(
            pipeline_run_id=self.context.pipeline_run_id,
            source_dataset=source_name,
            target_dataset=target_name,
            source_rows=recon_result["source_records"],
            target_rows=recon_result["target_records"],
            row_variance=recon_result["row_variance"],
            status=status,
            details=recon_result,
            reconciled_at=datetime.now(timezone.utc)
        )
        self.db.add(rec_record)
        self.db.commit()

        self.log(
            "INFO" if status == "MATCHED" else "ERROR",
            f"Reconciliation Status: {status}. Source rows: {recon_result['source_records']}, Target rows: {recon_result['target_records']}, Variance: {recon_result['row_variance']}"
        )

        if status == "DISCREPANCY_DETECTED" and fail_on_discrepancy:
            return ActivityExecutionResult(
                status="Failed",
                rows_read=recon_result["source_records"],
                rows_written=recon_result["target_records"],
                error_message=f"Reconciliation discrepancy detected: source has {recon_result['source_records']} rows, target has {recon_result['target_records']} rows (variance: {recon_result['row_variance']})",
                output_variables=recon_result
            )

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=recon_result["source_records"],
            rows_written=recon_result["target_records"],
            output_variables=recon_result
        )
