import pyarrow as pa
from typing import Dict, Any, List, Iterator, Optional, Tuple


class ArrowRecordBatchTransformer:
    """
    High-performance Arrow RecordBatch transformer.
    Applies column projections, renames, and exclusions directly on
    Arrow columnar arrays with zero Python dictionary serialization overhead.
    """

    def __init__(self, column_mappings: Optional[List[Dict[str, Any]]] = None):
        self.mappings = column_mappings or []
        self._has_mappings = bool(self.mappings and len(self.mappings) > 0)

    def transform_batch(self, batch: pa.RecordBatch) -> pa.RecordBatch:
        """Applies column mappings to an Apache Arrow RecordBatch."""
        if not self._has_mappings:
            return batch

        schema = batch.schema
        new_columns = []
        new_names = []

        for m in self.mappings:
            if m.get("exclude"):
                continue

            src_col = m.get("source_column")
            dst_col = m.get("destination_column") or src_col

            if src_col in schema.names:
                idx = schema.get_field_index(src_col)
                array = batch.column(idx)

                # Optional type casting if specified
                target_type = m.get("target_type")
                if target_type:
                    pa_type = self._resolve_target_type(target_type)
                    if pa_type:
                        try:
                            array = array.cast(pa_type)
                        except Exception:
                            pass

                new_columns.append(array)
                new_names.append(dst_col)

        if not new_columns:
            return batch

        return pa.RecordBatch.from_arrays(new_columns, names=new_names)

    def transform_dict_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback row-level dictionary transformer for non-Arrow row streams."""
        if not self._has_mappings or not records:
            return records

        transformed = []
        for rec in records:
            mapped_rec = {}
            for m in self.mappings:
                if m.get("exclude"):
                    continue
                src_col = m.get("source_column")
                dst_col = m.get("destination_column") or src_col
                if src_col in rec:
                    mapped_rec[dst_col] = rec[src_col]
            transformed.append(mapped_rec)
        return transformed

    @staticmethod
    def _resolve_target_type(type_name: str) -> Optional[pa.DataType]:
        t = (type_name or "").lower().strip()
        if t in ("string", "str", "varchar", "text"):
            return pa.string()
        elif t in ("int", "integer", "int32"):
            return pa.int32()
        elif t in ("bigint", "int64", "long"):
            return pa.int64()
        elif t in ("float", "float32"):
            return pa.float32()
        elif t in ("double", "float64"):
            return pa.float64()
        elif t in ("bool", "boolean"):
            return pa.bool_()
        elif t in ("date",):
            return pa.date32()
        elif t in ("timestamp", "datetime"):
            return pa.timestamp("ms")
        return None


def dict_records_to_record_batch(records: List[Dict[str, Any]]) -> Optional[pa.RecordBatch]:
    """Converts a chunk of dictionary records into an Apache Arrow RecordBatch."""
    if not records:
        return None
    table = pa.Table.from_pylist(records)
    batches = table.to_batches()
    return batches[0] if batches else None


def record_batch_to_dict_records(batch: pa.RecordBatch) -> List[Dict[str, Any]]:
    """Converts an Apache Arrow RecordBatch into a list of row dictionaries."""
    return batch.to_pylist()
