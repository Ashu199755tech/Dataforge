import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import polars as pl

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.models.data_quality import DataProfileResult
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.dataquality.engine import DataQualityEngine


class DataProfilingActivity(BaseActivity):
    """
    Data Profiling Activity:
    Calculates detailed statistical profiles (min, max, mean, stddev, null counts,
    distinct counts, uniqueness percentages, and top frequent values).
    Persists profile to `data_profile_results` table and sets execution outputs.
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
        dataset_name = table_name or file_path or "Dataset"

        self.log("INFO", f"Starting statistical data profiling on '{dataset_name}'")

        df = self._load_polars_df(connection_id, table_name, file_path)
        profile_res = DataQualityEngine.profile_dataset(df)

        # Persist profile result
        prof_record = DataProfileResult(
            pipeline_run_id=self.context.pipeline_run_id,
            dataset_name=dataset_name,
            total_rows=profile_res["total_rows"],
            total_columns=profile_res["total_columns"],
            column_profiles=profile_res["columns"],
            profiled_at=datetime.now(timezone.utc)
        )
        self.db.add(prof_record)
        self.db.commit()

        self.log(
            "INFO",
            f"Data profiling complete for '{dataset_name}': {profile_res['total_rows']} rows, {profile_res['total_columns']} columns profiled."
        )

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=profile_res["total_rows"],
            rows_written=0,
            output_variables={
                "dataset_name": dataset_name,
                "total_rows": profile_res["total_rows"],
                "total_columns": profile_res["total_columns"],
                "columns": profile_res["columns"]
            }
        )
