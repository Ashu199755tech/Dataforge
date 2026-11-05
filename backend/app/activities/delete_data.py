from typing import Dict, Any, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class DeleteDataActivity(BaseActivity):
    """
    Delete Data Activity:
    Performs targeted cleanup, conditional deletion, or table truncation on
    relational tables or file storage to support pre-copy staging and idempotent pipelines.
    """

    def _resolve_connector(self, connection_id: str):
        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")
        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        return get_connector(conn_record.connector_type, decrypted_config)

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        table_name = config.get("table_name")
        schema_name = config.get("schema_name")
        delete_mode = config.get("delete_mode", "conditional")  # "conditional" or "truncate"
        filter_expr = config.get("filter_expr")
        truncate = (delete_mode == "truncate") or bool(config.get("truncate", False))

        if not connection_id or not table_name:
            raise ValueError("Both 'connection_id' and 'table_name' are required for DeleteDataActivity.")

        connector = self._resolve_connector(connection_id)

        if truncate:
            self.log("INFO", f"Truncating table '{table_name}' on connection '{connection_id}'")
            deleted_count = connector.delete_data(object_name=table_name, truncate=True, schema_name=schema_name)
            self.log("INFO", f"Successfully truncated '{table_name}'")
        else:
            self.log("INFO", f"Deleting records from '{table_name}' with filter: '{filter_expr or 'ALL'}'")
            deleted_count = connector.delete_data(
                object_name=table_name,
                filter_expr=filter_expr,
                truncate=False,
                schema_name=schema_name
            )
            self.log("INFO", f"Successfully deleted {deleted_count} record(s) from '{table_name}'")

        return ActivityExecutionResult(
            status="Succeeded",
            rows_written=0,
            output_variables={"rows_deleted": deleted_count},
            metrics={"rows_deleted": deleted_count}
        )
