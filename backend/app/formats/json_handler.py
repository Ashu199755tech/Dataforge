import json
import io
import gzip
import bz2
from typing import Dict, Any, Iterator, Optional, List, BinaryIO

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.models import SchemaDefinition, ColumnSchema, DataType


def _flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = "_") -> Dict[str, Any]:
    items: List[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _infer_type_from_val(val: Any) -> str:
    if val is None:
        return DataType.STRING.value
    if isinstance(val, bool):
        return DataType.BOOLEAN.value
    if isinstance(val, int):
        return DataType.INTEGER.value
    if isinstance(val, float):
        return DataType.DOUBLE.value
    if isinstance(val, dict):
        return DataType.JSON.value
    if isinstance(val, list):
        return DataType.ARRAY.value
    return DataType.STRING.value


class JsonLinesFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    Newline-delimited JSON (JSON Lines / ndjson) handler.
    High-throughput streaming reader and writer with low memory footprint.
    """

    def _get_decompressed_stream(self, stream: BinaryIO) -> BinaryIO:
        compression = self.options.get("compression", "none").lower()
        if compression in ("gzip", "gz"):
            return gzip.GzipFile(fileobj=stream, mode="rb")
        elif compression in ("bz2", "bzip2"):
            return bz2.BZ2File(stream, mode="rb")
        return stream

    def read_records(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        raw_stream = self._get_decompressed_stream(stream)
        encoding = self.options.get("encoding", "utf-8")
        flatten = self.options.get("flatten_nested", False)
        skip_invalid = self.options.get("skip_invalid_records", False)

        text_stream = io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace")
        count = 0
        try:
            for line in text_stream:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    record = json.loads(line_str)
                    if not isinstance(record, dict):
                        continue
                except Exception:
                    if skip_invalid:
                        continue
                    raise

                if flatten:
                    record = _flatten_dict(record)

                if columns:
                    record = {k: v for k, v in record.items() if k in columns}

                yield record
                count += 1
                if limit and count >= limit:
                    break
        finally:
            text_stream.detach()

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        columns_map: Dict[str, str] = {}
        sample_count = 0

        for record in self.read_records(stream, limit=max_records):
            sample_count += 1
            for k, v in record.items():
                if k not in columns_map or columns_map[k] == DataType.STRING.value:
                    columns_map[k] = _infer_type_from_val(v)

        if hasattr(stream, "seek"):
            stream.seek(start_pos)

        col_schemas = [
            ColumnSchema(name=col, data_type=dtype, nullable=True)
            for col, dtype in columns_map.items()
        ]
        return SchemaDefinition(columns=col_schemas, record_count=sample_count)

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        compression = self.options.get("compression", "none").lower()
        encoding = self.options.get("encoding", "utf-8")

        out_stream = target_stream
        if compression in ("gzip", "gz"):
            out_stream = gzip.GzipFile(fileobj=target_stream, mode="wb")
        elif compression in ("bz2", "bzip2"):
            out_stream = bz2.BZ2File(target_stream, mode="wb")

        for record in records:
            line = json.dumps(record, default=str) + "\n"
            out_stream.write(line.encode(encoding))

        out_stream.flush()
        if out_stream != target_stream and hasattr(out_stream, "close"):
            out_stream.close()

        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)


class JsonFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    Standard JSON format handler.
    Handles JSON arrays `[{...}]` and object envelopes `{"data": [{...}]}`.
    """

    def _get_decompressed_stream(self, stream: BinaryIO) -> BinaryIO:
        compression = self.options.get("compression", "none").lower()
        if compression in ("gzip", "gz"):
            return gzip.GzipFile(fileobj=stream, mode="rb")
        elif compression in ("bz2", "bzip2"):
            return bz2.BZ2File(stream, mode="rb")
        return stream

    def read_records(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        raw_stream = self._get_decompressed_stream(stream)
        encoding = self.options.get("encoding", "utf-8")
        flatten = self.options.get("flatten_nested", False)
        json_root_path = self.options.get("json_root_path")

        content = raw_stream.read().decode(encoding, errors="replace")
        data = json.loads(content)

        if isinstance(data, dict):
            # If wrapped in common keys: records, data, items, rows
            if json_root_path and json_root_path in data and isinstance(data[json_root_path], list):
                items = data[json_root_path]
            elif "records" in data and isinstance(data["records"], list):
                items = data["records"]
            elif "data" in data and isinstance(data["data"], list):
                items = data["data"]
            elif "items" in data and isinstance(data["items"], list):
                items = data["items"]
            else:
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            items = [{"value": data}]

        count = 0
        for item in items:
            if not isinstance(item, dict):
                item = {"value": item}
            if flatten:
                item = _flatten_dict(item)
            if columns:
                item = {k: v for k, v in item.items() if k in columns}

            yield item
            count += 1
            if limit and count >= limit:
                break

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        columns_map: Dict[str, str] = {}
        sample_count = 0

        for record in self.read_records(stream, limit=max_records):
            sample_count += 1
            for k, v in record.items():
                if k not in columns_map or columns_map[k] == DataType.STRING.value:
                    columns_map[k] = _infer_type_from_val(v)

        if hasattr(stream, "seek"):
            stream.seek(start_pos)

        col_schemas = [
            ColumnSchema(name=col, data_type=dtype, nullable=True)
            for col, dtype in columns_map.items()
        ]
        return SchemaDefinition(columns=col_schemas, record_count=sample_count)

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        compression = self.options.get("compression", "none").lower()
        encoding = self.options.get("encoding", "utf-8")

        out_stream = target_stream
        if compression in ("gzip", "gz"):
            out_stream = gzip.GzipFile(fileobj=target_stream, mode="wb")
        elif compression in ("bz2", "bzip2"):
            out_stream = bz2.BZ2File(target_stream, mode="wb")

        all_records = list(records)
        serialized = json.dumps(all_records, indent=2, default=str)
        out_stream.write(serialized.encode(encoding))

        out_stream.flush()
        if out_stream != target_stream and hasattr(out_stream, "close"):
            out_stream.close()

        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)
