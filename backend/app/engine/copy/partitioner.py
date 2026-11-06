import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from backend.app.connectors.base import BaseConnector
from backend.app.engine.copy.models import PartitionSpec


class RangePartitioner:
    """
    Partitions numeric/integer keys into balanced, non-overlapping slices.
    Generates ANSI SQL compliant filter expressions for concurrent querying.
    """

    @classmethod
    def create_numeric_partitions(
        cls,
        column: str,
        min_val: Union[int, float],
        max_val: Union[int, float],
        num_partitions: int = 4
    ) -> List[PartitionSpec]:
        """
        Splits a numeric range [min_val, max_val] into num_partitions slices.
        Guarantees all values from min_val to max_val are covered with no gaps.
        """
        if num_partitions < 1:
            num_partitions = 1

        if min_val > max_val:
            min_val, max_val = max_val, min_val

        # Single partition case or single point range
        if num_partitions == 1 or min_val == max_val:
            expr = f'"{column}" >= {min_val} AND "{column}" <= {max_val}'
            return [
                PartitionSpec(
                    partition_id="part-00000",
                    slice_index=0,
                    total_slices=1,
                    partition_column=column,
                    range_min=min_val,
                    range_max=max_val,
                    filter_expr=expr
                )
            ]

        is_integer = isinstance(min_val, int) and isinstance(max_val, int)
        total_span = max_val - min_val

        # If number of partitions exceeds the total discrete integer span
        if is_integer and total_span + 1 < num_partitions:
            num_partitions = max(1, total_span + 1)

        step = total_span / num_partitions
        partitions: List[PartitionSpec] = []

        for i in range(num_partitions):
            part_id = f"part-{i:05d}"
            
            if is_integer:
                # Discretize integer step
                low = int(min_val + math.floor(i * step))
                if i == num_partitions - 1:
                    high = int(max_val)
                    expr = f'"{column}" >= {low} AND "{column}" <= {high}'
                else:
                    high = int(min_val + math.floor((i + 1) * step))
                    expr = f'"{column}" >= {low} AND "{column}" < {high}'
            else:
                low = min_val + (i * step)
                if i == num_partitions - 1:
                    high = max_val
                    expr = f'"{column}" >= {low:.6f} AND "{column}" <= {high:.6f}'
                else:
                    high = min_val + ((i + 1) * step)
                    expr = f'"{column}" >= {low:.6f} AND "{column}" < {high:.6f}'

            partitions.append(
                PartitionSpec(
                    partition_id=part_id,
                    slice_index=i,
                    total_slices=num_partitions,
                    partition_column=column,
                    range_min=low,
                    range_max=high,
                    filter_expr=expr
                )
            )

        return partitions

    @classmethod
    def auto_probe_and_partition(
        cls,
        connector: BaseConnector,
        table_name: str,
        column: str,
        num_partitions: int = 4,
        schema_name: Optional[str] = None,
        base_filter: Optional[str] = None
    ) -> List[PartitionSpec]:
        """
        Executes a lightweight MIN/MAX query against the source database to
        determine boundaries dynamically, then calculates optimal partition slices.
        """
        tbl = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'
        where_sql = f" WHERE ({base_filter})" if base_filter else ""
        query = f'SELECT MIN("{column}") AS min_val, MAX("{column}") AS max_val, COUNT(*) AS row_cnt FROM {tbl}{where_sql}'

        try:
            results = connector.execute_query(query)
            if not results or not results[0]:
                return [PartitionSpec(partition_id="part-00000", slice_index=0, total_slices=1, filter_expr=base_filter)]

            row = results[0]
            min_val = row.get("min_val")
            max_val = row.get("max_val")
            row_cnt = row.get("row_cnt", 0)

            if min_val is None or max_val is None or row_cnt == 0:
                return [PartitionSpec(partition_id="part-00000", slice_index=0, total_slices=1, filter_expr=base_filter)]

            # Convert to float or int
            if isinstance(min_val, (int, float)) and isinstance(max_val, (int, float)):
                specs = cls.create_numeric_partitions(column, min_val, max_val, num_partitions)
                if base_filter:
                    for s in specs:
                        s.filter_expr = f"({base_filter}) AND ({s.filter_expr})"
                return specs
            else:
                # String or non-numeric min/max
                return [PartitionSpec(partition_id="part-00000", slice_index=0, total_slices=1, filter_expr=base_filter)]
        except Exception:
            # Fallback to single unpartitioned read if probe fails
            return [PartitionSpec(partition_id="part-00000", slice_index=0, total_slices=1, filter_expr=base_filter)]


