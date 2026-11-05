import sqlite3
import time
from typing import List, Dict, Any, Iterator, Optional
from backend.app.connectors.base import BaseConnector, ConnectionTestResult, TableMetadata, ColumnMetadata


class SQLiteConnector(BaseConnector):
    """
    Local SQLite Connector for portable execution, testing, and file-based pipelines.
    """

    def _get_connection(self):
        database_path = self.config.get("database_path") or self.config.get("database") or ":memory:"
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            cur.execute("SELECT sqlite_version();")
            ver = cur.fetchone()[0]
            conn.close()
            latency = (time.time() - start) * 1000
            return ConnectionTestResult(
                success=True,
                message="Successfully opened SQLite database",
                latency_ms=round(latency, 2),
                server_version=ver
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"SQLite connection failed: {str(e)}"
            )

    def discover_schemas(self) -> List[str]:
        return ["main"]

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        query = "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        tables = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query)
            for row in cur.fetchall():
                tbl_name = row["name"]
                tbl_type = row["type"].upper()
                cols = self.discover_columns(tbl_name)
                tables.append(TableMetadata(
                    name=tbl_name,
                    schema_name="main",
                    table_type=tbl_type,
                    columns=cols
                ))
        finally:
            conn.close()
        return tables

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        query = f"PRAGMA table_info('{table_name}');"
        cols = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query)
            for row in cur.fetchall():
                cols.append(ColumnMetadata(
                    name=row["name"],
                    data_type=row["type"] or "TEXT",
                    is_nullable=(row["notnull"] == 0),
                    is_primary_key=(row["pk"] > 0),
                    default_value=row["dflt_value"]
                ))
        finally:
            conn.close()
        return cols

    def read_data_stream(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        watermark_column: Optional[str] = None,
        watermark_value: Optional[Any] = None,
        batch_size: int = 5000,
        schema_name: Optional[str] = None
    ) -> Iterator[List[Dict[str, Any]]]:
        col_clause = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        where_clauses = []
        params = []
        if filter_expr:
            where_clauses.append(f"({filter_expr})")
        if watermark_column and watermark_value is not None:
            where_clauses.append(f'"{watermark_column}" > ?')
            params.append(watermark_value)

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f'SELECT {col_clause} FROM "{table_name}"{where_sql}'

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                yield [dict(r) for r in rows]
        finally:
            conn.close()

    def _auto_create_table_if_needed(self, conn, table_name: str, sample_record: Dict[str, Any], key_columns: Optional[List[str]]):
        col_defs = []
        for k, v in sample_record.items():
            if isinstance(v, int):
                col_type = "INTEGER"
            elif isinstance(v, float):
                col_type = "REAL"
            else:
                col_type = "TEXT"
            col_defs.append(f'"{k}" {col_type}')

        if key_columns:
            pk_cols = ", ".join(f'"{c}"' for c in key_columns)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")

        create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)});'
        conn.execute(create_sql)
        conn.commit()

    def write_data_batch(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        write_mode: str = "append",
        key_columns: Optional[List[str]] = None,
        column_mappings: Optional[List[Dict[str, str]]] = None,
        schema_name: Optional[str] = None,
        auto_create_table: bool = True
    ) -> int:
        if not records:
            return 0

        mapped_records = []
        if column_mappings:
            mapping_dict = {
                m["source_column"]: (m.get("target_column") or m.get("destination_column") or m["source_column"])
                for m in column_mappings
                if not m.get("exclude")
            }
            for r in records:
                mapped_records.append({mapping_dict.get(k, k): v for k, v in r.items() if k in mapping_dict})
        else:
            mapped_records = records

        cols = list(mapped_records[0].keys())

        conn = self._get_connection()
        try:
            if auto_create_table:
                self._auto_create_table_if_needed(conn, table_name, mapped_records[0], key_columns)

            if write_mode == "overwrite":
                conn.execute(f'DELETE FROM "{table_name}";')

            col_names = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join(["?"] * len(cols))

            if write_mode == "upsert" and key_columns:
                pk_clause = ", ".join(f'"{c}"' for c in key_columns)
                update_clause = ", ".join([f'"{c}" = excluded."{c}"' for c in cols if c not in key_columns])
                if update_clause:
                    sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders}) ON CONFLICT({pk_clause}) DO UPDATE SET {update_clause};'
                else:
                    sql = f'INSERT OR IGNORE INTO "{table_name}" ({col_names}) VALUES ({placeholders});'
            else:
                sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders});'

            data_tuples = [tuple(r.get(c) for c in cols) for r in mapped_records]
            conn.executemany(sql, data_tuples)
            conn.commit()
        finally:
            conn.close()

        return len(mapped_records)

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params or ())
            if cur.description:
                return [dict(r) for r in cur.fetchall()]
            conn.commit()
            return []
        finally:
            conn.close()
