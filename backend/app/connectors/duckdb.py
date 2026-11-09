import os
import time
from typing import List, Dict, Any, Iterator, Optional

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

from backend.app.connectors.base import (
    BaseConnector,
    ColumnMetadata,
    TableMetadata,
    ConnectionTestResult
)


class DuckDBConnector(BaseConnector):
    """
    Enterprise DuckDB Connector for fast in-process analytical execution.
    Supports in-memory analytics, direct Parquet/CSV file querying with zero-copy,
    table auto-discovery, streaming chunked reads, and upsert/merge batch writes.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.database_path = config.get("database_path") or config.get("database") or ":memory:"
        self.read_only = bool(config.get("read_only", False))
        self.schema = config.get("schema", "main").strip()
        self.mock_mode = config.get("mock_mode", False)
        self._mock_tables: Dict[str, List[Dict[str, Any]]] = config.get("_mock_tables", {})
        self._conn: Optional[Any] = None

    def _get_connection(self):
        if not HAS_DUCKDB:
            raise RuntimeError("DuckDB package is not installed. Run 'pip install duckdb'.")
        if self._conn is None:
            if self.database_path == ":memory:":
                # Persistent in-memory instance for this connector session
                self._conn = duckdb.connect(database=":memory:", read_only=False)
            else:
                norm_path = os.path.abspath(self.database_path)
                if not self.read_only:
                    os.makedirs(os.path.dirname(norm_path), exist_ok=True)
                self._conn = duckdb.connect(database=norm_path, read_only=self.read_only)
        return self._conn

    def test_connection(self) -> ConnectionTestResult:
        start_time = time.time()
        if self.mock_mode:
            return ConnectionTestResult(
                success=True,
                message=f"Connected to DuckDB (Mock Database: '{self.database_path}')",
                latency_ms=1.5,
                server_version="DuckDB 2.0.0"
            )

        if not HAS_DUCKDB:
            return ConnectionTestResult(
                success=False,
                message="DuckDB library is not installed."
            )

        try:
            conn = self._get_connection()
            ver = conn.execute("SELECT version();").fetchone()[0]
            latency = (time.time() - start_time) * 1000.0
            return ConnectionTestResult(
                success=True,
                message=f"Connected successfully to DuckDB '{self.database_path}'.",
                latency_ms=round(latency, 2),
                server_version=f"DuckDB {ver}"
            )
        except Exception as ex:
            return ConnectionTestResult(
                success=False,
                message=f"DuckDB connection failed: {str(ex)}"
            )

    def discover_schemas(self) -> List[str]:
        if self.mock_mode:
            return ["main", "information_schema"]

        rows = self.execute_query("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name;")
        schemas = [r.get("schema_name") for r in rows if r.get("schema_name")]
        return schemas if schemas else ["main"]

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        target_schema = schema_name or self.schema or "main"
        if self.mock_mode:
            return [
                TableMetadata(
                    name=t_name,
                    schema_name=target_schema,
                    table_type="TABLE",
                    approx_row_count=len(rows),
                    columns=self.discover_columns(t_name, target_schema)
                )
                for t_name, rows in self._mock_tables.items()
            ]

        query = f"""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = '{target_schema}' 
            AND table_name NOT LIKE 'duckdb_%'
            ORDER BY table_name;
        """
        rows = self.execute_query(query)
        tables = []
        for r in rows:
            t_name = r.get("table_name")
            if t_name:
                t_type = "VIEW" if "VIEW" in (r.get("table_type") or "").upper() else "TABLE"
                cnt_row = self.execute_query(f'SELECT COUNT(*) as cnt FROM "{target_schema}"."{t_name}";')
                row_cnt = int(cnt_row[0].get("cnt", 0)) if cnt_row else 0
                tables.append(TableMetadata(
                    name=t_name,
                    schema_name=target_schema,
                    table_type=t_type,
                    approx_row_count=row_cnt,
                    columns=self.discover_columns(t_name, target_schema)
                ))
        return tables

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        target_schema = schema_name or self.schema or "main"
        if self.mock_mode:
            sample_rows = self._mock_tables.get(table_name, [])
            if sample_rows:
                first_row = sample_rows[0]
                return [
                    ColumnMetadata(
                        name=col,
                        data_type="BIGINT" if isinstance(val, int) else ("DOUBLE" if isinstance(val, float) else "VARCHAR"),
                        is_nullable=True,
                        is_primary_key=(col.lower() in ("id", f"{table_name.lower()}_id", "item_id"))
                    )
                    for col, val in first_row.items()
                ]
            return [
                ColumnMetadata(name="id", data_type="BIGINT", is_nullable=False, is_primary_key=True),
                ColumnMetadata(name="name", data_type="VARCHAR", is_nullable=True)
            ]

        query = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            AND table_schema = '{target_schema}'
            ORDER BY ordinal_position;
        """
        rows = self.execute_query(query)
        cols = []
        for r in rows:
            c_name = r.get("column_name")
            dtype = r.get("data_type") or "VARCHAR"
            nullable = (r.get("is_nullable") or "YES").upper() == "YES"
            if c_name:
                cols.append(ColumnMetadata(
                    name=c_name,
                    data_type=dtype,
                    is_nullable=nullable,
                    is_primary_key=(c_name.lower() in ("id", f"{table_name.lower()}_id"))
                ))
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
        if self.mock_mode:
            all_records = list(self._mock_tables.get(table_name, []))
            if watermark_column and watermark_value is not None:
                all_records = [r for r in all_records if str(r.get(watermark_column, "")) > str(watermark_value)]
            for i in range(0, max(len(all_records), 1), batch_size):
                chunk = all_records[i:i + batch_size]
                if chunk:
                    yield chunk
            return

        target_schema = schema_name or self.schema or "main"
        col_clause = ", ".join([f'"{c}"' for c in columns]) if columns else "*"
        where_clauses = []
        if filter_expr:
            where_clauses.append(f"({filter_expr})")
        if watermark_column and watermark_value is not None:
            where_clauses.append(f'"{watermark_column}" > \'{watermark_value}\'')

        where_stmt = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f'SELECT {col_clause} FROM "{target_schema}"."{table_name}" {where_stmt}'

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        col_names = [desc[0] for desc in cursor.description] if cursor.description else []

        while True:
            chunk = cursor.fetchmany(batch_size)
            if not chunk:
                break
            rows = [{col_names[i]: r[i] for i in range(len(col_names))} for r in chunk]
            yield rows

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

        # Apply column mappings if provided
        transformed_records = []
        if column_mappings:
            for r in records:
                new_row = {}
                for m in column_mappings:
                    src = m.get("source")
                    dst = m.get("destination") or src
                    if src in r:
                        new_row[dst] = r[src]
                transformed_records.append(new_row)
        else:
            transformed_records = records

        if self.mock_mode:
            clean_mode = write_mode.lower()
            if table_name not in self._mock_tables or clean_mode in ("overwrite", "truncate"):
                self._mock_tables[table_name] = []

            keys = key_columns or (self.config.get("primary_keys") if isinstance(self.config.get("primary_keys"), list) else None)
            if clean_mode == "upsert" and keys:
                existing = self._mock_tables[table_name]
                for rec in transformed_records:
                    match_idx = None
                    for idx, ex in enumerate(existing):
                        if all(ex.get(k) == rec.get(k) for k in keys):
                            match_idx = idx
                            break
                    if match_idx is not None:
                        existing[match_idx].update(rec)
                    else:
                        existing.append(rec)
            else:
                self._mock_tables[table_name].extend(transformed_records)
            return len(transformed_records)

        target_schema = schema_name or self.schema or "main"
        first_row = transformed_records[0]
        cols = list(first_row.keys())
        conn = self._get_connection()

        # Auto-create table if needed
        if auto_create_table:
            type_defs = []
            for c in cols:
                sample_val = first_row.get(c)
                if isinstance(sample_val, bool):
                    t = "BOOLEAN"
                elif isinstance(sample_val, int):
                    t = "BIGINT"
                elif isinstance(sample_val, float):
                    t = "DOUBLE"
                else:
                    t = "VARCHAR"
                type_defs.append(f'"{c}" {t}')
            conn.execute(f'CREATE TABLE IF NOT EXISTS "{target_schema}"."{table_name}" ({", ".join(type_defs)});')

        clean_mode = write_mode.lower()
        if clean_mode in ("overwrite", "truncate"):
            conn.execute(f'DELETE FROM "{target_schema}"."{table_name}";')

        keys = key_columns or (self.config.get("primary_keys") if isinstance(self.config.get("primary_keys"), list) else None)

        if clean_mode == "upsert" and keys:
            # Upsert using temporary staging table + DELETE/INSERT merge
            stage_table = f"_df_duck_stage_{int(time.time() * 1000)}"
            try:
                conn.execute(f'CREATE TEMP TABLE "{stage_table}" AS SELECT * FROM "{target_schema}"."{table_name}" WHERE 1=0;')
                placeholders = ", ".join(["?"] * len(cols))
                insert_stage = f'INSERT INTO "{stage_table}" ({", ".join([f"{c}" for c in cols])}) VALUES ({placeholders});'
                conn.executemany(insert_stage, [[r.get(c) for c in cols] for r in transformed_records])

                # Delete matching keys from target table
                join_cond = " AND ".join([f't."{k}" = s."{k}"' for k in keys])
                conn.execute(f'DELETE FROM "{target_schema}"."{table_name}" t USING "{stage_table}" s WHERE {join_cond};')

                # Insert all from staging table
                conn.execute(f'INSERT INTO "{target_schema}"."{table_name}" SELECT * FROM "{stage_table}";')
            finally:
                conn.execute(f'DROP TABLE IF EXISTS "{stage_table}";')
        else:
            # Standard batch append
            placeholders = ", ".join(["?"] * len(cols))
            cols_clause = ", ".join([f'"{c}"' for c in cols])
            insert_sql = f'INSERT INTO "{target_schema}"."{table_name}" ({cols_clause}) VALUES ({placeholders});'
            conn.executemany(insert_sql, [[r.get(c) for c in cols] for r in transformed_records])

        return len(transformed_records)

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self.mock_mode:
            q_upper = query.upper()
            if "SELECT SCHEMA_NAME" in q_upper or "SHOW SCHEMAS" in q_upper:
                return [{"schema_name": "main"}, {"schema_name": "information_schema"}]
            elif "SELECT TABLE_NAME" in q_upper or "SHOW TABLES" in q_upper:
                return [{"table_name": t, "table_type": "TABLE"} for t in self._mock_tables]
            elif "SELECT VERSION" in q_upper:
                return [{"ver": "DuckDB 2.0.0"}]
            elif "SELECT COUNT" in q_upper:
                for t in self._mock_tables:
                    if t.upper() in q_upper:
                        return [{"cnt": len(self._mock_tables[t])}]
                return [{"cnt": 0}]
            elif "SELECT" in q_upper and "FROM" in q_upper:
                for t, rows in self._mock_tables.items():
                    if t.upper() in q_upper:
                        return list(rows)
            return []

        conn = self._get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        if not cursor.description:
            return []

        col_names = [desc[0] for desc in cursor.description]
        fetched = cursor.fetchall()
        return [{col_names[i]: row[i] for i in range(len(col_names))} for row in fetched]

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
