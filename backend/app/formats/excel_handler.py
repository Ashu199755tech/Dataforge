from typing import Dict, Any, Iterator, Optional, List, BinaryIO
import io

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    openpyxl = None
    HAS_OPENPYXL = False

from backend.app.formats.base import BaseFormatReader, BaseFormatWriter
from backend.app.formats.models import SchemaDefinition, ColumnSchema, DataType


class ExcelFormatHandler(BaseFormatReader, BaseFormatWriter):
    """
    Microsoft Excel (.xlsx) format handler using openpyxl.
    Employs read_only=True and write_only=True streaming modes
    to eliminate unbounded memory consumption on large spreadsheets.
    """

    def read_records(
        self,
        stream: BinaryIO,
        limit: Optional[int] = None,
        columns: Optional[List[str]] = None
    ) -> Iterator[Dict[str, Any]]:
        # openpyxl requires seekable stream
        if not hasattr(stream, "seek"):
            stream = io.BytesIO(stream.read())

        sheet_name = self.options.get("sheet_name")
        has_header = self.options.get("has_header", True)

        wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
        try:
            ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

            rows_iter = ws.iter_rows(values_only=True)
            header = None
            if has_header:
                header_row = next(rows_iter, None)
                if header_row:
                    header = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(header_row)]

            count = 0
            for row in rows_iter:
                if not any(c is not None for c in row):
                    continue
                if not header:
                    header = [f"col_{i}" for i in range(len(row))]

                record = {}
                for idx, col_name in enumerate(header):
                    if idx < len(row):
                        if columns and col_name not in columns:
                            continue
                        record[col_name] = row[idx]

                yield record
                count += 1
                if limit and count >= limit:
                    break
        finally:
            wb.close()

    def infer_schema(self, stream: BinaryIO, max_records: int = 100) -> SchemaDefinition:
        start_pos = stream.tell() if hasattr(stream, "tell") else 0
        if not hasattr(stream, "seek"):
            stream = io.BytesIO(stream.read())

        sheet_name = self.options.get("sheet_name")
        has_header = self.options.get("has_header", True)

        wb = openpyxl.load_workbook(stream, read_only=True, data_only=True)
        columns = []
        sample_count = 0
        try:
            ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
            rows_iter = ws.iter_rows(values_only=True)

            header = None
            if has_header:
                header_row = next(rows_iter, None)
                if header_row:
                    header = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(header_row)]

            sample_rows = []
            for _ in range(max_records):
                row = next(rows_iter, None)
                if row is None:
                    break
                if any(c is not None for c in row):
                    sample_rows.append(row)

            if not header and sample_rows:
                header = [f"col_{i}" for i in range(len(sample_rows[0]))]
            elif not header:
                return SchemaDefinition(columns=[])

            for idx, col_name in enumerate(header):
                detected_type = DataType.STRING.value
                non_null_samples = [r[idx] for r in sample_rows if idx < len(r) and r[idx] is not None]
                if non_null_samples:
                    first_val = non_null_samples[0]
                    if isinstance(first_val, bool):
                        detected_type = DataType.BOOLEAN.value
                    elif isinstance(first_val, int):
                        detected_type = DataType.INTEGER.value
                    elif isinstance(first_val, float):
                        detected_type = DataType.DOUBLE.value
                    elif hasattr(first_val, "isoformat"):
                        detected_type = DataType.TIMESTAMP.value

                columns.append(ColumnSchema(name=col_name, data_type=detected_type, nullable=True))

            sample_count = len(sample_rows)
        finally:
            wb.close()
            if hasattr(stream, "seek"):
                stream.seek(start_pos)

        return SchemaDefinition(columns=columns, record_count=sample_count)

    def write_records(
        self,
        records: Iterator[Dict[str, Any]],
        target_stream: BinaryIO,
        schema: Optional[SchemaDefinition] = None
    ) -> int:
        start_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet(title=self.options.get("sheet_name", "Sheet1"))

        headers = schema.column_names() if schema else None
        header_written = False

        for record in records:
            if not headers:
                headers = list(record.keys())
            if not header_written:
                ws.append(headers)
                header_written = True

            row = [record.get(k) for k in headers]
            ws.append(row)

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()

        val = buf.getvalue()
        target_stream.write(val)
        target_stream.flush()

        end_pos = target_stream.tell() if hasattr(target_stream, "tell") else 0
        return max(0, end_pos - start_pos)
