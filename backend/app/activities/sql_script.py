from typing import Dict, Any
import time
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class SqlScriptActivity(BaseActivity):
    """
    SQL Script Activity: Executes arbitrary SQL queries or DDL/DML commands on a designated connection.
    """

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        sql = config.get("sql")

        if not connection_id or not sql:
            raise ValueError("SQL Script activity requires 'connection_id' and 'sql'.")

        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")

        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        connector = get_connector(conn_record.connector_type, decrypted_config)

        self.log("INFO", f"Executing SQL script on connection '{conn_record.name}'")
        start = time.time()
        results = connector.execute_query(sql)
        duration = round(time.time() - start, 2)

        self.log("INFO", f"SQL execution completed in {duration}s. Returned {len(results)} rows.")

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=len(results),
            rows_written=0,
            metrics={"duration_seconds": duration, "row_count": len(results)},
            output_variables={"first_row": results[0] if results else None}
        )
