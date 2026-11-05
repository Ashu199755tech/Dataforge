import os
import csv
import json
import time
from typing import List, Dict, Any, Iterator, Optional
from backend.app.connectors.base import BaseConnector, ConnectionTestResult, TableMetadata, ColumnMetadata


class LocalFileConnector(BaseConnector):
    """
    Local File & Object Storage Connector.
    Supports CSV and JSON file extraction and ingestion.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_dir = config.get("base_path", "./data_storage")
        os.makedirs(self.base_dir, exist_ok=True)

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            if os.path.exists(self.base_dir) and os.access(self.base_dir, os.W_OK):
                latency = round((time.time() - start) * 1000, 2)
                return ConnectionTestResult(
                    success=True,
                    message=f"Local storage directory accessible: {self.base_dir}",
                    latency_ms=latency,
                    server_version="POSIX Filesystem"
                )
            else:
                return ConnectionTestResult(success=False, message="Directory not writable")
        except Exception as e:
            return ConnectionTestResult(success=False, message=str(e))

    def discover_schemas(self) -> List[str]:
        return ["default"]

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        files = []
        for f in os.listdir(self.base_dir):
            if f.endswith((".csv", ".json")):
                full_path = os.path.join(self.base_dir, f)
                cols = self.discover_columns(f)
                files.append(TableMetadata(
                    name=f,
                    schema_name="default",
                    table_type="FILE",
                    columns=cols
                ))
        return files

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        file_path = os.path.join(self.base_dir, table_name)
        cols = []
        if not os.path.exists(file_path):
            return []

        if table_name.endswith(".csv"):
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if header:
                    for col_name in header:
                        cols.append(ColumnMetadata(name=col_name.strip(), data_type="STRING"))
        elif table_name.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                        for k in data[0].keys():
                            cols.append(ColumnMetadata(name=k, data_type="STRING"))
                except Exception:
                    pass
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
        file_path = os.path.join(self.base_dir, table_name)
        if not os.path.exists(file_path):
            return

        batch = []
        if table_name.endswith(".csv"):
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Apply watermark filter if requested
                    if watermark_column and watermark_value is not None:
                        val = row.get(watermark_column)
                        if val is None or str(val) <= str(watermark_value):
                            continue

                    batch.append(dict(row))
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                if batch:
                    yield batch
        elif table_name.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                records = data if isinstance(data, list) else [data]
                for row in records:
                    if watermark_column and watermark_value is not None:
                        val = row.get(watermark_column)
                        if val is None or str(val) <= str(watermark_value):
                            continue
                    batch.append(row)
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                if batch:
                    yield batch

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

        # Ensure correct extension
        filename = table_name if ("." in table_name) else f"{table_name}.csv"
        file_path = os.path.join(self.base_dir, filename)

        mapped_records = []
        if column_mappings:
            mapping_dict = {m["source_column"]: m["target_column"] for m in column_mappings}
            for r in records:
                mapped_records.append({mapping_dict.get(k, k): v for k, v in r.items()})
        else:
            mapped_records = records

        file_exists = os.path.exists(file_path)
        mode = "w" if write_mode == "overwrite" or not file_exists else "a"

        if filename.endswith(".csv"):
            headers = list(mapped_records[0].keys())
            with open(file_path, mode, newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                if mode == "w" or not file_exists:
                    writer.writeheader()
                writer.writerows(mapped_records)
        elif filename.endswith(".json"):
            existing = []
            if file_exists and write_mode != "overwrite":
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
            existing.extend(mapped_records)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2, default=str)

        return len(mapped_records)

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return []

    def get_metadata(
        self,
        object_name: str,
        schema_name: Optional[str] = None
    ) -> Dict[str, Any]:
        file_path = os.path.join(self.base_dir, object_name)
        if not os.path.exists(file_path):
            return {
                "exists": False,
                "rowCount": 0,
                "columnCount": 0,
                "structure": [],
                "sizeInBytes": 0,
                "childItems": []
            }

        size_bytes = os.path.getsize(file_path)
        cols = self.discover_columns(object_name)
        row_cnt = 0

        try:
            if object_name.endswith(".csv"):
                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    # header count
                    next(reader, None)
                    row_cnt = sum(1 for _ in reader)
            elif object_name.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    row_cnt = len(data) if isinstance(data, list) else 1
        except Exception:
            row_cnt = 0

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
        file_path = os.path.join(self.base_dir, object_name)
        if os.path.exists(file_path):
            os.remove(file_path)
            return 1
        return 0
