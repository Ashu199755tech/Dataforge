import time
from typing import Dict, Any, List, Optional

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.connectors.reverse_etl import ReverseETLConnector
from backend.app.core.security import decrypt_secret
from backend.app.execution.expressions import ExpressionEvaluator


class ReverseETLActivity(BaseActivity):
    """
    Enterprise Reverse ETL Activity.
    Synchronizes operational golden records from analytical warehouses (Snowflake, DuckDB,
    BigQuery, Redshift, PostgreSQL) into operational applications:
    Salesforce, HubSpot, Slack, and generic webhook endpoints.
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

        c_type = conn_config.get("connector_type") or conn_config.get("destination_type", "reverse_etl")
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

        target_object = evaluator.evaluate(dest_cfg.get("object_name") or dest_cfg.get("target_object") or config.get("target_object", "default"))
        sync_mode = config.get("sync_mode", "upsert")
        external_id_field = dest_cfg.get("external_id_field") or config.get("external_id_field")
        field_mappings = config.get("field_mappings") or dest_cfg.get("field_mappings", [])
        batch_size = int(config.get("batch_size", 50))

        # 1. Collect records from source
        records: List[Dict[str, Any]] = []
        if "records" in source_cfg or "data" in source_cfg:
            raw_records = source_cfg.get("records") or source_cfg.get("data", [])
            records = evaluator.evaluate(raw_records)
        elif source_cfg.get("connection_id") and (source_cfg.get("table_name") or source_cfg.get("query")):
            src_conn = self._resolve_connector(source_cfg)
            if source_cfg.get("query"):
                records = src_conn.execute_query(source_cfg["query"])
            else:
                stream = src_conn.read_data_stream(
                    table_name=source_cfg["table_name"],
                    filter_expr=source_cfg.get("filter_expr"),
                    batch_size=batch_size
                )
                for chunk in stream:
                    records.extend(chunk)
        elif "records" in config:
            records = evaluator.evaluate(config["records"])

        self.log("INFO", f"Loaded {len(records)} records for Reverse ETL sync to '{target_object}'.")

        # 2. Resolve destination connector
        dst_connector = self._resolve_connector(dest_cfg)

        # 3. Batch dispatch
        total_synced = 0
        total_failed = 0
        all_errors = []

        for i in range(0, max(len(records), 1), batch_size):
            chunk = records[i:i + batch_size]
            if not chunk:
                break

            if hasattr(dst_connector, "sync_batch"):
                res = dst_connector.sync_batch(
                    records=chunk,
                    object_name=target_object,
                    sync_mode=sync_mode,
                    external_id_field=external_id_field,
                    field_mappings=field_mappings
                )
            else:
                written = dst_connector.write_data_batch(
                    table_name=target_object,
                    records=chunk,
                    write_mode=sync_mode,
                    key_columns=[external_id_field] if external_id_field else None,
                    column_mappings=field_mappings
                )
                res = {"synced": written, "failed": len(chunk) - written, "errors": []}

            synced = res.get("synced", 0)
            failed = res.get("failed", 0)
            total_synced += synced
            total_failed += failed
            if res.get("errors"):
                all_errors.extend(res["errors"])

            self.log("INFO", f"Dispatched batch #{i // batch_size + 1}: {synced} synced, {failed} failed.")

        duration = round(time.time() - start_time, 2)
        status = "Succeeded" if total_failed == 0 else ("Failed" if total_synced == 0 and len(records) > 0 else "Succeeded")

        return ActivityExecutionResult(
            status=status,
            rows_read=len(records),
            rows_written=total_synced,
            duration_seconds=duration,
            error_message="; ".join(all_errors[:5]) if all_errors else None,
            output_variables={
                "records_synced": total_synced,
                "records_failed": total_failed,
                "target_object": target_object,
                "destination_type": getattr(dst_connector, "destination_type", "unknown"),
                "duration_seconds": duration
            },
            metrics={
                "records_synced": total_synced,
                "throughput_records_sec": round(total_synced / max(duration, 0.001), 2)
            }
        )
