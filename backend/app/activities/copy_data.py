import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class CopyDataActivity(BaseActivity):
    """
    Copy Data Activity: Extracts data from a source connector and loads
    it into a destination connector with streaming chunks, column mappings,
    full or incremental watermark ingestion, and merge/upsert support.
    """

    def _resolve_connector(self, connection_id: str):
        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")
        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        return get_connector(conn_record.connector_type, decrypted_config)

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        source_cfg = config.get("source", {})
        dest_cfg = config.get("destination", {})

        src_conn_id = source_cfg.get("connection_id")
        dst_conn_id = dest_cfg.get("connection_id")

        if not src_conn_id or not dst_conn_id:
            raise ValueError("Both source.connection_id and destination.connection_id must be specified.")

        self.log("INFO", f"Initializing Copy Data: {source_cfg.get('table_name')} -> {dest_cfg.get('table_name')}")

        src_connector = self._resolve_connector(src_conn_id)
        dst_connector = self._resolve_connector(dst_conn_id)

        src_table = source_cfg.get("table_name")
        dst_table = dest_cfg.get("table_name")
        batch_size = int(source_cfg.get("batch_size", 5000))
        write_mode = dest_cfg.get("write_mode", "append")
        key_columns = dest_cfg.get("key_columns", [])
        column_mappings = config.get("column_mappings", [])
        pre_copy_script = dest_cfg.get("pre_copy_script")
        post_copy_script = dest_cfg.get("post_copy_script")

        # Execute optional pre-copy script on destination
        if pre_copy_script and hasattr(dst_connector, "execute_query"):
            self.log("INFO", f"Executing pre-copy script on destination: {pre_copy_script}")
            dst_connector.execute_query(pre_copy_script)

        # Incremental watermark configuration
        incremental_cfg = source_cfg.get("incremental", {})
        watermark_col = incremental_cfg.get("column")
        watermark_val = incremental_cfg.get("watermark_value")
        
        # Resolve variables in watermark (e.g. @variables('last_watermark'))
        if isinstance(watermark_val, str) and watermark_val.startswith("@variables('"):
            var_name = watermark_val[12:-2]
            watermark_val = self.context.pipeline_variables.get(var_name)

        if watermark_col:
            self.log("INFO", f"Incremental loading enabled on column '{watermark_col}' > '{watermark_val}'")

        start_time = time.time()
        total_rows_read = 0
        total_rows_written = 0
        total_bytes = 0
        highest_watermark = watermark_val

        self.log("INFO", f"Beginning streaming extraction from '{src_table}' with batch size {batch_size}")

        stream_gen = src_connector.read_data_stream(
            table_name=src_table,
            columns=source_cfg.get("columns"),
            filter_expr=source_cfg.get("filter_expr"),
            watermark_column=watermark_col,
            watermark_value=watermark_val,
            batch_size=batch_size,
            schema_name=source_cfg.get("schema_name")
        )

        for batch_index, chunk in enumerate(stream_gen):
            chunk_size = len(chunk)
            total_rows_read += chunk_size
            
            # Estimate bytes
            chunk_json = json.dumps(chunk, default=str)
            total_bytes += len(chunk_json.encode("utf-8"))

            # Track watermark if column exists in chunk
            if watermark_col:
                for row in chunk:
                    row_val = row.get(watermark_col)
                    if row_val is not None:
                        if highest_watermark is None or str(row_val) > str(highest_watermark):
                            highest_watermark = row_val

            # Write batch to target
            mode = write_mode if batch_index == 0 else "append"
            if write_mode == "upsert":
                mode = "upsert"

            written = dst_connector.write_data_batch(
                table_name=dst_table,
                records=chunk,
                write_mode=mode,
                key_columns=key_columns,
                column_mappings=column_mappings,
                schema_name=dest_cfg.get("schema_name"),
                auto_create_table=dest_cfg.get("auto_create_table", True)
            )
            total_rows_written += written
            self.log("INFO", f"Batch #{batch_index + 1}: Transferred {written} rows to '{dst_table}'. Total rows written: {total_rows_written}")

        duration = round(time.time() - start_time, 2)
        self.log("INFO", f"Copy Data completed successfully: {total_rows_read} rows read, {total_rows_written} rows written ({total_bytes} bytes in {duration}s)")

        # Execute optional post-copy script on destination
        if post_copy_script and hasattr(dst_connector, "execute_query"):
            self.log("INFO", f"Executing post-copy script on destination: {post_copy_script}")
            dst_connector.execute_query(post_copy_script)

        output_vars = {}
        if watermark_col and highest_watermark is not None:
            output_vars["new_watermark"] = str(highest_watermark)

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=total_rows_read,
            rows_written=total_rows_written,
            bytes_processed=total_bytes,
            output_variables=output_vars,
            metrics={
                "duration_seconds": duration,
                "throughput_rows_sec": round(total_rows_written / max(duration, 0.001), 2)
            }
        )
