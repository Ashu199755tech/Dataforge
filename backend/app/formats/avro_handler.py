from typing import Dict, Any, Iterator, Optional, List, BinaryIO

try:
    import fastavro
    HAS_FASTAVRO = True
except ImportError:
    fastavro = None
    HAS_FASTAVRO = False

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.models import SchemaDefinition, ColumnSchema, DataType


def _avro_type_to_dataforge(avro_type: Any) -> str:
    if isinstance(avro_type, list):
        # Union type, e.g. ["null", "string"]
        non_null = [t for t in avro_type if t != "null"]
        if non_null:
            return _avro_type_to_dataforge(non_null[0])
        return DataType.STRING.value

    if isinstance(avro_type, dict):
        base_t = avro_type.get("type")
        if base_t == "record":
            return DataType.JSON.value
        elif base_t == "array":
            return DataType.ARRAY.value
        elif base_t == "map":
            return DataType.MAP.value
        return _avro_type_to_dataforge(base_t)

    t_str = str(avro_type).lower()
    mapping = {
        "string": DataType.STRING.value,
        "int": DataType.INTEGER.value,
        "long": DataType.BIGINT.value,
        "float": DataType.FLOAT.value,
        "double": DataType.DOUBLE.value,
        "boolean": DataType.BOOLEAN.value,
        "bytes": DataType.BINARY.value,
    }
    return mapping.get(t_str, DataType.STRING.value)


class AvroFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    Apache Avro container format handler using fastavro.
    Provides schema discovery from Avro headers and streaming record I/O.
    """

    def read_records(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        reader = fastavro.reader(stream)
        count = 0
        for record in reader:
            if columns:
                record = {k: v for k, v in record.items() if k in columns}
            yield record
            count += 1
            if limit and count >= limit:
                break

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        reader = fastavro.reader(stream)
        writer_schema = reader.writer_schema

        columns = []
        if isinstance(writer_schema, dict) and "fields" in writer_schema:
            for field in writer_schema["fields"]:
                field_name = field["name"]
                field_type = _avro_type_to_dataforge(field["type"])
                nullable = isinstance(field["type"], list) and "null" in field["type"]
                columns.append(ColumnSchema(name=field_name, data_type=field_type, nullable=nullable))

        if hasattr(stream, "seek"):
            stream.seek(start_pos)

        return SchemaDefinition(columns=columns)

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        all_records = list(records)
        if not all_records:
            return 0

        # Construct Avro schema if not provided
        fields = []
        if schema and schema.columns:
            for col in schema.columns:
                t = "string"
                if col.data_type == DataType.INTEGER.value:
                    t = "int"
                elif col.data_type == DataType.BIGINT.value:
                    t = "long"
                elif col.data_type in (DataType.FLOAT.value, DataType.DOUBLE.value):
                    t = "double"
                elif col.data_type == DataType.BOOLEAN.value:
                    t = "boolean"
                fields.append({"name": col.name, "type": ["null", t] if col.nullable else t})
        else:
            first_row = all_records[0]
            for k in first_row.keys():
                fields.append({"name": k, "type": ["null", "string"]})

        avro_schema = {
            "type": "record",
            "name": "DataForgeRecord",
            "fields": fields
        }

        codec = self.options.get("compression", "deflate").lower()
        if codec in ("none", "uncompressed"):
            codec = "null"

        fastavro.writer(target_stream, avro_schema, all_records, codec=codec)
        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)
