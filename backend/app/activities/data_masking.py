import os
from typing import Dict, Any, List, Optional
import polars as pl

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.dataquality.engine import DataQualityEngine


class DataMaskingActivity(BaseActivity):
    """
    Data Masking Activity.
    Applies security masking strategies (redact, hash, partial_mask, nullify)
    to sensitive PII columns and writes masked output to destination.
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
        s_conn = config.get("source_connection_id")
        s_tbl = config.get("source_table_name")
        s_file = config.get("source_file_path")

        dest_file = config.get("destination_file_path")
        masking_rules = config.get("masking_rules", [])

        source_name = s_tbl or s_file or "Dataset"
        self.log("INFO", f"Starting Data Masking on '{source_name}' with {len(masking_rules)} masking rules")

        df = self._load_polars_df(s_conn, s_tbl, s_file)
        masked_df = DataQualityEngine.apply_masking(df, masking_rules)

        total_masked_records = len(masked_df)

        if dest_file:
            norm_dest = os.path.abspath(dest_file)
            os.makedirs(os.path.dirname(norm_dest), exist_ok=True)
            if norm_dest.endswith(".parquet"):
                masked_df.write_parquet(norm_dest)
            elif norm_dest.endswith(".json"):
                masked_df.write_json(norm_dest)
            else:
                masked_df.write_csv(norm_dest)
            self.log("INFO", f"Masked dataset written to '{norm_dest}' ({total_masked_records} rows)")

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=total_masked_records,
            rows_written=total_masked_records,
            outputs={
                "masked_records_count": total_masked_records,
                "destination_file_path": dest_file,
                "masked_columns": [r.get("column") for r in masking_rules]
            }
        )
