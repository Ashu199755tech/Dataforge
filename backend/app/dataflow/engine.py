import time
from typing import Dict, Any, List, Optional, Tuple
import polars as pl
from sqlalchemy.orm import Session
from backend.app.models.connection import Connection
from backend.app.connectors.factory import get_connector
from backend.app.core.security import decrypt_secret


class DataFlowExecutionResult:
    def __init__(
        self,
        status: str,
        total_rows_read: int,
        total_rows_written: int,
        duration_seconds: float,
        sink_metrics: Dict[str, Any],
        node_outputs: Dict[str, Any],
        error_message: Optional[str] = None
    ):
        self.status = status
        self.total_rows_read = total_rows_read
        self.total_rows_written = total_rows_written
        self.duration_seconds = duration_seconds
        self.sink_metrics = sink_metrics
        self.node_outputs = node_outputs
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "total_rows_read": self.total_rows_read,
            "total_rows_written": self.total_rows_written,
            "duration_seconds": self.duration_seconds,
            "sink_metrics": self.sink_metrics,
            "node_outputs": self.node_outputs,
            "error_message": self.error_message
        }


class DataFlowEngine:
    """
    High-performance Vectorized Data Flow Transformation Engine.
    Executes mapping transformation DAGs using Polars with full multi-threading
    and memory-efficient columnar operators.
    """

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.streams: Dict[str, pl.DataFrame] = {}
        self.node_previews: Dict[str, Dict[str, Any]] = {}
        self.sink_metrics: Dict[str, Dict[str, Any]] = {}

    def _resolve_connector(self, connection_id: str):
        if not self.db:
            raise ValueError("Database session required to resolve connection credentials.")
        conn_record = self.db.query(Connection).filter(Connection.id == connection_id).first()
        if not conn_record:
            raise ValueError(f"Connection with ID '{connection_id}' not found.")
        decrypted_config = decrypt_secret(conn_record.config_encrypted)
        return get_connector(conn_record.connector_type, decrypted_config)

    def execute_graph(self, graph_json: Dict[str, Any], limit_preview: Optional[int] = None) -> DataFlowExecutionResult:
        start_time = time.time()
        nodes = graph_json.get("nodes", [])
        edges = graph_json.get("edges", [])

        if not nodes:
            return DataFlowExecutionResult(
                status="Succeeded",
                total_rows_read=0,
                total_rows_written=0,
                duration_seconds=0.0,
                sink_metrics={},
                node_outputs={}
            )

        # Build adjacency graph
        in_degrees: Dict[str, int] = {n["id"]: 0 for n in nodes}
        adj_list: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
        incoming_edges: Dict[str, List[Dict[str, Any]]] = {n["id"]: [] for n in nodes}

        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            if tgt in in_degrees:
                in_degrees[tgt] += 1
                adj_list[src].append(tgt)
                incoming_edges[tgt].append(edge)

        # Topological Sort
        queue = [n_id for n_id, deg in in_degrees.items() if deg == 0]
        exec_order = []

        while queue:
            curr = queue.pop(0)
            exec_order.append(curr)
            for neighbor in adj_list.get(curr, []):
                in_degrees[neighbor] -= 1
                if in_degrees[neighbor] == 0:
                    queue.append(neighbor)

        if len(exec_order) < len(nodes):
            raise ValueError("Cycle detected in Data Flow transformation graph.")

        nodes_by_id = {n["id"]: n for n in nodes}
        total_rows_read = 0
        total_rows_written = 0

        try:
            for node_id in exec_order:
                node = nodes_by_id[node_id]
                node_type = (
                    node.get("data", {}).get("operatorType")
                    or node.get("data", {}).get("operator")
                    or node.get("type")
                    or ""
                ).strip()
                node_config = node.get("data", {}).get("config", {})
                parent_edges = incoming_edges.get(node_id, [])

                # Execute specific operator
                df_out = self._execute_operator(node_id, node_type, node_config, parent_edges)

                if df_out is not None:
                    self.streams[node_id] = df_out

                    if node_type.lower() == "source":
                        total_rows_read += len(df_out)
                    elif node_type.lower() == "sink":
                        total_rows_written += len(df_out)

                    # Store preview metadata
                    sample_size = limit_preview or 100
                    schema_dict = [{"name": col, "type": str(dtype)} for col, dtype in zip(df_out.columns, df_out.dtypes)]
                    sample_rows = df_out.head(sample_size).to_dicts()

                    self.node_previews[node_id] = {
                        "node_id": node_id,
                        "operator": node_type,
                        "row_count": len(df_out),
                        "columns": df_out.columns,
                        "schema": schema_dict,
                        "preview_rows": sample_rows
                    }

            duration = round(time.time() - start_time, 2)
            return DataFlowExecutionResult(
                status="Succeeded",
                total_rows_read=total_rows_read,
                total_rows_written=total_rows_written,
                duration_seconds=duration,
                sink_metrics=self.sink_metrics,
                node_outputs=self.node_previews
            )

        except Exception as e:
            duration = round(time.time() - start_time, 2)
            return DataFlowExecutionResult(
                status="Failed",
                total_rows_read=total_rows_read,
                total_rows_written=total_rows_written,
                duration_seconds=duration,
                sink_metrics=self.sink_metrics,
                node_outputs=self.node_previews,
                error_message=str(e)
            )

    def _execute_operator(
        self,
        node_id: str,
        op_type: str,
        config: Dict[str, Any],
        incoming_edges: List[Dict[str, Any]]
    ) -> Optional[pl.DataFrame]:
        op_lower = op_type.lower()

        # 1. SOURCE
        if op_lower == "source":
            return self._op_source(config)

        # Retrieve primary incoming stream
        if not incoming_edges:
            raise ValueError(f"Operator '{op_type}' ({node_id}) requires at least one input stream.")

        primary_parent = incoming_edges[0]["source"]
        df_in = self.streams.get(primary_parent)
        if df_in is None:
            raise ValueError(f"Input stream from parent '{primary_parent}' is not available.")

        # 2. SINK
        if op_lower == "sink":
            return self._op_sink(node_id, df_in, config)

        # 3. SELECT (Project, rename, drop)
        elif op_lower == "select":
            return self._op_select(df_in, config)

        # 4. FILTER
        elif op_lower == "filter":
            return self._op_filter(df_in, config)

        # 5. DERIVED COLUMN
        elif op_lower in ("derivedcolumn", "derived_column"):
            return self._op_derived_column(df_in, config)

        # 6. SORT
        elif op_lower == "sort":
            return self._op_sort(df_in, config)

        # 7. AGGREGATE
        elif op_lower == "aggregate":
            return self._op_aggregate(df_in, config)

        # 8. JOIN
        elif op_lower == "join":
            return self._op_join(node_id, incoming_edges, config)

        # 9. UNION
        elif op_lower == "union":
            return self._op_union(node_id, incoming_edges)

        # 10. SURROGATE KEY
        elif op_lower in ("surrogatekey", "surrogate_key"):
            return self._op_surrogate_key(df_in, config)

        # 11. WINDOW
        elif op_lower == "window":
            return self._op_window(df_in, config)

        # 12. CONDITIONAL SPLIT
        elif op_lower in ("conditionalsplit", "conditional_split"):
            return self._op_conditional_split(df_in, config)

        # 13. LOOKUP
        elif op_lower == "lookup":
            return self._op_lookup(incoming_edges, config)

        # 14. FLATTEN
        elif op_lower in ("flatten", "unnest"):
            return self._op_flatten(df_in, config)

        # 15. PARSE
        elif op_lower in ("parse", "parse_json"):
            return self._op_parse(df_in, config)

        # 16. CAST
        elif op_lower == "cast":
            return self._op_cast(df_in, config)

        else:
            # Pass-through if unrecognized operator
            return df_in

    def _op_source(self, config: Dict[str, Any]) -> pl.DataFrame:
        connection_id = config.get("connection_id")
        table_name = config.get("table_name") or config.get("dataset_name")
        raw_data = config.get("inline_data")
        file_path = config.get("file_path") or config.get("path")

        # Inline mock/sample data
        if raw_data:
            return pl.DataFrame(raw_data)

        # File-based source (Parquet, CSV, JSON)
        if file_path:
            import os
            fmt = (config.get("format") or os.path.splitext(file_path)[1].lstrip(".") or "parquet").lower()
            if fmt == "csv":
                return pl.read_csv(file_path)
            elif fmt == "json":
                return pl.read_json(file_path)
            else:
                return pl.read_parquet(file_path)

        if not connection_id or not table_name:
            raise ValueError("Source operator requires 'connection_id' and 'table_name', or 'file_path'.")

        connector = self._resolve_connector(connection_id)
        records = []
        for batch in connector.read_data_stream(table_name, batch_size=50000):
            records.extend(batch)

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records)

    def _op_sink(self, node_id: str, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        connection_id = config.get("connection_id")
        table_name = config.get("table_name") or config.get("dataset_name")
        file_path = config.get("file_path") or config.get("path")
        write_mode = config.get("write_mode", "append").lower()

        if file_path:
            import os
            fmt = (config.get("format") or os.path.splitext(file_path)[1].lstrip(".") or "parquet").lower()
            if fmt == "csv":
                df.write_csv(file_path)
            elif fmt == "json":
                df.write_json(file_path)
            else:
                df.write_parquet(file_path)
            written = len(df)
        elif connection_id and table_name:
            connector = self._resolve_connector(connection_id)
            records = df.to_dicts()
            written = connector.write_data_batch(table_name, records, write_mode=write_mode)
        else:
            written = len(df)

        self.sink_metrics[node_id] = {
            "table_name": table_name,
            "rows_written": written,
            "columns_count": len(df.columns)
        }
        return df

    def _op_select(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        rename_map = config.get("rename_columns", {})
        drop_cols = config.get("drop_columns", [])
        keep_cols = config.get("columns", [])

        out_df = df
        if drop_cols:
            out_df = out_df.drop([c for c in drop_cols if c in out_df.columns])

        if keep_cols:
            valid_keep = [c for c in keep_cols if c in out_df.columns]
            if valid_keep:
                out_df = out_df.select(valid_keep)

        if rename_map:
            valid_rename = {k: v for k, v in rename_map.items() if k in out_df.columns}
            if valid_rename:
                out_df = out_df.rename(valid_rename)

        return out_df

    def _op_filter(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        col_name = config.get("column")
        operator = (config.get("operator") or "==").strip()
        val = config.get("value")

        cond = config.get("condition") or config.get("filter_expression")
        if not col_name and cond:
            import re
            m = re.match(r"^\s*([a-zA-Z0-9_]+)\s*(=|==|!=|<>|>=|<=|>|<)\s*(.+?)\s*$", cond)
            if m:
                col_name = m.group(1)
                operator = m.group(2)
                raw_val = m.group(3).strip()
                if (raw_val.startswith("'") and raw_val.endswith("'")) or (raw_val.startswith('"') and raw_val.endswith('"')):
                    val = raw_val[1:-1]
                elif raw_val.lower() == "true":
                    val = True
                elif raw_val.lower() == "false":
                    val = False
                else:
                    try:
                        val = int(raw_val) if "." not in raw_val else float(raw_val)
                    except ValueError:
                        val = raw_val

        if not col_name or col_name not in df.columns:
            return df

        if operator in ("==", "equals", "="):
            return df.filter(pl.col(col_name) == val)
        elif operator in ("!=", "<>", "not_equals"):
            return df.filter(pl.col(col_name) != val)
        elif operator in (">", "greater"):
            return df.filter(pl.col(col_name) > val)
        elif operator in (">=", "greater_equals"):
            return df.filter(pl.col(col_name) >= val)
        elif operator in ("<", "less"):
            return df.filter(pl.col(col_name) < val)
        elif operator in ("<=", "less_equals"):
            return df.filter(pl.col(col_name) <= val)
        elif operator in ("contains", "like"):
            return df.filter(pl.col(col_name).cast(pl.Utf8).str.contains(str(val)))
        elif operator in ("is_null", "null"):
            return df.filter(pl.col(col_name).is_null())
        elif operator in ("is_not_null", "not_null"):
            return df.filter(pl.col(col_name).is_not_null())
        return df

    def _op_derived_column(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        columns_config = config.get("derived_columns", [])
        # Each item: {"column_name": "total", "expression": "col('price') * col('qty')"}
        # Or simple config: {"column_name": "full_name", "type": "concat", "inputs": ["first", "last"]}
        out_df = df
        for d in columns_config:
            name = d.get("column_name")
            expr_type = d.get("type", "literal")

            if not name:
                continue

            if expr_type == "literal":
                out_df = out_df.with_columns(pl.lit(d.get("value")).alias(name))
            elif expr_type == "concat":
                inputs = d.get("inputs", [])
                sep = d.get("separator", " ")
                valid_inputs = [pl.col(c).cast(pl.Utf8) for c in inputs if c in out_df.columns]
                if valid_inputs:
                    out_df = out_df.with_columns(pl.concat_str(valid_inputs, separator=sep).alias(name))
            elif expr_type == "multiply":
                c1, c2 = d.get("col1"), d.get("col2")
                if c1 in out_df.columns and c2 in out_df.columns:
                    out_df = out_df.with_columns((pl.col(c1) * pl.col(c2)).alias(name))
            elif expr_type == "add":
                c1, c2 = d.get("col1"), d.get("col2")
                if c1 in out_df.columns and c2 in out_df.columns:
                    out_df = out_df.with_columns((pl.col(c1) + pl.col(c2)).alias(name))
            elif expr_type == "uppercase":
                col = d.get("input_column")
                if col in out_df.columns:
                    out_df = out_df.with_columns(pl.col(col).cast(pl.Utf8).str.to_uppercase().alias(name))
            elif expr_type == "lowercase":
                col = d.get("input_column")
                if col in out_df.columns:
                    out_df = out_df.with_columns(pl.col(col).cast(pl.Utf8).str.to_lowercase().alias(name))
        return out_df

    def _op_sort(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        sort_by = config.get("columns", [])
        descending = config.get("descending", False)

        if isinstance(sort_by, str):
            sort_by = [sort_by]

        valid_sort = [c for c in sort_by if c in df.columns]
        if valid_sort:
            return df.sort(by=valid_sort, descending=descending)
        return df

    def _op_aggregate(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        group_by_cols = config.get("group_by", [])
        aggs_config = config.get("aggregates", [])

        if isinstance(group_by_cols, str):
            group_by_cols = [group_by_cols]

        valid_group = [c for c in group_by_cols if c in df.columns]

        agg_exprs = []
        for a in aggs_config:
            fn = a.get("function", "count").lower()
            col = a.get("column")
            alias = a.get("alias") or f"{fn}_{col}"

            if fn == "count":
                if col and col in df.columns:
                    agg_exprs.append(pl.col(col).count().alias(alias))
                else:
                    agg_exprs.append(pl.len().alias(alias))
            elif fn == "sum" and col in df.columns:
                agg_exprs.append(pl.col(col).sum().alias(alias))
            elif fn == "avg" and col in df.columns:
                agg_exprs.append(pl.col(col).mean().alias(alias))
            elif fn == "min" and col in df.columns:
                agg_exprs.append(pl.col(col).min().alias(alias))
            elif fn == "max" and col in df.columns:
                agg_exprs.append(pl.col(col).max().alias(alias))

        if not agg_exprs:
            agg_exprs = [pl.len().alias("count")]

        if valid_group:
            return df.group_by(valid_group).agg(agg_exprs)
        else:
            return df.select(agg_exprs)

    def _op_join(self, node_id: str, incoming_edges: List[Dict[str, Any]], config: Dict[str, Any]) -> pl.DataFrame:
        if len(incoming_edges) < 2:
            raise ValueError(f"Join operator '{node_id}' requires at least 2 input streams (left and right).")

        left_node_id = incoming_edges[0]["source"]
        right_node_id = incoming_edges[1]["source"]

        left_df = self.streams.get(left_node_id)
        right_df = self.streams.get(right_node_id)

        if left_df is None or right_df is None:
            raise ValueError("Join input streams must be computed before join operation.")

        join_type = config.get("join_type", "inner").lower()
        left_on = config.get("left_on")
        right_on = config.get("right_on") or left_on

        if not left_on or not right_on:
            raise ValueError("Join requires 'left_on' and 'right_on' keys.")

        how = "inner"
        if join_type in ("left", "left_outer"):
            how = "left"
        elif join_type in ("full", "outer", "full_outer"):
            how = "full"
        elif join_type == "cross":
            how = "cross"

        if how == "cross":
            return left_df.join(right_df, how="cross")
        else:
            return left_df.join(right_df, left_on=left_on, right_on=right_on, how=how)

    def _op_union(self, node_id: str, incoming_edges: List[Dict[str, Any]]) -> pl.DataFrame:
        dfs = []
        for e in incoming_edges:
            df_parent = self.streams.get(e["source"])
            if df_parent is not None:
                dfs.append(df_parent)

        if not dfs:
            return pl.DataFrame()

        return pl.concat(dfs, how="diagonal")

    def _op_surrogate_key(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        key_name = config.get("key_name", "surrogate_key")
        start_value = int(config.get("start_value", 1))
        # Monotonically increasing index series
        return df.with_columns((pl.int_range(start_value, start_value + len(df))).alias(key_name))

    def _op_window(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        partition_by = config.get("partition_by", [])
        order_by = config.get("order_by")
        func = config.get("function", "row_number").lower()
        target_col = config.get("target_column", "window_rank")

        if isinstance(partition_by, str):
            partition_by = [partition_by]

        valid_part = [c for c in partition_by if c in df.columns]

        if func == "row_number":
            if order_by and order_by in df.columns:
                return df.with_columns(
                    pl.col(order_by).cum_count().over(valid_part).alias(target_col) if valid_part else
                    pl.col(order_by).cum_count().alias(target_col)
                )
            else:
                return df.with_columns(pl.int_range(1, len(df) + 1).alias(target_col))
        elif func == "rank" and order_by and order_by in df.columns:
            return df.with_columns(
                pl.col(order_by).rank("dense").over(valid_part).alias(target_col) if valid_part else
                pl.col(order_by).rank("dense").alias(target_col)
            )
        return df

    def _op_conditional_split(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        # Returns primary matching subset
        condition_col = config.get("column")
        val = config.get("value")
        if condition_col and condition_col in df.columns and val is not None:
            return df.filter(pl.col(condition_col) == val)
        return df

    def _op_lookup(self, incoming_edges: List[Dict[str, Any]], config: Dict[str, Any]) -> pl.DataFrame:
        if len(incoming_edges) < 2:
            return self.streams.get(incoming_edges[0]["source"], pl.DataFrame())

        primary_df = self.streams.get(incoming_edges[0]["source"])
        lookup_df = self.streams.get(incoming_edges[1]["source"])

        key = config.get("key") or config.get("left_on")
        if primary_df is not None and lookup_df is not None and key in primary_df.columns and key in lookup_df.columns:
            return primary_df.join(lookup_df, on=key, how="left")

        return primary_df or pl.DataFrame()

    def _op_flatten(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        import json
        col_name = config.get("column")
        prefix = config.get("prefix", "")
        if not col_name or col_name not in df.columns:
            return df

        records = df.to_dicts()
        new_records = []
        for r in records:
            val = r.get(col_name)
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    pass
            base_row = {k: v for k, v in r.items() if k != col_name}
            if isinstance(val, dict):
                for k, v in val.items():
                    base_row[f"{prefix}{k}"] = v
                new_records.append(base_row)
            elif isinstance(val, list):
                if not val:
                    new_records.append(base_row)
                else:
                    for item in val:
                        row_copy = base_row.copy()
                        if isinstance(item, dict):
                            for k, v in item.items():
                                row_copy[f"{prefix}{k}"] = v
                        else:
                            row_copy[f"{prefix}value"] = item
                        new_records.append(row_copy)
            else:
                base_row[col_name] = val
                new_records.append(base_row)

        return pl.DataFrame(new_records) if new_records else df

    def _op_parse(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        import json
        col_name = config.get("column")
        target_col = config.get("target_column") or col_name
        records = df.to_dicts()
        for r in records:
            if col_name in r and isinstance(r[col_name], str):
                try:
                    r[target_col] = json.loads(r[col_name])
                except Exception:
                    pass
        return pl.DataFrame(records) if records else df

    def _op_cast(self, df: pl.DataFrame, config: Dict[str, Any]) -> pl.DataFrame:
        casts = config.get("columns", {})
        out_df = df
        for col, dtype in casts.items():
            if col in out_df.columns:
                dt_lower = str(dtype).lower()
                if dt_lower in ("int", "integer", "bigint"):
                    out_df = out_df.with_columns(pl.col(col).cast(pl.Int64, strict=False))
                elif dt_lower in ("float", "numeric", "double"):
                    out_df = out_df.with_columns(pl.col(col).cast(pl.Float64, strict=False))
                elif dt_lower in ("str", "string", "text", "utf8"):
                    out_df = out_df.with_columns(pl.col(col).cast(pl.Utf8, strict=False))
                elif dt_lower in ("bool", "boolean"):
                    out_df = out_df.with_columns(pl.col(col).cast(pl.Boolean, strict=False))
        return out_df

