import time
from typing import List, Dict, Any, Iterator, Optional
import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from backend.app.connectors.base import BaseConnector, ConnectionTestResult, TableMetadata, ColumnMetadata


class PostgresConnector(BaseConnector):
    """
    Enterprise PostgreSQL Connector.
    Supports secure SSL connection, metadata discovery, streaming cursors, and bulk upsert.
    """

    def _get_connection(self):
        return psycopg2.connect(
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 5432)),
            user=self.config.get("user", "postgres"),
            password=self.config.get("password", ""),
            dbname=self.config.get("database", "postgres"),
            connect_timeout=10
        )

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    ver = cur.fetchone()[0]
            latency = (time.time() - start) * 1000
            return ConnectionTestResult(
                success=True,
                message="Successfully connected to PostgreSQL",
                latency_ms=round(latency, 2),
                server_version=ver
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"PostgreSQL connection failed: {str(e)}"
            )

    def discover_schemas(self) -> List[str]:
        query = """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog') 
            ORDER BY schema_name;
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                return [row[0] for row in cur.fetchall()]

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        schema = schema_name or "public"
        query = """
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = %s
            ORDER BY table_name;
        """
        tables = []
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (schema,))
                for table_name, table_type in cur.fetchall():
                    cols = self.discover_columns(table_name, schema)
                    tables.append(TableMetadata(
                        name=table_name,
                        schema_name=schema,
                        table_type="VIEW" if "VIEW" in table_type else "TABLE",
                        columns=cols
                    ))
        return tables

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        schema = schema_name or "public"
        query = """
            SELECT 
                c.column_name, 
                c.data_type, 
                c.is_nullable, 
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN TRUE ELSE FALSE END as is_pk
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.table_schema = ku.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position;
        """
        cols = []
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (schema, table_name, schema, table_name))
                for col_name, data_type, is_null, default_val, is_pk in cur.fetchall():
                    cols.append(ColumnMetadata(
                        name=col_name,
                        data_type=data_type,
                        is_nullable=(is_null == "YES"),
                        is_primary_key=bool(is_pk),
                        default_value=str(default_val) if default_val is not None else None
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
        schema = schema_name or "public"
        col_clause = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        full_table = f'"{schema}"."{table_name}"'

        where_clauses = []
        params = []
        if filter_expr:
            where_clauses.append(f"({filter_expr})")
        if watermark_column and watermark_value is not None:
            where_clauses.append(f'"{watermark_column}" > %s')
            params.append(watermark_value)

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT {col_clause} FROM {full_table}{where_sql}"

        conn = self._get_connection()
        try:
            # Server-side cursor for low-memory streaming
            cursor_name = f"cur_{int(time.time() * 1000)}"
            cur = conn.cursor(name=cursor_name, cursor_factory=RealDictCursor)
            cur.execute(query, tuple(params))
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                yield [dict(r) for r in rows]
            cur.close()
        finally:
            conn.close()

    def _auto_create_table_if_needed(self, conn, table_name: str, sample_record: Dict[str, Any], key_columns: Optional[List[str]], schema: str):
        col_defs = []
        for k, v in sample_record.items():
            if isinstance(v, int):
                col_type = "BIGINT"
            elif isinstance(v, float):
                col_type = "NUMERIC(18, 4)"
            elif isinstance(v, bool):
                col_type = "BOOLEAN"
            elif isinstance(v, (dict, list)):
                col_type = "JSONB"
            else:
                col_type = "TEXT"
            col_defs.append(f'"{k}" {col_type}')

        if key_columns:
            pk_cols = ", ".join(f'"{c}"' for c in key_columns)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")

        create_sql = f'CREATE TABLE IF NOT EXISTS "{schema}"."{table_name}" ({", ".join(col_defs)});'
        with conn.cursor() as cur:
            cur.execute(create_sql)
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

        schema = schema_name or "public"
        full_table = f'"{schema}"."{table_name}"'

        # Apply column mapping if provided
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

        with self._get_connection() as conn:
            if auto_create_table:
                self._auto_create_table_if_needed(conn, table_name, mapped_records[0], key_columns, schema)

            with conn.cursor() as cur:
                if write_mode == "overwrite":
                    cur.execute(f"TRUNCATE TABLE {full_table};")

                col_names = ", ".join(f'"{c}"' for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))

                if write_mode == "upsert" and key_columns:
                    conflict_targets = ", ".join(f'"{k}"' for k in key_columns)
                    update_clauses = [f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in key_columns]
                    if update_clauses:
                        sql = f"""
                            INSERT INTO {full_table} ({col_names})
                            VALUES ({placeholders})
                            ON CONFLICT ({conflict_targets})
                            DO UPDATE SET {', '.join(update_clauses)};
                        """
                    else:
                        sql = f"""
                            INSERT INTO {full_table} ({col_names})
                            VALUES ({placeholders})
                            ON CONFLICT ({conflict_targets}) DO NOTHING;
                        """
                else:
                    sql = f"INSERT INTO {full_table} ({col_names}) VALUES ({placeholders});"

                data_tuples = [tuple(r.get(c) for c in cols) for r in mapped_records]
                execute_batch(cur, sql, data_tuples, page_size=1000)
            conn.commit()

        return len(mapped_records)

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or {})
                if cur.description:
                    return [dict(r) for r in cur.fetchall()]
                conn.commit()
                return []

    def get_metadata(
        self,
        object_name: str,
        schema_name: Optional[str] = None
    ) -> Dict[str, Any]:
        schema = schema_name or "public"
        cols = self.discover_columns(object_name, schema)
        if not cols:
            return {
                "exists": False,
                "rowCount": 0,
                "columnCount": 0,
                "structure": [],
                "sizeInBytes": 0,
                "childItems": []
            }

        full_table = f'"{schema}"."{object_name}"'
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SELECT COUNT(*) as cnt FROM {full_table};")
                row_cnt = int(cur.fetchone()["cnt"])

                try:
                    cur.execute(f"SELECT pg_total_relation_size('{full_table}') as sz;")
                    size_bytes = int(cur.fetchone()["sz"])
                except Exception:
                    size_bytes = 0

        structure = [{"name": c.name, "type": c.data_type, "nullable": c.is_nullable} for c in cols]
        return {
            "exists": True,
            "rowCount": row_cnt,
            "columnCount": len(cols),
            "structure": structure,
            "sizeInBytes": size_bytes,
            "childItems": [c.name for c in cols]
        }

    def delete_data(
        self,
        object_name: str,
        filter_expr: Optional[str] = None,
        truncate: bool = False,
        schema_name: Optional[str] = None
    ) -> int:
        schema = schema_name or "public"
        full_table = f'"{schema}"."{object_name}"'

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if truncate:
                    cur.execute(f"TRUNCATE TABLE {full_table} CASCADE;")
                    conn.commit()
                    return 0

                where_clause = f" WHERE {filter_expr}" if filter_expr and filter_expr.strip() else ""
                cur.execute(f"DELETE FROM {full_table}{where_clause};")
                deleted = cur.rowcount
                conn.commit()
                return deleted
