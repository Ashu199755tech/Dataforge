from typing import Dict, Any, Iterator, Optional, List, BinaryIO
import io
import pyarrow as pa
import pyarrow.parquet as pq

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.models import SchemaDefinition, ColumnSchema, DataType


def _arrow_type_to_dataforge(pa_type: pa.DataType) -> str:
    if pa.types.is_boolean(pa_type):
        return DataType.BOOLEAN.value
    elif pa.types.is_int8(pa_type) or pa.types.is_int16(pa_type) or pa.types.is_int32(pa_type):
        return DataType.INTEGER.value
    elif pa.types.is_int64(pa_type):
        return DataType.BIGINT.value
    elif pa.types.is_float32(pa_type):
        return DataType.FLOAT.value
    elif pa.types.is_float64(pa_type):
        return DataType.DOUBLE.value
    elif pa.types.is_timestamp(pa_type):
        return DataType.TIMESTAMP.value
    elif pa.types.is_date(pa_type):
        return DataType.DATE.value
    elif pa.types.is_decimal(pa_type):
        return DataType.DECIMAL.value
    elif pa.types.is_binary(pa_type) or pa.types.is_fixed_size_binary(pa_type):
        return DataType.BINARY.value
    elif pa.types.is_list(pa_type) or pa.types.is_large_list(pa_type):
        return DataType.ARRAY.value
    elif pa.types.is_map(pa_type) or pa.types.is_struct(pa_type):
        return DataType.JSON.value
    return DataType.STRING.value


class ParquetFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    High-performance Apache Parquet handler using PyArrow.
    Features row-group streaming, column projection pushdown,
    and snappy / zstd / gzip compression support.
    """

    def read_records(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        # pq.ParquetFile can read directly from file-like binary stream
        parquet_file = pq.ParquetFile(stream)
        valid_cols = None
        if columns:
            schema_cols = parquet_file.schema.names
            valid_cols = [c for c in columns if c in schema_cols]

        yielded = 0
        num_row_groups = parquet_file.num_row_groups

        for i in range(num_row_groups):
            table = parquet_file.read_row_group(i, columns=valid_cols)
            batch_records = table.to_pylist()

            for rec in batch_records:
                yield rec
                yielded += 1
                if limit and yielded >= limit:
                    return

    def read_arrow_table(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> pa.Table:
        parquet_file = pq.ParquetFile(stream)
        valid_cols = None
        if columns:
            schema_cols = parquet_file.schema.names
            valid_cols = [c for c in columns if c in schema_cols]

        table = parquet_file.read(columns=valid_cols)
        if limit and table.num_rows > limit:
            return table.slice(0, limit)
        return table

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        parquet_file = pq.ParquetFile(stream)
        pa_schema = parquet_file.schema_arrow

        columns = []
        for field in pa_schema:
            col_type = _arrow_type_to_dataforge(field.type)
            columns.append(
                ColumnSchema(
                    name=field.name,
                    data_type=col_type,
                    nullable=field.nullable
                )
            )

        if hasattr(stream, "seek"):
            stream.seek(start_pos)

        total_rows = parquet_file.metadata.num_rows
        return SchemaDefinition(columns=columns, record_count=total_rows)

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        all_records = list(records)
        if not all_records:
            return 0
        table = pa.Table.from_pylist(all_records)
        return self.write_arrow_table(table, target_stream)

    def write_arrow_table(
        self,
        table: pa.Table,
        target_stream: BinaryIO
    ) -> int:
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        compression = self.options.get("compression", "snappy").lower()
        if compression not in ("snappy", "gzip", "zstd", "none", "uncompressed"):
            compression = "snappy"
        if compression == "none":
            compression = "uncompressed"

        pq.write_table(table, target_stream, compression=compression)
        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)
