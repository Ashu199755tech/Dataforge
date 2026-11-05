import json
from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class GetMetadataActivity(BaseActivity):
    """
    Get Metadata Activity:
    Inspects and retrieves metadata about a data source or dataset, including
    object existence, row count, column count, schema structure, and size.
    Enables downstream conditional branching and validation.
    """

    def _resolve_connector(self, connection_id: str):
        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")
        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        return get_connector(conn_record.connector_type, decrypted_config)

    def execute(self) -> ActivityExecutionResult:
        import os
        config = self.context.config
        path = config.get("path") or config.get("directory_path") or config.get("file_path")
        connection_id = config.get("connection_id")
        table_name = config.get("table_name")
        schema_name = config.get("schema_name")
        field_list = config.get("field_list", ["exists", "rowCount", "columnCount", "structure"])

        if path:
            self.log("INFO", f"Inspecting file/directory metadata for '{path}'")
            if not os.path.exists(path):
                raw_meta = {"exists": False, "rowCount": 0, "columnCount": 0, "sizeInBytes": 0, "childItems": [], "structure": []}
            elif os.path.isdir(path):
                entries = sorted(os.listdir(path))
                child_items = [{"name": e, "type": "Folder" if os.path.isdir(os.path.join(path, e)) else "File"} for e in entries]
                size_total = sum(os.path.getsize(os.path.join(path, e)) for e in entries if os.path.isfile(os.path.join(path, e)))
                raw_meta = {
                    "exists": True,
                    "rowCount": len(entries),
                    "columnCount": 0,
                    "sizeInBytes": size_total,
                    "childItems": child_items,
                    "structure": []
                }
            else:
                raw_meta = {
                    "exists": True,
                    "rowCount": 0,
                    "columnCount": 0,
                    "sizeInBytes": os.path.getsize(path),
                    "childItems": [],
                    "structure": []
                }
        else:
            if not connection_id or not table_name:
                raise ValueError("Either 'path' or both 'connection_id' and 'table_name' are required for GetMetadataActivity.")

            self.log("INFO", f"Inspecting metadata for '{table_name}' on connection '{connection_id}'")

            connector = self._resolve_connector(connection_id)
            raw_meta = connector.get_metadata(object_name=table_name, schema_name=schema_name)

        output_vars: Dict[str, Any] = {}
        # Selectively expose requested metadata fields or all by default
        output_vars["exists"] = raw_meta.get("exists", False)
        output_vars["rowCount"] = raw_meta.get("rowCount", 0)
        output_vars["columnCount"] = raw_meta.get("columnCount", 0)
        output_vars["sizeInBytes"] = raw_meta.get("sizeInBytes", 0)
        output_vars["structure"] = raw_meta.get("structure", [])
        output_vars["childItems"] = raw_meta.get("childItems", [])

        self.log(
            "INFO",
            f"Metadata discovered: exists={output_vars['exists']}, "
            f"rowCount={output_vars['rowCount']}, columnCount={output_vars['columnCount']}, "
            f"size={output_vars['sizeInBytes']} bytes"
        )

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=output_vars["rowCount"],
            output_variables=output_vars,
            metrics={
                "column_count": output_vars["columnCount"],
                "row_count": output_vars["rowCount"],
                "size_bytes": output_vars["sizeInBytes"]
            }
        )
