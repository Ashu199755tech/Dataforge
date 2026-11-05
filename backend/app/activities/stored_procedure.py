from typing import Dict, Any, List, Optional
from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret
from backend.app.execution.expressions import ExpressionEvaluator


class StoredProcedureActivity(BaseActivity):
    """
    Stored Procedure Activity:
    Invokes stored procedures or database functions against configured
    relational connections (PostgreSQL, MySQL, SQL Server) with IN/OUT parameter mapping.
    """

    def _resolve_connector(self, connection_id: str):
        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")
        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        return get_connector(conn_record.connector_type, decrypted_config), conn_record.connector_type

    def execute(self) -> ActivityExecutionResult:
        config = self.context.config
        connection_id = config.get("connection_id")
        proc_name = config.get("stored_procedure_name") or config.get("procedure_name")
        schema_name = config.get("schema_name")
        raw_parameters = config.get("parameters", {})

        if not connection_id or not proc_name:
            raise ValueError("Both 'connection_id' and 'stored_procedure_name' are required for StoredProcedureActivity.")

        connector, conn_type = self._resolve_connector(connection_id)

        # Evaluate parameter expressions
        evaluator = ExpressionEvaluator(
            parameters=self.context.pipeline_parameters,
            variables=self.context.pipeline_variables
        )
        resolved_params = evaluator.evaluate(raw_parameters)

        self.log("INFO", f"Invoking stored procedure '{proc_name}' on {conn_type} connection '{connection_id}'")

        # Format procedure call SQL based on database type and parameter format
        param_values = []
        if isinstance(resolved_params, dict):
            param_values = list(resolved_params.values())
        elif isinstance(resolved_params, list):
            param_values = resolved_params

        # Build placeholders
        placeholders = []
        sql_params = {}
        for idx, val in enumerate(param_values):
            if val is None:
                placeholders.append("NULL")
            elif isinstance(val, (int, float)):
                placeholders.append(str(val))
            else:
                # String escaping
                escaped = str(val).replace("'", "''")
                placeholders.append(f"'{escaped}'")

        param_str = ", ".join(placeholders)

        # Qualify with schema if provided
        full_proc = f'"{schema_name}"."{proc_name}"' if (schema_name and conn_type.lower() == "postgresql") else (
            f"`{schema_name}`.`{proc_name}`" if (schema_name and conn_type.lower() == "mysql") else proc_name
        )

        # Use CALL for procedures or SELECT for functions if specified
        is_function = bool(config.get("is_function", False))
        table_function = bool(config.get("table_function", False))
        if is_function:
            if table_function:
                call_sql = f"SELECT * FROM {full_proc}({param_str});"
            else:
                call_sql = f"SELECT {full_proc}({param_str}) AS result;"
        else:
            call_sql = f"CALL {full_proc}({param_str});"

        self.log("INFO", f"Executing SQL: {call_sql}")
        rows = connector.execute_query(call_sql)
        row_count = len(rows) if rows else 0

        self.log("INFO", f"Stored procedure '{proc_name}' executed successfully ({row_count} rows returned)")

        output_vars = {
            "procedure_name": proc_name,
            "row_count": row_count,
            "first_row": rows[0] if rows else {},
            "rows": rows[:100]  # Cap in output variables for memory safety
        }

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=row_count,
            output_variables=output_vars,
            metrics={"row_count": row_count}
        )
