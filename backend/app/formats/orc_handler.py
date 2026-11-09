from typing import Dict, Any, Iterator, Optional, List, BinaryIO

try:
    import pyorc
    HAS_PYORC = True
except ImportError:
    pyorc = None
    HAS_PYORC = False

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.models import SchemaDefinition, ColumnSchema, DataType


def _orc_type_to_dataforge(orc_type: Any) -> str:
    kind = str(getattr(orc_type, "kind", orc_type)).lower()
    if "int" in kind or "short" in kind or "byte" in kind:
        return DataType.INTEGER.value
    elif "long" in kind or "bigint" in kind:
        return DataType.BIGINT.value
    elif "float" in kind:
        return DataType.FLOAT.value
    elif "double" in kind:
        return DataType.DOUBLE.value
    elif "bool" in kind:
        return DataType.BOOLEAN.value
    elif "timestamp" in kind:
        return DataType.TIMESTAMP.value
    elif "date" in kind:
        return DataType.DATE.value
    elif "decimal" in kind:
        return DataType.DECIMAL.value
    elif "binary" in kind:
        return DataType.BINARY.value
    elif "array" in kind or "list" in kind:
        return DataType.ARRAY.value
    elif "map" in kind or "struct" in kind:
        return DataType.JSON.value
    return DataType.STRING.value


class OrcFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    Apache ORC (Optimized Row Columnar) handler using pyorc.
    Supports stripe streaming, column projections, and zlib/snappy compression.
    """

    def read_records(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        if not HAS_PYORC or pyorc is None:
            raise RuntimeError("pyorc is not installed. Please install pyorc to process ORC files.")
        reader = pyorc.Reader(stream)
        schema = reader.schema
        field_names = [f for f in schema.fields.keys()]

        count = 0
        for row in reader:
            record = {}
            for idx, val in enumerate(row):
                col_name = field_names[idx] if idx < len(field_names) else f"col_{idx}"
                if columns and col_name not in columns:
                    continue
                record[col_name] = val

            yield record
            count += 1
            if limit and count >= limit:
                break

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        if not HAS_PYORC or pyorc is None:
            raise RuntimeError("pyorc is not installed. Please install pyorc to process ORC files.")
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        reader = pyorc.Reader(stream)
        schema = reader.schema

        columns = []
        for field_name, field_type in schema.fields.items():
            dt = _orc_type_to_dataforge(field_type)
            columns.append(ColumnSchema(name=field_name, data_type=dt, nullable=True))

        if hasattr(stream, "seek"):
            stream.seek(start_pos)

        return SchemaDefinition(columns=columns, record_count=len(reader))

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        if not HAS_PYORC or pyorc is None:
            raise RuntimeError("pyorc is not installed. Please install pyorc to process ORC files.")
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        all_records = list(records)
        if not all_records:
            return 0

        # Construct struct schema string for pyorc
        field_defs = []
        col_names = []
        if schema and schema.columns:
            for c in schema.columns:
                t = "string"
                if c.data_type == DataType.INTEGER.value:
                    t = "int"
                elif c.data_type == DataType.BIGINT.value:
                    t = "bigint"
                elif c.data_type in (DataType.FLOAT.value, DataType.DOUBLE.value):
                    t = "double"
                elif c.data_type == DataType.BOOLEAN.value:
                    t = "boolean"
                field_defs.append(f"{c.name}:{t}")
                col_names.append(c.name)
        else:
            first_row = all_records[0]
            for k in first_row.keys():
                field_defs.append(f"{k}:string")
                col_names.append(k)

        schema_str = f"struct<{','.join(field_defs)}>"

        compression_opt = self.options.get("compression", "zlib").upper()
        if compression_opt == "SNAPPY":
            compression = pyorc.CompressionKind.SNAPPY
        elif compression_opt == "ZSTD":
            compression = pyorc.CompressionKind.ZSTD
        elif compression_opt in ("NONE", "UNCOMPRESSED"):
            compression = pyorc.CompressionKind.NONE
        else:
            compression = pyorc.CompressionKind.ZLIB

        with pyorc.Writer(target_stream, schema_str, compression=compression) as writer:
            for rec in all_records:
                row_tuple = tuple(rec.get(col) for col in col_names)
                writer.write(row_tuple)

        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)