class TemporalPartitioner:
    """
    Partitions timestamp/datetime fields into non-overlapping temporal windows.
    Supports ISO 8601 timestamps and uniform temporal intervals.
    """

    @classmethod
    def _parse_timestamp(cls, val: Union[datetime, str]) -> datetime:
        if isinstance(val, datetime):
            return val
        clean_str = val.strip().replace("Z", "+00:00")
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S.%f"
        ):
            try:
                return datetime.strptime(clean_str, fmt)
            except ValueError:
                continue
        # Fallback to fromisoformat
        return datetime.fromisoformat(clean_str)

    @classmethod
    def create_temporal_partitions(
        cls,
        column: str,
        start_time: Union[datetime, str],
        end_time: Union[datetime, str],
        num_partitions: int = 4,
        date_format: str = "%Y-%m-%d %H:%M:%S"
    ) -> List[PartitionSpec]:
        """
        Divides the temporal window [start_time, end_time] into num_partitions slices.
        """
        start_dt = cls._parse_timestamp(start_time)
        end_dt = cls._parse_timestamp(end_time)

        if start_dt > end_dt:
            start_dt, end_dt = end_dt, start_dt

        if num_partitions < 1:
            num_partitions = 1

        total_seconds = max(0.0, (end_dt - start_dt).total_seconds())

        if num_partitions == 1 or total_seconds == 0:
            start_str = start_dt.strftime(date_format)
            end_str = end_dt.strftime(date_format)
            expr = f'"{column}" >= \'{start_str}\' AND "{column}" <= \'{end_str}\''
            return [
                PartitionSpec(
                    partition_id="part-00000",
                    slice_index=0,
                    total_slices=1,
                    partition_column=column,
                    range_min=start_str,
                    range_max=end_str,
                    filter_expr=expr
                )
            ]

        step_seconds = total_seconds / num_partitions
        partitions: List[PartitionSpec] = []

        for i in range(num_partitions):
            part_id = f"part-{i:05d}"
            cur_start = start_dt + timedelta(seconds=i * step_seconds)
            start_str = cur_start.strftime(date_format)

            if i == num_partitions - 1:
                cur_end = end_dt
                end_str = cur_end.strftime(date_format)
                expr = f'"{column}" >= \'{start_str}\' AND "{column}" <= \'{end_str}\''
            else:
                cur_end = start_dt + timedelta(seconds=(i + 1) * step_seconds)
                end_str = cur_end.strftime(date_format)
                expr = f'"{column}" >= \'{start_str}\' AND "{column}" < \'{end_str}\''

            partitions.append(
                PartitionSpec(
                    partition_id=part_id,
                    slice_index=i,
                    total_slices=num_partitions,
                    partition_column=column,
                    range_min=start_str,
                    range_max=end_str,
                    filter_expr=expr
                )
            )

        return partitions


class ListPartitioner:
    """
    Partitions discrete discrete values (e.g. status codes, country codes, tenant IDs)
    into balanced partition buckets using modulo distribution.
    """

    @classmethod
    def create_discrete_partitions(
        cls,
        column: str,
        values: List[Any],
        num_partitions: int = 4
    ) -> List[PartitionSpec]:
        """
        Distributes distinct categorical values across num_partitions buckets.
        """
        if not values:
            return [
                PartitionSpec(
                    partition_id="part-00000",
                    slice_index=0,
                    total_slices=1,
                    partition_column=column,
                    filter_expr=None
                )
            ]

        unique_vals = list(dict.fromkeys(values))  # Preserve insertion order deduplication
        num_partitions = min(max(1, num_partitions), len(unique_vals))

        buckets: List[List[Any]] = [[] for _ in range(num_partitions)]
        for idx, val in enumerate(unique_vals):
            buckets[idx % num_partitions].append(val)

        partitions: List[PartitionSpec] = []
        for i, bucket in enumerate(buckets):
            part_id = f"part-{i:05d}"
            
            def _format_sql_literal(v: Any) -> str:
                if isinstance(v, (int, float)):
                    return str(v)
                escaped = str(v).replace("'", "''")
                return f"'{escaped}'"

            if len(bucket) == 1:
                expr = f'"{column}" = {_format_sql_literal(bucket[0])}'
            else:
                formatted_items = ", ".join(_format_sql_literal(v) for v in bucket)
                expr = f'"{column}" IN ({formatted_items})'

            partitions.append(
                PartitionSpec(
                    partition_id=part_id,
                    slice_index=i,
                    total_slices=num_partitions,
                    partition_column=column,
                    filter_expr=expr
                )
            )

        return partitions


class StorageFilePartitioner:
    """
    Groups storage files into balanced partition batches using Longest Processing Time (LPT)
    bin packing to equalize workload distribution across parallel workers.
    """

    @classmethod
    def create_file_partitions(
        cls,
        files: List[Union[str, Tuple[str, int], Dict[str, Any]]],
        num_partitions: int = 4
    ) -> List[PartitionSpec]:
        """
        Given a list of file paths (or (path, size_bytes) tuples / storage item dicts),
        distributes them into num_partitions size-weighted buckets.
        """
        if not files:
            return []

        num_partitions = max(1, num_partitions)

        # Normalize to list of (path, size)
        normalized: List[Tuple[str, int]] = []
        for f in files:
            if isinstance(f, str):
                normalized.append((f, 1024 * 1024))  # default 1MB weight if unknown
            elif isinstance(f, tuple) and len(f) >= 2:
                normalized.append((str(f[0]), max(1, int(f[1]))))
            elif isinstance(f, dict):
                path = f.get("path") or f.get("name") or str(f)
                size = max(1, int(f.get("size") or f.get("size_bytes") or 1024 * 1024))
                normalized.append((path, size))
            elif hasattr(f, "path") and hasattr(f, "size_bytes"):
                # StorageItem model
                normalized.append((f.path, max(1, getattr(f, "size_bytes", 1024 * 1024))))
            else:
                normalized.append((str(f), 1024 * 1024))

        # If fewer files than partitions, reduce partitions to file count
        actual_partitions = min(num_partitions, len(normalized))

        # Sort files descending by size for greedy LPT bin-packing
        sorted_files = sorted(normalized, key=lambda x: x[1], reverse=True)

        # Buckets: List of (current_weight, list_of_paths)
        buckets: List[List[str]] = [[] for _ in range(actual_partitions)]
        weights: List[int] = [0 for _ in range(actual_partitions)]

        for path, size in sorted_files:
            # Find bucket with minimum current total bytes
            min_idx = weights.index(min(weights))
            buckets[min_idx].append(path)
            weights[min_idx] += size

        partitions: List[PartitionSpec] = []
        for i in range(actual_partitions):
            partitions.append(
                PartitionSpec(
                    partition_id=f"part-{i:05d}",
                    slice_index=i,
                    total_slices=actual_partitions,
                    file_items=buckets[i],
                    bytes_transferred=0,
                    status="Pending"
                )
            )

        return partitions
