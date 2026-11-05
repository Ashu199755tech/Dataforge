import time
from typing import List, Dict, Any, Iterator, Optional
import pymysql
import pymysql.cursors
from backend.app.connectors.base import BaseConnector, ConnectionTestResult, TableMetadata, ColumnMetadata


class MySQLConnector(BaseConnector):
    """
    Enterprise MySQL Connector.
    Supports low-memory streaming cursors, schema discovery, and bulk upsert.
    """

    def _get_connection(self, cursorclass=pymysql.cursors.DictCursor):
        return pymysql.connect(
            host=self.config.get("host", "localhost"),
            port=int(self.config.get("port", 3306)),
            user=self.config.get("user", "root"),
            password=self.config.get("password", ""),
            database=self.config.get("database", "mysql"),
            charset="utf8mb4",
            connect_timeout=10,
            cursorclass=cursorclass
        )

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION();")
                ver = cur.fetchone()["VERSION()"]
            conn.close()
            latency = (time.time() - start) * 1000
            return ConnectionTestResult(
                success=True,
                message="Successfully connected to MySQL",
                latency_ms=round(latency, 2),
                server_version=ver
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"MySQL connection failed: {str(e)}"
            )

    def discover_schemas(self) -> List[str]:
        query = "SHOW DATABASES;"
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                system_dbs = {"information_schema", "performance_schema", "sys"}
                return [row["Database"] for row in cur.fetchall() if row["Database"] not in system_dbs]
        finally:
            conn.close()

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        db_name = schema_name or self.config.get("database", "mysql")
        query = f"SHOW FULL TABLES FROM `{db_name}`;"
        tables = []
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                key_name = f"Tables_in_{db_name}"
                for r in rows:
                    tbl = r.get(key_name) or list(r.values())[0]
                    tbl_type = r.get("Table_type", "BASE TABLE")
                    cols = self.discover_columns(tbl, db_name)
                    tables.append(TableMetadata(
                        name=tbl,
                        schema_name=db_name,
                        table_type="VIEW" if "VIEW" in tbl_type else "TABLE",
                        columns=cols
                    ))
        finally:
            conn.close()
        return tables

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        db_name = schema_name or self.config.get("database", "mysql")
        query = f"DESCRIBE `{db_name}`.`{table_name}`;"
        cols = []
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                for r in cur.fetchall():
                    cols.append(ColumnMetadata(
                        name=r["Field"],
                        data_type=r["Type"],
                        is_nullable=(r["Null"] == "YES"),
                        is_primary_key=(r["Key"] == "PRI"),
                        default_value=str(r["Default"]) if r["Default"] is not None else None
                    ))
        except Exception:
            return []
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
        db_name = schema_name or self.config.get("database", "mysql")
        col_clause = ", ".join(f"`{c}`" for c in columns) if columns else "*"
        full_table = f"`{db_name}`.`{table_name}`"

        where_clauses = []
        params = []
        if filter_expr:
            where_clauses.append(f"({filter_expr})")
        if watermark_column and watermark_value is not None:
            where_clauses.append(f"`{watermark_column}` > %s")
            params.append(watermark_value)

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT {col_clause} FROM {full_table}{where_sql}"

        # SSDictCursor provides server-side streaming cursor
        conn = self._get_connection(cursorclass=pymysql.cursors.SSDictCursor)
        try:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                while True:
                    rows = cur.fetchmany(batch_size)
                    if not rows:
                        break
                    yield rows
        finally:
            conn.close()

    def _auto_create_table_if_needed(self, conn, table_name: str, sample_record: Dict[str, Any], key_columns: Optional[List[str]], db_name: str):
        col_defs = []
        for k, v in sample_record.items():
            if isinstance(v, int):
                col_type = "BIGINT"
            elif isinstance(v, float):
                col_type = "DECIMAL(18, 4)"
            elif isinstance(v, bool):
                col_type = "TINYINT(1)"
            elif isinstance(v, (dict, list)):
                col_type = "JSON"
            else:
                col_type = "TEXT"
            col_defs.append(f"`{k}` {col_type}")

        if key_columns:
            pk_cols = ", ".join(f"`{c}`" for c in key_columns)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")

        create_sql = f"CREATE TABLE IF NOT EXISTS `{db_name}`.`{table_name}` ({', '.join(col_defs)}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
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

        db_name = schema_name or self.config.get("database", "mysql")
        full_table = f"`{db_name}`.`{table_name}`"

        # Apply column mappings if provided
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
                self._auto_create_table_if_needed(conn, table_name, mapped_records[0], key_columns, db_name)

            with conn.cursor() as cur:
                if write_mode == "overwrite":
                    cur.execute(f"TRUNCATE TABLE {full_table};")

                col_names = ", ".join(f"`{c}`" for c in cols)
                placeholders = ", ".join(["%s"] * len(cols))

                if write_mode == "upsert" and key_columns:
                    update_clauses = [f"`{c}`=VALUES(`{c}`)" for c in cols if c not in key_columns]
                    update_sql = f" ON DUPLICATE KEY UPDATE {', '.join(update_clauses)}" if update_clauses else ""
                    sql = f"INSERT INTO {full_table} ({col_names}) VALUES ({placeholders}){update_sql};"
                else:
                    sql = f"INSERT INTO {full_table} ({col_names}) VALUES ({placeholders});"

                data_tuples = [tuple(r.get(c) for c in cols) for r in mapped_records]
                cur.executemany(sql, data_tuples)
            conn.commit()
        finally:
            conn.close()

        return len(mapped_records)

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if cur.description:
                    return cur.fetchall()
                conn.commit()
                return []
        finally:
            conn.close()

    def get_metadata(
        self,
        object_name: str,
        schema_name: Optional[str] = None
    ) -> Dict[str, Any]:
        db_name = schema_name or self.config.get("database", "mysql")
        cols = self.discover_columns(object_name, db_name)
        if not cols:
            return {
                "exists": False,
                "rowCount": 0,
                "columnCount": 0,
                "structure": [],
                "sizeInBytes": 0,
                "childItems": []
            }

        full_table = f"`{db_name}`.`{object_name}`"
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) as cnt FROM {full_table};")
                row_cnt = int(cur.fetchone()["cnt"])

                try:
                    cur.execute(
                        "SELECT (data_length + index_length) as sz FROM information_schema.tables WHERE table_schema=%s AND table_name=%s;",
                        (db_name, object_name)
                    )
                    res = cur.fetchone()
                    size_bytes = int(res["sz"]) if res and res["sz"] is not None else 0
                except Exception:
                    size_bytes = 0
        finally:
            conn.close()

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
        db_name = schema_name or self.config.get("database", "mysql")
        full_table = f"`{db_name}`.`{object_name}`"

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                if truncate:
                    cur.execute(f"TRUNCATE TABLE {full_table};")
                    conn.commit()
                    return 0

                where_clause = f" WHERE {filter_expr}" if filter_expr and filter_expr.strip() else ""
                cur.execute(f"DELETE FROM {full_table}{where_clause};")
                deleted = cur.rowcount
                conn.commit()
                return deleted
        finally:
            conn.close()
