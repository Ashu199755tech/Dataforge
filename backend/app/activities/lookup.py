import time
from typing import Dict, Any, List
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class LookupActivity(BaseActivity):
    """
    Lookup Activity: Fetches a dataset or single record from a connection
    and exposes the results to downstream activities via pipeline variables.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        table_name = config.get("table_name")
        query = config.get("query")
        first_row_only = config.get("first_row_only", True)

        if not connection_id:
            raise ValueError("Lookup activity requires 'connection_id'.")

        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")

        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        connector = get_connector(conn_record.connector_type, decrypted_config)

        self.log("INFO", f"Executing Lookup on connection '{conn_record.name}'")
        start = time.time()

        if query:
            rows = connector.execute_query(query)
        elif table_name:
            stream = connector.read_data_stream(table_name=table_name, batch_size=100)
            rows = []
            for chunk in stream:
                rows.extend(chunk)
                if first_row_only and len(rows) > 0:
                    break
        else:
            raise ValueError("Lookup requires either 'query' or 'table_name'.")

        duration = round(time.time() - start, 2)
        self.log("INFO", f"Lookup returned {len(rows)} rows in {duration}s")

        output_vars: Dict[str, Any] = {
            "count": len(rows),
            "rows": rows[:50]  # Cap to prevent excessive memory
        }

        if rows:
            output_vars["first_row"] = rows[0]
        else:
            output_vars["first_row"] = {}

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=len(rows),
            output_variables=output_vars,
            metrics={"duration_seconds": duration, "count": len(rows)}
        )
