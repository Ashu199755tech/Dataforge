import time
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Iterator, Optional

from backend.app.connectors.base import (
    BaseConnector,
    ColumnMetadata,
    TableMetadata,
    ConnectionTestResult
)


class BigQueryConnector(BaseConnector):
    """
    Enterprise Google Cloud BigQuery Connector.
    Connects to BigQuery via the official Google BigQuery REST API v2.
    Supports dataset discovery, table and column metadata inspection,
    bounded chunk streaming reads, batch writes, and upsert/merge executions.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.project_id = config.get("project_id", "").strip()
        self.dataset_id = config.get("dataset_id") or config.get("dataset") or config.get("schema", "")
        self.location = config.get("location", "US").strip()
        self.access_token = config.get("access_token") or config.get("token")
        self.credentials_json = config.get("credentials_json") or config.get("service_account_key")
        self.mock_mode = config.get("mock_mode", False)
        self._mock_tables: Dict[str, List[Dict[str, Any]]] = config.get("_mock_tables", {})

    def _get_auth_token(self) -> str:
        """Resolves OAuth2 Bearer token from access_token or service account key."""
        if self.access_token:
            return self.access_token

        if self.credentials_json:
            try:
                from google.oauth2 import service_account
                import google.auth.transport.requests

                key_dict = json.loads(self.credentials_json) if isinstance(self.credentials_json, str) else self.credentials_json
                creds = service_account.Credentials.from_service_account_info(
                    key_dict,
                    scopes=["https://www.googleapis.com/auth/bigquery"]
                )
                request = google.auth.transport.requests.Request()
                creds.refresh(request)
                return creds.token
            except Exception as ex:
                raise RuntimeError(f"Failed to authenticate BigQuery service account: {str(ex)}")

        return "mock_bq_token"

    def _get_api_headers(self) -> Dict[str, str]:
        token = self._get_auth_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DataForge-BigQuery/1.0"
        }

    def _make_api_request(self, endpoint: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes an HTTP request to the Google Cloud BigQuery REST API v2."""
        url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{self.project_id}/{endpoint.lstrip('/')}"
        headers = self._get_api_headers()
        data_bytes = json.dumps(payload).encode("utf-8") if payload else None

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"BigQuery API Error ({e.code}): {err_body}")
        except Exception as e:
            raise RuntimeError(f"BigQuery Network Error: {str(e)}")

    def test_connection(self) -> ConnectionTestResult:
        start_time = time.time()
        if self.mock_mode:
            return ConnectionTestResult(
                success=True,
                message=f"Connected to Google BigQuery (Project: '{self.project_id or 'mock-gcp-project'}', Dataset: '{self.dataset_id or 'analytics'}')",
                latency_ms=18.5,
                server_version="Google BigQuery v2"
            )

        if not self.project_id:
            return ConnectionTestResult(
                success=False,
                message="BigQuery configuration requires 'project_id'."
            )

        try:
            # Query datasets to verify connectivity and auth
            res = self._make_api_request("datasets?maxResults=1")
            latency = (time.time() - start_time) * 1000.0
            return ConnectionTestResult(
                success=True,
                message=f"Connected successfully to Google BigQuery project '{self.project_id}'.",
                latency_ms=round(latency, 2),
                server_version="Google BigQuery v2"
            )
        except Exception as ex:
            return ConnectionTestResult(
                success=False,
                message=f"BigQuery connection test failed: {str(ex)}"
            )

    def discover_schemas(self) -> List[str]:
        if self.mock_mode:
            schemas = ["analytics", "raw", "staging"]
            if self.dataset_id and self.dataset_id not in schemas:
                schemas.append(self.dataset_id)
            return schemas

        res = self._make_api_request("datasets")
        datasets = []
        for ds in res.get("datasets", []):
            ds_ref = ds.get("datasetReference", {})
            ds_id = ds_ref.get("datasetId")
            if ds_id:
                datasets.append(ds_id)
        return datasets if datasets else [self.dataset_id] if self.dataset_id else []

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        target_dataset = schema_name or self.dataset_id or "analytics"
        if self.mock_mode:
            return [
                TableMetadata(
                    name=t_name,
                    schema_name=target_dataset,
                    table_type="TABLE",
                    approx_row_count=len(rows),
                    columns=self.discover_columns(t_name, target_dataset)
                )
                for t_name, rows in self._mock_tables.items()
            ]

        res = self._make_api_request(f"datasets/{target_dataset}/tables")
        tables = []
        for tbl in res.get("tables", []):
            tbl_ref = tbl.get("tableReference", {})
            t_name = tbl_ref.get("tableId")
            t_type = tbl.get("type", "TABLE")
            if t_name:
                tables.append(TableMetadata(
                    name=t_name,
                    schema_name=target_dataset,
                    table_type=t_type,
                    columns=self.discover_columns(t_name, target_dataset)
                ))
        return tables

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        target_dataset = schema_name or self.dataset_id or "analytics"
        if self.mock_mode:
            sample_rows = self._mock_tables.get(table_name, [])
            if sample_rows:
                first_row = sample_rows[0]
                return [
                    ColumnMetadata(
                        name=col,
                        data_type="INT64" if isinstance(val, int) else ("FLOAT64" if isinstance(val, float) else "STRING"),
                        is_nullable=True,
                        is_primary_key=(col.lower() in ("id", f"{table_name.lower()}_id", "item_id"))
                    )
                    for col, val in first_row.items()
                ]
            return [
                ColumnMetadata(name="id", data_type="INT64", is_nullable=False, is_primary_key=True),
                ColumnMetadata(name="name", data_type="STRING", is_nullable=True)
            ]

        res = self._make_api_request(f"datasets/{target_dataset}/tables/{table_name}")
        fields = res.get("schema", {}).get("fields", [])
        cols = []
        for f in fields:
            c_name = f.get("name")
            dtype = f.get("type", "STRING")
            mode = f.get("mode", "NULLABLE")
            if c_name:
                cols.append(ColumnMetadata(
                    name=c_name,
                    data_type=dtype,
                    is_nullable=(mode != "REQUIRED"),
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

        target_dataset = schema_name or self.dataset_id or "analytics"
        col_clause = ", ".join([f"`{c}`" for c in columns]) if columns else "*"
        where_clauses = []
        if filter_expr:
            where_clauses.append(f"({filter_expr})")
        if watermark_column and watermark_value is not None:
            where_clauses.append(f"`{watermark_column}` > '{watermark_value}'")

        where_stmt = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT {col_clause} FROM `{self.project_id}.{target_dataset}.{table_name}` {where_stmt}"

        all_rows = self.execute_query(query)
        for i in range(0, len(all_rows), batch_size):
            yield all_rows[i:i + batch_size]

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

        # Apply column mapping
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

        target_dataset = schema_name or self.dataset_id or "analytics"
        first_row = transformed_records[0]
        cols = list(first_row.keys())

        clean_mode = write_mode.lower()
        if clean_mode in ("overwrite", "truncate"):
            self.execute_query(f"DELETE FROM `{self.project_id}.{target_dataset}.{table_name}` WHERE 1=1;")

        keys = key_columns or (self.config.get("primary_keys") if isinstance(self.config.get("primary_keys"), list) else None)

        if clean_mode == "upsert" and keys:
            # Upsert using standard BigQuery MERGE INTO
            temp_table = f"_df_stage_{int(time.time() * 1000)}"
            # Batch insert rows into temp staging table then merge
            values_rows = []
            for r in transformed_records:
                val_strs = []
                for c in cols:
                    v = r.get(c)
                    if v is None:
                        val_strs.append("NULL")
                    elif isinstance(v, (int, float)):
                        val_strs.append(str(v))
                    else:
                        escaped = str(v).replace("'", "''")
                        val_strs.append(f"'{escaped}'")
                values_rows.append(f"({', '.join(val_strs)})")

            target_tbl = f"`{self.project_id}.{target_dataset}.{table_name}`"
            cols_clause = ", ".join([f"`{c}`" for c in cols])
            join_cond = " AND ".join([f"T.`{k}` = S.`{k}`" for k in keys])
            update_set = ", ".join([f"`{c}` = S.`{c}`" for c in cols if c not in keys])

            merge_sql = f"""
                MERGE {target_tbl} T
                USING (SELECT * FROM UNNEST([{', '.join([f"STRUCT({', '.join([f'{v} AS `{c}`' for c, v in zip(cols, r.values())])})" for r in transformed_records])}])) S
                ON {join_cond}
                WHEN MATCHED THEN
                    UPDATE SET {update_set}
                WHEN NOT MATCHED THEN
                    INSERT ({cols_clause}) VALUES ({cols_clause});
            """
            self.execute_query(merge_sql)
        else:
            # Batch INSERT INTO
            values_rows = []
            for r in transformed_records:
                val_strs = []
                for c in cols:
                    v = r.get(c)
                    if v is None:
                        val_strs.append("NULL")
                    elif isinstance(v, (int, float)):
                        val_strs.append(str(v))
                    else:
                        escaped = str(v).replace("'", "''")
                        val_strs.append(f"'{escaped}'")
                values_rows.append(f"({', '.join(val_strs)})")

            insert_sql = f"INSERT INTO `{self.project_id}.{target_dataset}.{table_name}` ({', '.join([f'`{c}`' for c in cols])}) VALUES {', '.join(values_rows)};"
            self.execute_query(insert_sql)

        return len(transformed_records)

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if self.mock_mode:
            q_upper = query.upper()
            if "SELECT SCHEMA" in q_upper or "DATASET" in q_upper:
                return [{"schema_name": "analytics"}, {"schema_name": "raw"}]
            elif "SELECT TABLE" in q_upper or "TABLES" in q_upper:
                return [{"table_name": t, "table_type": "TABLE"} for t in self._mock_tables]
            elif "SELECT VERSION" in q_upper or "CURRENT_VERSION" in q_upper:
                return [{"ver": "Google BigQuery v2"}]
            elif "SELECT COUNT" in q_upper:
                for t in self._mock_tables:
                    if t.upper() in q_upper:
                        return [{"cnt": len(self._mock_tables[t])}]
                return [{"cnt": 0}]
            elif "SELECT" in q_upper and "FROM" in q_upper:
                for t, rows in self._mock_tables.items():
                    if t.upper() in q_upper:
                        if "WHERE" in q_upper:
                            import re
                            m = re.search(r"WHERE\s+(\w+)\s*=\s*'([^']+)'", query, re.IGNORECASE)
                            if m:
                                col, val = m.group(1), m.group(2)
                                return [r for r in rows if str(r.get(col, "")).upper() == val.upper()]
                        return list(rows)
            return []

        payload = {
            "query": query,
            "useLegacySql": False,
            "timeoutMs": 60000,
            "location": self.location
        }
        res = self._make_api_request("queries", method="POST", payload=payload)

        # Parse BigQuery schema and matrix format
        schema_fields = res.get("schema", {}).get("fields", [])
        cols = [f.get("name") for f in schema_fields]
        rows = []
        for r in res.get("rows", []):
            vals = [v.get("v") for v in r.get("f", [])]
            rows.append({cols[i]: vals[i] for i in range(min(len(cols), len(vals)))})
        return rows
