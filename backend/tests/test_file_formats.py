import io
import gzip
import pytest
from datetime import datetime
from backend.app.formats.registry import FormatRegistry
from backend.app.formats.models import DataType, ColumnSchema, SchemaDefinition
from backend.app.formats.csv_handler import CsvFormatHandler
from backend.app.formats.json_handler import JsonFormatHandler, JsonLinesFormatHandler
from backend.app.formats.parquet_handler import ParquetFormatHandler
from backend.app.formats.avro_handler import AvroFormatHandler
from backend.app.formats.orc_handler import OrcFormatHandler
from backend.app.formats.excel_handler import ExcelFormatHandler
from backend.app.formats.text_handler import TextFormatHandler


SAMPLE_RECORDS = [
    {"id": 1, "name": "Alpha", "amount": 100.5, "active": True},
    {"id": 2, "name": "Beta", "amount": 250.0, "active": False},
    {"id": 3, "name": "Gamma", "amount": 999.75, "active": True},
]


class TestCsvFormat:
    def test_csv_write_and_read(self):
        handler = CsvFormatHandler(options={"delimiter": ",", "has_header": True})
        buf = io.BytesIO()
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"
        assert records[1]["id"] == "2"

    def test_csv_compression_gzip(self):
        handler = CsvFormatHandler(options={"compression": "gzip", "has_header": True})
        buf = io.BytesIO()
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[2]["name"] == "Gamma"

    def test_csv_schema_inference_and_preview(self):
        handler = CsvFormatHandler(options={"has_header": True})
        buf = io.BytesIO()
        handler.write_records(iter(SAMPLE_RECORDS), buf)

        buf.seek(0)
        schema = handler.infer_schema(buf)
        assert len(schema.columns) == 4
        names = schema.column_names()
        assert "name" in names
        assert "amount" in names

        buf.seek(0)
        preview = handler.preview(buf, limit=2)
        assert len(preview.rows) == 2
        assert preview.truncated is True


class TestJsonAndJsonLinesFormat:
    def test_json_write_and_read(self):
        handler = JsonFormatHandler()
        buf = io.BytesIO()
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"

    def test_json_nested_flattening(self):
        nested = [
            {"id": 1, "user": {"first": "Jane", "last": "Doe"}, "stats": {"score": 95}}
        ]
        handler = JsonFormatHandler(options={"flatten_nested": True})
        buf = io.BytesIO()
        handler.write_records(iter(nested), buf)

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 1
        assert records[0]["user_first"] == "Jane"
        assert records[0]["stats_score"] == 95

    def test_json_lines_write_and_read(self):
        handler = JsonLinesFormatHandler()
        buf = io.BytesIO()
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[1]["name"] == "Beta"

    def test_json_lines_skip_invalid_records(self):
        handler = JsonLinesFormatHandler(options={"skip_invalid_records": True})
        bad_jsonl = b'{"id": 1, "name": "Valid"}\nMALFORMED_LINE\n{"id": 2, "name": "AlsoValid"}\n'
        buf = io.BytesIO(bad_jsonl)

        records = list(handler.read_records(buf))
        assert len(records) == 2
        assert records[0]["id"] == 1
        assert records[1]["id"] == 2


class TestParquetFormat:
    def test_parquet_write_and_read(self):
        handler = ParquetFormatHandler(options={"compression": "snappy"})
        buf = io.BytesIO()
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"
        assert records[0]["amount"] == 100.5
        assert records[0]["active"] is True

    def test_parquet_column_projection(self):
        handler = ParquetFormatHandler()
        buf = io.BytesIO()
        handler.write_records(iter(SAMPLE_RECORDS), buf)

        buf.seek(0)
        records = list(handler.read_records(buf, columns=["name", "amount"]))
        assert len(records) == 3
        assert set(records[0].keys()) == {"name", "amount"}

    def test_parquet_schema_discovery(self):
        handler = ParquetFormatHandler()
        buf = io.BytesIO()
        handler.write_records(iter(SAMPLE_RECORDS), buf)

        buf.seek(0)
        schema = handler.infer_schema(buf)
        assert len(schema.columns) == 4
        col_map = {c.name: c.data_type for c in schema.columns}
        assert col_map["id"] == DataType.INTEGER.value or col_map["id"] == DataType.BIGINT.value
        assert col_map["name"] == DataType.STRING.value
        assert col_map["amount"] == DataType.DOUBLE.value
        assert col_map["active"] == DataType.BOOLEAN.value


