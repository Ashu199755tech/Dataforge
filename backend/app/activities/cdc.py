import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.connectors.cdc import DebeziumCDCConnector
from backend.app.core.security import decrypt_secret
from backend.app.execution.expressions import ExpressionEvaluator


class CDCReplicationActivity(BaseActivity):
    """
    Enterprise Incremental CDC (Change Data Capture) Stream Engine Activity.
    Replicates continuous or micro-batched transaction log streams (Debezium/WAL)
    into target analytical data warehouses (Snowflake, DuckDB, BigQuery, Redshift, PostgreSQL).
    Idempotently handles inserts, updates, deletes, audit logging, and LSN watermark tracking.
    """

    def _resolve_connector(self, conn_config: Dict[str, Any]):
        conn_id = conn_config.get("connection_id")
        if conn_id:
            conn_record = self.db.query(Connection).filter(Connection.id == conn_id).first()
            if not conn_record:
                raise ValueError(f"Connection ID '{conn_id}' not found.")
            decrypted = decrypt_secret(conn_record.config_encrypted)
            merged = {**decrypted, **conn_config}
            return get_connector(conn_record.connector_type, merged)
        
        c_type = conn_config.get("connector_type") or conn_config.get("type", "cdc")
        return get_connector(c_type, conn_config)

    def execute(self) -> ActivityExecutionResult:
        start_time = time.time()
        config = self.context.config

        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables,
            activity_outputs=self.context.activity_outputs
        )

        source_cfg = config.get("source", {})
        dest_cfg = config.get("destination", {})

        # Resolve connectors
        src_connector = self._resolve_connector(source_cfg)
        dst_connector = self._resolve_connector(dest_cfg)

        target_table = evaluator.evaluate(dest_cfg.get("table_name") or source_cfg.get("table_name", "target_table"))
        key_columns = dest_cfg.get("key_columns") or config.get("key_columns", ["id"])
        soft_delete = bool(config.get("soft_delete", False))
        audit_mode = bool(config.get("audit_mode", False) or config.get("enable_cdc_log", False))
        batch_size = int(config.get("batch_size", 1000))

        # Resolve starting checkpoint LSN/offset
        start_lsn_raw = config.get("checkpoint_lsn") or config.get("from_lsn", 0)
        start_lsn = evaluator.evaluate(start_lsn_raw)

        self.log("INFO", f"Starting CDC Replication to '{target_table}' from checkpoint LSN: {start_lsn}")

        # Stream change events from CDC source
        stream = getattr(src_connector, "read_cdc_stream", None)
        if callable(stream):
            cdc_batches = stream(from_lsn=start_lsn, batch_size=batch_size)
        else:
            # Fallback for standard connectors providing row streams
            row_stream = src_connector.read_data_stream(
                table_name=source_cfg.get("table_name", "cdc"),
                watermark_value=start_lsn,
                batch_size=batch_size
            )
            # Wrap as pseudo-CDC change records
            cdc_batches = (
                [{"op": "c", "data": r, "table": target_table, "lsn": int(time.time() * 1000)} for r in chunk]
                for chunk in row_stream
            )

        total_events = 0
        total_inserts = 0
        total_updates = 0
        total_deletes = 0
        highest_lsn = start_lsn

        for batch_idx, batch in enumerate(cdc_batches):
            if not batch:
                continue

            upsert_records: List[Dict[str, Any]] = []
            delete_keys: List[Dict[str, Any]] = []
            audit_records: List[Dict[str, Any]] = []

            for evt in batch:
                total_events += 1
                op = evt.get("op", "c").lower()
                data = dict(evt.get("data") or {})
                evt_lsn = evt.get("lsn", highest_lsn)

                if str(evt_lsn) > str(highest_lsn):
                    highest_lsn = evt_lsn

                # Audit record entry if requested
                if audit_mode:
                    audit_entry = {
                        **data,
                        "_cdc_op": op,
                        "_cdc_lsn": evt_lsn,
                        "_cdc_timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    audit_records.append(audit_entry)

                if op in ("c", "r"):  # Insert or Snapshot read
                    total_inserts += 1
                    upsert_records.append(data)
                elif op == "u":       # Update
                    total_updates += 1
                    upsert_records.append(data)
                elif op == "d":       # Delete
                    total_deletes += 1
                    if soft_delete:
                        data["_df_is_deleted"] = True
                        upsert_records.append(data)
                    else:
                        # Extract key columns for hard delete
                        key_val = {k: data.get(k) or evt.get("before", {}).get(k) for k in key_columns}
                        delete_keys.append(key_val)

            # 1. Apply upserts/merges to target warehouse
            if upsert_records:
                dst_connector.write_data_batch(
                    table_name=target_table,
                    records=upsert_records,
                    write_mode="upsert",
                    key_columns=key_columns,
                    schema_name=dest_cfg.get("schema_name"),
                    auto_create_table=True
                )

            # 2. Apply hard deletes if any and not soft_delete
            if delete_keys and hasattr(dst_connector, "execute_query"):
                for k_dict in delete_keys:
                    where_conds = []
                    for k, v in k_dict.items():
                        if v is not None:
                            val_str = f"'{v}'" if isinstance(v, str) else str(v)
                            where_conds.append(f'"{k}" = {val_str}')
                    if where_conds:
                        del_sql = f'DELETE FROM "{target_table}" WHERE {" AND ".join(where_conds)};'
                        try:
                            dst_connector.execute_query(del_sql)
                        except Exception as dex:
                            self.log("WARN", f"Failed to execute CDC hard delete: {str(dex)}")

            # 3. Write historical audit changelog if requested
            if audit_records:
                history_table = f"{target_table}_cdc_history"
                dst_connector.write_data_batch(
                    table_name=history_table,
                    records=audit_records,
                    write_mode="append",
                    schema_name=dest_cfg.get("schema_name"),
                    auto_create_table=True
                )

            self.log("INFO", f"CDC Batch #{batch_idx + 1}: Processed {len(batch)} changes (Inserts: {len(upsert_records)}, Deletes: {len(delete_keys)})")

        # Commit offset on source connector if supported
        if hasattr(src_connector, "commit_offset") and highest_lsn is not None:
            src_connector.commit_offset(highest_lsn)

        duration = round(time.time() - start_time, 2)
        self.log("INFO", f"CDC Replication finished in {duration}s: {total_events} events (Inserts: {total_inserts}, Updates: {total_updates}, Deletes: {total_deletes}), Highest LSN: {highest_lsn}")

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=total_events,
            rows_written=total_inserts + total_updates,
            duration_seconds=duration,
            output_variables={
                "events_processed": total_events,
                "inserts": total_inserts,
                "updates": total_updates,
                "deletes": total_deletes,
                "highest_lsn": highest_lsn,
                "duration_seconds": duration,
                "target_table": target_table
            },
            metrics={
                "events_processed": total_events,
                "throughput_events_sec": round(total_events / max(duration, 0.001), 2)
            }
        )
