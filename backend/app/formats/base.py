from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, Optional, List, BinaryIO
import io
import pyarrow as pa
from backend.app.formats.models import SchemaDefinition, ColumnSchema, PreviewResult, DataType


class BaseFormatReader(ABC):
    """
    Abstract format reader for high-throughput streaming deserialization,
    schema discovery, and low-memory head previews.
    """

    def __init__(self, options: Optional[Dict[str, Any]] = None):
        self.options = options or {}

    @abstractmethod
    def read_records(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        """Yields records as Python dictionaries in streaming chunks."""
        pass

    def read_arrow_table(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> pa.Table:
        """Reads stream into an Apache Arrow Table. Subclasses can override for native Arrow speed."""
        records = list(self.read_records(stream, limit=limit, columns=columns))
        if not records:
            return pa.Table.from_arrays([], names=[])
        return pa.Table.from_pylist(records)

    @abstractmethod
    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        """Discovers or samples schema structure without loading full file."""
        pass

    def preview(self, stream: BinaryIO, limit: int = 50) -> PreviewResult:
        """Generates a bounded preview of the first N rows and schema."""
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        schema = self.infer_schema(stream, max_records=limit)
        
        # Reset stream position if seekable
        if hasattr(stream, "seek"):
            stream.seek(start_pos)

        rows = []
        sampled_bytes = 0
        for row in self.read_records(stream, limit=limit):
            rows.append(row)
            if len(rows) >= limit:
                break

        end_pos = stream.tell() if hasattr(stream, "tell") else 0
        sampled_bytes = max(0, end_pos - start_pos)

        return PreviewResult(
            columns=schema.columns,
            rows=rows,
            sample_row_count=len(rows),
            format_detected=self.__class__.__name__.replace("Handler", "").replace("Format", "").lower(),
            total_bytes_sampled=sampled_bytes,
            truncated=len(rows) >= limit
        )


class BaseFormatWriter(ABC):
    """
    Abstract format writer for high-performance chunked serialization,
    Arrow buffer conversions, and compressed file generation.
    """

    def __init__(self, options: Optional[Dict[str, Any]] = None):
        self.options = options or {}

    @abstractmethod
    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        """
        Serializes record iterator into target binary stream.
        Returns total number of bytes written.
        """
        pass

    def write_arrow_table(
        self,
        table: pa.Table,
        target_stream: BinaryIO
    ) -> int:
        """Writes an Apache Arrow Table to binary target. Can be overridden for native writers."""
        records = iter(table.to_pylist())
        return self.write_records(records, target_stream)
