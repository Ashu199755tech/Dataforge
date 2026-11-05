import io
import gzip
import bz2
from typing import Dict, Any, Iterator, Optional, List, BinaryIO

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.models import SchemaDefinition, ColumnSchema, DataType


class TextFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    Plain text line-by-line format handler.
    Yields records with schema `{"line_no": int, "text": str}`.
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
        text_column = self.options.get("text_column", "text")

        text_stream = io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace")
        count = 0
        try:
            for idx, line in enumerate(text_stream, 1):
                clean_line = line.rstrip("\r\n")
                record = {"line_no": idx, text_column: clean_line}
                if columns:
                    record = {k: v for k, v in record.items() if k in columns}
                yield record
                count += 1
                if limit and count >= limit:
                    break
        finally:
            text_stream.detach()

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        text_column = self.options.get("text_column", "text")
        columns = [
            ColumnSchema(name="line_no", data_type=DataType.INTEGER.value, nullable=False),
            ColumnSchema(name=text_column, data_type=DataType.STRING.value, nullable=True)
        ]
        return SchemaDefinition(columns=columns)

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        compression = self.options.get("compression", "none").lower()
        encoding = self.options.get("encoding", "utf-8")
        text_column = self.options.get("text_column", "text")

        out_stream = target_stream
        if compression in ("gzip", "gz"):
            out_stream = gzip.GzipFile(fileobj=target_stream, mode="wb")
        elif compression in ("bz2", "bzip2"):
            out_stream = bz2.BZ2File(target_stream, mode="wb")

        for record in records:
            text = record.get(text_column, "")
            line = f"{text}\n"
            out_stream.write(line.encode(encoding))

        out_stream.flush()
        if out_stream != target_stream and hasattr(out_stream, "close"):
            out_stream.close()

        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)
