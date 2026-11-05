import os
from typing import Dict, Any, Type, Optional

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.csv_handler import CsvFormatHandler
from backend.app.formats.json_handler import JsonFormatHandler, JsonLinesFormatHandler
from backend.app.formats.parquet_handler import ParquetFormatHandler
from backend.app.formats.avro_handler import AvroFormatHandler
from backend.app.formats.orc_handler import OrcFormatHandler
from backend.app.formats.excel_handler import ExcelFormatHandler
from backend.app.formats.text_handler import TextFormatHandler


class FormatRegistry:
    """
    Central factory and registry for all supported multi-cloud file formats.
    Provides automatic format resolution, extension matching, and magic-byte detection.
    """

    _HANDLERS: Dict[str, Type[Any]] = {
        "csv": CsvFormatHandler,
        "tsv": CsvFormatHandler,
        "json": JsonFormatHandler,
        "jsonl": JsonLinesFormatHandler,
        "ndjson": JsonLinesFormatHandler,
        "parquet": ParquetFormatHandler,
        "avro": AvroFormatHandler,
        "orc": OrcFormatHandler,
        "excel": ExcelFormatHandler,
        "xlsx": ExcelFormatHandler,
        "xls": ExcelFormatHandler,
        "text": TextFormatHandler,
        "txt": TextFormatHandler,
    }

    @classmethod
    def get_reader(cls, format_name: str, options: Optional[Dict[str, Any]] = None) -> BaseFormatReader:
        key = format_name.lower().strip()
        handler_cls = cls._HANDLERS.get(key)
        if not handler_cls:
            raise ValueError(f"Unsupported file format '{format_name}'. Supported formats: {list(cls._HANDLERS.keys())}")
        return handler_cls(options or {})

    @classmethod
    def get_writer(cls, format_name: str, options: Optional[Dict[str, Any]] = None) -> BaseFormatWriter:
        key = format_name.lower().strip()
        handler_cls = cls._HANDLERS.get(key)
        if not handler_cls:
            raise ValueError(f"Unsupported file format '{format_name}'. Supported formats: {list(cls._HANDLERS.keys())}")
        return handler_cls(options or {})

    @classmethod
    def detect_format_from_filename(cls, filename: str) -> str:
        """Guesses format based on file extension."""
        lower = filename.lower()
        # Strip compression extension if present
        for comp_ext in (".gz", ".bz2", ".zst", ".snappy"):
            if lower.endswith(comp_ext):
                lower = lower[:-len(comp_ext)]
                break

        _, ext = os.path.splitext(lower)
        ext = ext.lstrip(".")
        if ext in cls._HANDLERS:
            return "jsonl" if ext in ("jsonl", "ndjson") else ext
        return "csv"

    @classmethod
    def detect_format_from_bytes(cls, sample_bytes: bytes) -> str:
        """Detects format from magic bytes or leading tokens."""
        if not sample_bytes:
            return "csv"

        if sample_bytes.startswith(b"PAR1") or sample_bytes.endswith(b"PAR1"):
            return "parquet"
        if sample_bytes.startswith(b"Obj\x01"):
            return "avro"
        if sample_bytes.startswith(b"ORC"):
            return "orc"
        if sample_bytes.startswith(b"PK\x03\x04"):
            return "xlsx"

        stripped = sample_bytes.strip()
        if stripped.startswith(b"["):
            return "json"
        if stripped.startswith(b"{"):
            # Check if second line also starts with { -> jsonl
            lines = stripped.split(b"\n", 2)
            if len(lines) > 1 and lines[1].strip().startswith(b"{"):
                return "jsonl"
            return "json"

        return "csv"
