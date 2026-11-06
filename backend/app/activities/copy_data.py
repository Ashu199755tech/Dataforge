import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.models.dataset import Dataset
from backend.app.connectors.factory import get_connector
from backend.app.connectors.storage.base import BaseStorageConnector
from backend.app.transfer.engine import TransferEngine
from backend.app.core.security import decrypt_secret
from backend.app.engine.planner.planner import IntelligentExecutionPlanner
from backend.app.engine.planner.models import PlannerStrategy, ExecutionEngineType
from backend.app.engine.copy.engine import DataForgeCopyEngine


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
        source_cfg = dict(config.get("source", {}))
        dest_cfg = dict(config.get("destination", {}) or config.get("sink", {}))

        # Resolve Reusable Source Dataset if referenced
        source_dataset_id = source_cfg.get("dataset_id") or config.get("source_dataset_id")
        if source_dataset_id:
            src_ds = self.db.query(Dataset).filter(Dataset.id == source_dataset_id).first()
            if not src_ds:
                raise ValueError(f"Referenced source dataset '{source_dataset_id}' not found.")
            loc = src_ds.location_config or {}
            resolved_src = {
                "connection_id": src_ds.connection_id,
                "table_name": loc.get("table") or loc.get("table_name"),
                "schema_name": loc.get("schema") or loc.get("schema_name"),
                "query": loc.get("query"),
                "container": loc.get("container") or loc.get("bucket"),
                "bucket": loc.get("bucket") or loc.get("container"),
                "path": loc.get("path") or loc.get("file_name"),
                "file_path": loc.get("path") or loc.get("file_name"),
                "format": src_ds.format_settings.get("format") or loc.get("format")
            }
            resolved_src.update(src_ds.format_settings)
            resolved_src.update(source_cfg)
            source_cfg = resolved_src

        # Resolve Reusable Destination Dataset if referenced
        dest_dataset_id = dest_cfg.get("dataset_id") or config.get("sink_dataset_id")
        if dest_dataset_id:
            dst_ds = self.db.query(Dataset).filter(Dataset.id == dest_dataset_id).first()
            if not dst_ds:
                raise ValueError(f"Referenced destination dataset '{dest_dataset_id}' not found.")
            loc = dst_ds.location_config or {}
            resolved_dst = {
                "connection_id": dst_ds.connection_id,
                "table_name": loc.get("table") or loc.get("table_name"),
                "schema_name": loc.get("schema") or loc.get("schema_name"),
                "container": loc.get("container") or loc.get("bucket"),
                "bucket": loc.get("bucket") or loc.get("container"),
                "path": loc.get("path") or loc.get("file_name"),
                "file_path": loc.get("path") or loc.get("file_name"),
                "format": dst_ds.format_settings.get("format") or loc.get("format")
            }
            resolved_dst.update(dst_ds.format_settings)
            resolved_dst.update(dest_cfg)
            dest_cfg = resolved_dst

        src_conn_id = source_cfg.get("connection_id")
        dst_conn_id = dest_cfg.get("connection_id")

        if not src_conn_id or not dst_conn_id:
            raise ValueError("Both source.connection_id and destination.connection_id must be specified.")

        self.log("INFO", f"Initializing Copy Data: {source_cfg.get('table_name')} -> {dest_cfg.get('table_name')}")

        src_connector = self._resolve_connector(src_conn_id)
        dst_connector = self._resolve_connector(dst_conn_id)

        # Evaluate Intelligent Execution Planner
        strategy_raw = (
            config.get("execution_engine_strategy")
            or config.get("engine_strategy")
            or "AUTO"
        )
        strat_key = str(strategy_raw).upper().replace(" ", "_")
        strategy = getattr(PlannerStrategy, strat_key, PlannerStrategy.AUTO)

        plan = IntelligentExecutionPlanner.plan_copy_activity(
            activity_config=config,
            source_connector=src_connector,
            target_connector=dst_connector,
            strategy=strategy
        )
        self.log(
            "INFO",
            f"Execution Planner Decision: {plan.selected_engine.value} "
            f"(Strategy: {strategy.value}, Confidence: {plan.confidence_score}) - {plan.explanation}"
        )

        planner_metrics = {
            "execution_engine": plan.selected_engine.value,
            "planner_strategy": strategy.value,
            "planner_confidence": plan.confidence_score,
            "planner_scores": plan.scores,
            "planner_explanation": plan.explanation,
            "primary_reason": plan.primary_reason
        }

        partition_cfg = config.get("partitioning") or {}
        partition_col = partition_cfg.get("column") or config.get("partition_column")
        if partition_col:
            planner_metrics["partition_column"] = partition_col
            planner_metrics["partition_strategy"] = partition_cfg.get("strategy") or "Range"
            planner_metrics["concurrency_limit"] = int(partition_cfg.get("concurrency_limit") or config.get("concurrency_limit") or 4)

        # Multi-Cloud Storage-to-Storage Transfer
        is_src_storage = isinstance(src_connector, BaseStorageConnector)
        is_dst_storage = isinstance(dst_connector, BaseStorageConnector)

        # In-Database SQL Pushdown (Same Database instance)
        if plan.selected_engine == ExecutionEngineType.SQL_PUSHDOWN and not is_src_storage and not is_dst_storage:
            src_table = source_cfg.get("table_name")
            dst_table = dest_cfg.get("table_name")
            write_mode = dest_cfg.get("write_mode", "append")
            filter_expr = source_cfg.get("filter_expr") or source_cfg.get("filter_expression")
            column_mappings = config.get("column_mappings", [])
            pre_copy_script = dest_cfg.get("pre_copy_script")
            post_copy_script = dest_cfg.get("post_copy_script")

            if src_table and dst_table and hasattr(dst_connector, "execute_query"):
                start_p = time.time()
                self.log("INFO", f"Executing In-Database SQL Pushdown: '{src_table}' -> '{dst_table}' (0 B egress)")

                if pre_copy_script:
                    self.log("INFO", f"Executing pre-copy script: {pre_copy_script}")
                    dst_connector.execute_query(pre_copy_script)

                if write_mode == "overwrite":
                    try:
                        dst_connector.execute_query(f'DELETE FROM "{dst_table}"')
                    except Exception:
                        pass

                if column_mappings:
                    proj = ", ".join([f'"{m.get("source_column", m.get("source"))}" AS "{m.get("destination_column", m.get("destination"))}"' for m in column_mappings if not m.get("exclude")])
                    cols = ", ".join([f'"{m.get("destination_column", m.get("destination"))}"' for m in column_mappings if not m.get("exclude")])
                else:
                    proj = "*"
                    cols = ""

                where_clause = f" WHERE {filter_expr}" if filter_expr else ""
                if cols:
                    insert_sql = f'INSERT INTO "{dst_table}" ({cols}) SELECT {proj} FROM "{src_table}"{where_clause}'
                else:
                    insert_sql = f'INSERT INTO "{dst_table}" SELECT {proj} FROM "{src_table}"{where_clause}'

                self.log("INFO", f"Pushdown SQL: {insert_sql}")
                dst_connector.execute_query(insert_sql)

                if post_copy_script:
                    self.log("INFO", f"Executing post-copy script: {post_copy_script}")
                    dst_connector.execute_query(post_copy_script)

                duration_p = round(time.time() - start_p, 4)
                row_count = 0
                try:
                    cnt_res = dst_connector.execute_query(f'SELECT COUNT(*) FROM "{dst_table}"')
                    if cnt_res and len(cnt_res) > 0:
                        first_row = list(cnt_res[0].values())
                        row_count = int(first_row[0]) if first_row else 0
                except Exception:
                    row_count = 1

                self.log("INFO", f"SQL Pushdown completed in {duration_p}s. Zero network egress bytes transferred.")
                return ActivityExecutionResult(
                    status="Succeeded",
                    rows_read=row_count,
                    rows_written=row_count,
                    bytes_processed=0,
                    metrics={
                        **planner_metrics,
                        "duration_seconds": duration_p,
                        "bytes_transferred": 0,
                        "records_transferred": row_count,
                        "egress_bytes": 0
                    }
                )

        if is_src_storage and is_dst_storage:
            src_container = source_cfg.get("container") or source_cfg.get("bucket")
            src_path = source_cfg.get("path") or source_cfg.get("file_path") or source_cfg.get("object_key")
            dst_container = dest_cfg.get("container") or dest_cfg.get("bucket")
            dst_path = dest_cfg.get("path") or dest_cfg.get("file_path") or dest_cfg.get("object_key")

            if not src_container or not src_path or not dst_container or not dst_path:
                raise ValueError("Cloud storage transfers require container/bucket and path for both source and destination.")

            self.log("INFO", f"Executing Multi-Cloud Storage Transfer: {src_container}/{src_path} -> {dst_container}/{dst_path}")

            def on_progress(p):
                self.log("INFO", f"Transferred {p.bytes_written} bytes ({round(p.speed_bytes_per_sec / 1024 / 1024, 2)} MB/s)")

            res = TransferEngine.execute_storage_to_storage(
                src_connector=src_connector,
                dst_connector=dst_connector,
                src_container=src_container,
                src_path=src_path,
                dst_container=dst_container,
                dst_path=dst_path,
                config=config,
                progress_callback=on_progress
            )

            if not res.success:
                raise RuntimeError(f"Storage transfer failed: {res.error_message}")

            self.log("INFO", f"Storage transfer completed successfully: {res.bytes_transferred} bytes in {res.duration_seconds}s (checksum: {res.destination_checksum})")
            return ActivityExecutionResult(
                status="Succeeded",
                rows_read=res.records_transferred,
                rows_written=res.records_transferred,
                bytes_processed=res.bytes_transferred,
                metrics={
                    **planner_metrics,
                    "duration_seconds": res.duration_seconds,
                    "bytes_transferred": res.bytes_transferred,
                    "records_transferred": res.records_transferred,
                    "checksum": res.destination_checksum,
                    "checksum_algorithm": res.checksum_algorithm
                }
            )

        # Database-to-Cloud Ingestion
        if not is_src_storage and is_dst_storage:
            src_table = source_cfg.get("table_name")
            dst_container = dest_cfg.get("container") or dest_cfg.get("bucket")
            dst_path = dest_cfg.get("path") or dest_cfg.get("file_path") or dest_cfg.get("object_key")

            if not src_table or not dst_container or not dst_path:
                raise ValueError("Database to cloud transfer requires source.table_name and destination container + path.")

            self.log("INFO", f"Executing Database-to-Cloud Ingestion: {src_table} -> {dst_container}/{dst_path}")
            res = TransferEngine.execute_database_to_storage(
                db_connector=src_connector,
                dst_connector=dst_connector,
                src_table=src_table,
                dst_container=dst_container,
                dst_path=dst_path,
                config=config
            )
            if not res.success:
                raise RuntimeError(f"Database-to-cloud transfer failed: {res.error_message}")

            self.log("INFO", f"Database-to-cloud ingestion completed: {res.records_transferred} rows ({res.bytes_transferred} bytes)")
            return ActivityExecutionResult(
                status="Succeeded",
                rows_read=res.records_transferred,
                rows_written=res.records_transferred,
                bytes_processed=res.bytes_transferred,
                metrics={
                    **planner_metrics,
                    "duration_seconds": res.duration_seconds,
                    "bytes_transferred": res.bytes_transferred,
                    "records_transferred": res.records_transferred,
                    "checksum": res.destination_checksum
                }
            )

        # Cloud-to-Database Reverse ETL
        if is_src_storage and not is_dst_storage:
            src_container = source_cfg.get("container") or source_cfg.get("bucket")
            src_path = source_cfg.get("path") or source_cfg.get("file_path") or source_cfg.get("object_key")
            dst_table = dest_cfg.get("table_name")

            if not src_container or not src_path or not dst_table:
                raise ValueError("Cloud to database transfer requires source container + path and destination table_name.")

            self.log("INFO", f"Executing Cloud-to-Database Reverse ETL: {src_container}/{src_path} -> {dst_table}")
            res = TransferEngine.execute_storage_to_database(
                src_connector=src_connector,
                db_connector=dst_connector,
                src_container=src_container,
                src_path=src_path,
                dst_table=dst_table,
                config=config
            )
            if not res.success:
                raise RuntimeError(f"Cloud-to-database transfer failed: {res.error_message}")

            self.log("INFO", f"Cloud-to-database reverse ETL completed: {res.records_transferred} rows ({res.bytes_transferred} bytes)")
            return ActivityExecutionResult(
                status="Succeeded",
                rows_read=res.records_transferred,
                rows_written=res.records_transferred,
                bytes_processed=res.bytes_transferred,
                metrics={
                    **planner_metrics,
                    "duration_seconds": res.duration_seconds,
                    "bytes_transferred": res.bytes_transferred,
                    "records_transferred": res.records_transferred
                }
            )

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
            filter_expr=source_cfg.get("filter_expr") or source_cfg.get("filter_expression"),
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
                **planner_metrics,
                "duration_seconds": duration,
                "throughput_rows_sec": round(total_rows_written / max(duration, 0.001), 2)
            }
        )