class TestAvroFormat:
    def test_avro_write_and_read(self):
        handler = AvroFormatHandler(options={"compression": "deflate"})
        buf = io.BytesIO()
        schema_def = SchemaDefinition(columns=[
            ColumnSchema(name="id", data_type=DataType.INTEGER.value),
            ColumnSchema(name="name", data_type=DataType.STRING.value),
            ColumnSchema(name="amount", data_type=DataType.DOUBLE.value),
            ColumnSchema(name="active", data_type=DataType.BOOLEAN.value),
        ])
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf, schema=schema_def)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"

    def test_avro_header_schema_discovery(self):
        handler = AvroFormatHandler()
        buf = io.BytesIO()
        schema_def = SchemaDefinition(columns=[
            ColumnSchema(name="id", data_type=DataType.INTEGER.value),
            ColumnSchema(name="name", data_type=DataType.STRING.value),
        ])
        records = [{"id": 1, "name": "Test1"}]
        handler.write_records(iter(records), buf, schema=schema_def)

        buf.seek(0)
        discovered = handler.infer_schema(buf)
        names = discovered.column_names()
        assert "id" in names
        assert "name" in names


class TestOrcFormat:
    def test_orc_write_and_read(self):
        handler = OrcFormatHandler(options={"compression": "zlib"})
        buf = io.BytesIO()
        schema_def = SchemaDefinition(columns=[
            ColumnSchema(name="id", data_type=DataType.INTEGER.value),
            ColumnSchema(name="name", data_type=DataType.STRING.value),
            ColumnSchema(name="amount", data_type=DataType.DOUBLE.value),
            ColumnSchema(name="active", data_type=DataType.BOOLEAN.value),
        ])
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf, schema=schema_def)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"
        assert records[1]["name"] == "Beta"

    def test_orc_column_projection(self):
        handler = OrcFormatHandler()
        buf = io.BytesIO()
        schema_def = SchemaDefinition(columns=[
            ColumnSchema(name="id", data_type=DataType.INTEGER.value),
            ColumnSchema(name="name", data_type=DataType.STRING.value),
            ColumnSchema(name="amount", data_type=DataType.DOUBLE.value),
        ])
        handler.write_records(iter(SAMPLE_RECORDS), buf, schema=schema_def)

        buf.seek(0)
        records = list(handler.read_records(buf, columns=["name"]))
        assert len(records) == 3
        assert list(records[0].keys()) == ["name"]


class TestExcelFormat:
    def test_excel_write_and_read(self):
        handler = ExcelFormatHandler(options={"has_header": True})
        buf = io.BytesIO()
        bytes_written = handler.write_records(iter(SAMPLE_RECORDS), buf)
        assert bytes_written > 0

        buf.seek(0)
        records = list(handler.read_records(buf))
        assert len(records) == 3
        assert records[0]["name"] == "Alpha"

    def test_excel_schema_inference(self):
        handler = ExcelFormatHandler(options={"has_header": True})
        buf = io.BytesIO()
        handler.write_records(iter(SAMPLE_RECORDS), buf)

        buf.seek(0)
        schema = handler.infer_schema(buf)
        assert len(schema.columns) == 4
        assert "name" in schema.column_names()


class TestTextFormat:
    def test_text_write_and_read(self):
        handler = TextFormatHandler(options={"text_column": "log_entry"})
        records = [
            {"log_entry": "2026-05-10 INFO Startup complete"},
            {"log_entry": "2026-05-10 WARN Latency spike"},
            {"log_entry": "2026-05-10 ERROR Connection refused"},
        ]
        buf = io.BytesIO()
        bytes_written = handler.write_records(iter(records), buf)
        assert bytes_written > 0

        buf.seek(0)
        read_back = list(handler.read_records(buf))
        assert len(read_back) == 3
        assert read_back[0]["line_no"] == 1
        assert "Startup complete" in read_back[0]["log_entry"]


class TestFormatRegistry:
    def test_extension_detection(self):
        assert FormatRegistry.detect_format_from_filename("data.parquet") == "parquet"
        assert FormatRegistry.detect_format_from_filename("orders.csv.gz") == "csv"
        assert FormatRegistry.detect_format_from_filename("events.jsonl") == "jsonl"
        assert FormatRegistry.detect_format_from_filename("archive.avro") == "avro"
        assert FormatRegistry.detect_format_from_filename("metrics.orc") == "orc"
        assert FormatRegistry.detect_format_from_filename("finance.xlsx") == "xlsx"
        assert FormatRegistry.detect_format_from_filename("server.log") == "csv"

    def test_magic_bytes_detection(self):
        assert FormatRegistry.detect_format_from_bytes(b"PAR1xxxxxxxxPAR1") == "parquet"
        assert FormatRegistry.detect_format_from_bytes(b"Obj\x01xxxx") == "avro"
        assert FormatRegistry.detect_format_from_bytes(b"ORCxxxx") == "orc"
        assert FormatRegistry.detect_format_from_bytes(b'{"key": "val"}') == "json"
        assert FormatRegistry.detect_format_from_bytes(b'{"id":1}\n{"id":2}\n') == "jsonl"

    def test_get_reader_and_writer(self):
        reader = FormatRegistry.get_reader("parquet")
        assert isinstance(reader, ParquetFormatHandler)

        writer = FormatRegistry.get_writer("csv")
        assert isinstance(writer, CsvFormatHandler)

        with pytest.raises(ValueError):
            FormatRegistry.get_reader("unsupported_format_xyz")
