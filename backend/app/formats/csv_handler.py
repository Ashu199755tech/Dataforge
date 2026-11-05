import csv
import io
import gzip
import bz2
from typing import Dict, Any, Iterator, Optional, List, BinaryIO
import pyarrow as pa
import pyarrow.csv as pacsv

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.models import SchemaDefinition, ColumnSchema, DataType


class CsvFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    High-performance CSV and delimited text handler.
    Supports custom delimiters, headers, quote characters, column projections,
    and automatic compression wrapping (gzip, bz2).
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
        delimiter = self.options.get("delimiter", ",")
        has_header = self.options.get("has_header", True)
        skip_rows = int(self.options.get("skip_rows", 0))

        text_stream = io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace", newline="")
        try:
            reader = csv.reader(text_stream, delimiter=delimiter)
            
            # Skip initial rows if requested
            for _ in range(skip_rows):
                next(reader, None)

            header = None
            if has_header:
                header = next(reader, None)
                if header:
                    header = [h.strip() for h in header]

            count = 0
            for row in reader:
                if not row:
                    continue
                if not header:
                    header = [f"col_{i}" for i in range(len(row))]

                record = {}
                for idx, col_name in enumerate(header):
                    if idx < len(row):
                        if columns and col_name not in columns:
                            continue
                        val = row[idx]
                        record[col_name] = val

                yield record
                count += 1
                if limit and count >= limit:
                    break
        finally:
            text_stream.detach()

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        raw_stream = self._get_decompressed_stream(stream)
        encoding = self.options.get("encoding", "utf-8")
        delimiter = self.options.get("delimiter", ",")
        has_header = self.options.get("has_header", True)
        skip_rows = int(self.options.get("skip_rows", 0))

        text_stream = io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace", newline="")
        columns = []
        try:
            reader = csv.reader(text_stream, delimiter=delimiter)
            for _ in range(skip_rows):
                next(reader, None)

            header = next(reader, None) if has_header else None
            sample_rows = []
            for _ in range(max_records):
                row = next(reader, None)
                if row is None:
                    break
                sample_rows.append(row)

            if not header and sample_rows:
                header = [f"col_{i}" for i in range(len(sample_rows[0]))]
            elif not header:
                return SchemaDefinition(columns=[])

            # Type sampling
            for idx, col_name in enumerate(header):
                detected_type = DataType.STRING.value
                non_null_samples = [r[idx].strip() for r in sample_rows if idx < len(r) and r[idx].strip()]

                if non_null_samples:
                    if all(s.lower() in ("true", "false", "1", "0") for s in non_null_samples):
                        detected_type = DataType.BOOLEAN.value
                    elif all(s.lstrip("-").isdigit() for s in non_null_samples):
                        detected_type = DataType.INTEGER.value
                    else:
                        try:
                            for s in non_null_samples:
                                float(s)
                            detected_type = DataType.DOUBLE.value
                        except ValueError:
                            detected_type = DataType.STRING.value

                columns.append(ColumnSchema(name=col_name.strip(), data_type=detected_type, nullable=True))

            return SchemaDefinition(columns=columns, record_count=len(sample_rows))
        finally:
            text_stream.detach()
            if hasattr(stream, "seek"):
                stream.seek(start_pos)

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        encoding = self.options.get("encoding", "utf-8")
        delimiter = self.options.get("delimiter", ",")
        write_header = self.options.get("has_header", True)
        compression = self.options.get("compression", "none").lower()

        out_stream = target_stream
        if compression in ("gzip", "gz"):
            out_stream = gzip.GzipFile(fileobj=target_stream, mode="wb")
        elif compression in ("bz2", "bzip2"):
            out_stream = bz2.BZ2File(target_stream, mode="wb")

        text_stream = io.TextIOWrapper(out_stream, encoding=encoding, errors="replace", newline="")
        writer = None
        headers = schema.column_names() if schema else None

        try:
            for record in records:
                if not headers:
                    headers = list(record.keys())
                if writer is None:
                    writer = csv.DictWriter(text_stream, fieldnames=headers, delimiter=delimiter)
                    if write_header:
                        writer.writeheader()

                filtered_row = {k: record.get(k, "") for k in headers}
                writer.writerow(filtered_row)

            text_stream.flush()
            if out_stream != target_stream:
                out_stream.flush()
                if hasattr(out_stream, "close"):
                    out_stream.close()
        finally:
            if not text_stream.closed:
                text_stream.detach()

        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)
