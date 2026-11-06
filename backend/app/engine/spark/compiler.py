import re
from typing import Dict, Any, List, Optional, Tuple


class SparkDataFlowCompiler:
    """
    Compiles DataForge Visual Data Flow JSON graphs into distributed PySpark
    DataFrame transformations and executable PySpark scripts.
    """

    @classmethod
    def compile_to_script(
        cls,
        graph_json: Dict[str, Any],
        app_name: str = "DataForgeSparkJob",
        master: str = "local[*]"
    ) -> str:
        """
        Translates a DataForge Data Flow graph into a standalone, production-ready
        PySpark script suitable for execution or spark-submit.
        """
        nodes = graph_json.get("nodes", [])
        edges = graph_json.get("edges", [])

        if not nodes:
            return "# Empty DataForge Data Flow graph.\n"

        # 1. Build DAG topology
        in_degrees: Dict[str, int] = {n["id"]: 0 for n in nodes}
        adj_list: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
        incoming: Dict[str, List[str]] = {n["id"]: [] for n in nodes}

        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            if tgt in in_degrees:
                in_degrees[tgt] += 1
                adj_list[src].append(tgt)
                incoming[tgt].append(src)

        # 2. Topological sort
        queue = [nid for nid, deg in in_degrees.items() if deg == 0]
        exec_order: List[str] = []

        while queue:
            curr = queue.pop(0)
            exec_order.append(curr)
            for nxt in adj_list.get(curr, []):
                in_degrees[nxt] -= 1
                if in_degrees[nxt] == 0:
                    queue.append(nxt)

        if len(exec_order) < len(nodes):
            raise ValueError("Cycle detected in Data Flow transformation graph during Spark compilation.")

        nodes_by_id = {n["id"]: n for n in nodes}

        # 3. Code Generation
        code_lines: List[str] = [
            "#!/usr/bin/env python3",
            "# ====================================================================",
            f"# DataForge Spark Engine – Compiled Job: {app_name}",
            "# Generated automatically by DataForge SparkDataFlowCompiler",
            "# ====================================================================",
            "import os",
            "import sys",
            "from pyspark.sql import SparkSession",
            "from pyspark.sql import functions as F",
            "from pyspark.sql.window import Window",
            "",
            "def main():",
            "    spark = (",
            f'        SparkSession.builder.appName("{app_name}")',
            f'        .master("{master}")',
            '        .config("spark.sql.shuffle.partitions", "200")',
            "        .getOrCreate()",
            "    )",
            "    spark.sparkContext.setLogLevel('WARN')",
            ""
        ]

        for node_id in exec_order:
            node = nodes_by_id[node_id]
            data = node.get("data", {})
            op_type = (
                data.get("operatorType") or data.get("operator") or node.get("type") or ""
            ).strip().lower()
            cfg = data.get("config", {})
            parents = incoming.get(node_id, [])

            var_name = cls._sanitize_var_name(node_id)
            code_lines.append(f"    # --- Node: {node_id} ({op_type}) ---")

            if op_type == "source":
                cls._compile_source_node(code_lines, var_name, cfg)
            elif op_type == "sink":
                parent_var = cls._sanitize_var_name(parents[0]) if parents else "df_in"
                cls._compile_sink_node(code_lines, parent_var, cfg)
            elif op_type == "filter":
                parent_var = cls._sanitize_var_name(parents[0])
                cls._compile_filter_node(code_lines, var_name, parent_var, cfg)
            elif op_type == "select":
                parent_var = cls._sanitize_var_name(parents[0])
                cls._compile_select_node(code_lines, var_name, parent_var, cfg)
            elif op_type in ("derivedcolumn", "derived_column"):
                parent_var = cls._sanitize_var_name(parents[0])
                cls._compile_derived_column_node(code_lines, var_name, parent_var, cfg)
            elif op_type == "aggregate":
                parent_var = cls._sanitize_var_name(parents[0])
                cls._compile_aggregate_node(code_lines, var_name, parent_var, cfg)
            elif op_type == "join":
                cls._compile_join_node(code_lines, var_name, parents, cfg)
            elif op_type == "union":
                cls._compile_union_node(code_lines, var_name, parents)
            elif op_type == "sort":
                parent_var = cls._sanitize_var_name(parents[0])
                cls._compile_sort_node(code_lines, var_name, parent_var, cfg)
            elif op_type in ("surrogatekey", "surrogate_key"):
                parent_var = cls._sanitize_var_name(parents[0])
                key_col = cfg.get("key_column", "id")
                code_lines.append(f'    {var_name} = {parent_var}.withColumn("{key_col}", F.monotonically_increasing_id() + 1)')
            elif op_type == "window":
                parent_var = cls._sanitize_var_name(parents[0])
                cls._compile_window_node(code_lines, var_name, parent_var, cfg)
            elif op_type == "cast":
                parent_var = cls._sanitize_var_name(parents[0])
                cls._compile_cast_node(code_lines, var_name, parent_var, cfg)
            else:
                # Passthrough unknown node
                parent_var = cls._sanitize_var_name(parents[0]) if parents else "df_in"
                code_lines.append(f"    {var_name} = {parent_var}")

            code_lines.append("")

        code_lines.extend([
            "    print('[DataForge Spark Engine] Pipeline execution completed successfully.')",
            "    spark.stop()",
            "",
            "if __name__ == '__main__':",
            "    main()"
        ])

        return "\n".join(code_lines) + "\n"

    @classmethod
    def compile_to_plan(cls, graph_json: Dict[str, Any]) -> Dict[str, Any]:
        """Returns structured plan representation of the compiled Spark job."""
        nodes = graph_json.get("nodes", [])
        script = cls.compile_to_script(graph_json)
        sources = [n["id"] for n in nodes if (n.get("data", {}).get("operatorType") or "").lower() == "source"]
        sinks = [n["id"] for n in nodes if (n.get("data", {}).get("operatorType") or "").lower() == "sink"]

        return {
            "total_nodes": len(nodes),
            "sources": sources,
            "sinks": sinks,
            "script": script
        }

    # ------------------------------------------------------------------
    # Node Translators
    # ------------------------------------------------------------------

    @classmethod
    def _sanitize_var_name(cls, node_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", node_id)
        return f"df_{clean}"

    @classmethod
    def _compile_source_node(cls, lines: List[str], var: str, cfg: Dict[str, Any]):
        fmt = (cfg.get("format") or "parquet").lower()
        path = cfg.get("path") or cfg.get("file_path") or cfg.get("table_name") or "data"

        if fmt in ("parquet", "delta", "orc"):
            lines.append(f'    {var} = spark.read.format("{fmt}").load("{path}")')
        elif fmt == "csv":
            delim = cfg.get("delimiter", ",")
            header = "true" if cfg.get("has_header", True) else "false"
            lines.append(
                f'    {var} = spark.read.format("csv")'
                f'.option("header", "{header}")'
                f'.option("sep", "{delim}")'
                f'.option("inferSchema", "true")'
                f'.load("{path}")'
            )
        elif fmt == "json":
            lines.append(f'    {var} = spark.read.format("json").load("{path}")')
        else:
            lines.append(f'    {var} = spark.read.format("{fmt}").load("{path}")')

    @classmethod
    def _compile_sink_node(cls, lines: List[str], parent_var: str, cfg: Dict[str, Any]):
        fmt = (cfg.get("format") or "parquet").lower()
        path = cfg.get("path") or cfg.get("file_path") or cfg.get("table_name") or "output_data"
        mode = cfg.get("write_mode") or cfg.get("mode") or "overwrite"
        lines.append(f'    {parent_var}.write.format("{fmt}").mode("{mode}").save("{path}")')

    @classmethod
    def _compile_filter_node(cls, lines: List[str], var: str, parent_var: str, cfg: Dict[str, Any]):
        cond = cfg.get("condition") or cfg.get("filter_expression") or "1 = 1"
        escaped = cond.replace('"', '\\"')
        lines.append(f'    {var} = {parent_var}.filter("{escaped}")')

    @classmethod
    def _compile_select_node(cls, lines: List[str], var: str, parent_var: str, cfg: Dict[str, Any]):
        cols = cfg.get("columns") or cfg.get("selected_columns") or []
        renames = cfg.get("renames") or {}
        if cols:
            cols_quoted = ", ".join(f'"{c}"' for c in cols)
            lines.append(f"    {var} = {parent_var}.select({cols_quoted})")
        else:
            lines.append(f"    {var} = {parent_var}")

        for old_col, new_col in renames.items():
            lines.append(f'    {var} = {var}.withColumnRenamed("{old_col}", "{new_col}")')

    @classmethod
    def _compile_derived_column_node(cls, lines: List[str], var: str, parent_var: str, cfg: Dict[str, Any]):
        cols = cfg.get("columns")
        if isinstance(cols, list) and cols:
            current_var = parent_var
            for c in cols:
                c_name = c.get("name") or c.get("column_name") or "new_col"
                c_expr = c.get("expression") or c.get("expr") or "1"
                escaped = c_expr.replace('"', '\\"')
                lines.append(f'    {var} = {current_var}.withColumn("{c_name}", F.expr("{escaped}"))')
                current_var = var
        else:
            col_name = cfg.get("column_name") or cfg.get("target_column") or "new_col"
            expr = cfg.get("expression") or cfg.get("expr") or "1"
            escaped_expr = expr.replace('"', '\\"')
            lines.append(f'    {var} = {parent_var}.withColumn("{col_name}", F.expr("{escaped_expr}"))')

    @classmethod
    def _compile_aggregate_node(cls, lines: List[str], var: str, parent_var: str, cfg: Dict[str, Any]):
        group_cols = cfg.get("group_by") or cfg.get("group_columns") or []
        aggs = cfg.get("aggregates") or cfg.get("aggregations") or []
        groups_str = ", ".join(f'"{c}"' for c in group_cols) if group_cols else ""

        agg_exprs = []
        for a in aggs:
            col = a.get("column")
            func = (a.get("function") or "count").lower()
            alias = a.get("alias") or f"{func}_{col}"
            agg_exprs.append(f'F.{func}("{col}").alias("{alias}")')

        aggs_str = ", ".join(agg_exprs) if agg_exprs else 'F.count("*").alias("count")'
        if groups_str:
            lines.append(f"    {var} = {parent_var}.groupBy({groups_str}).agg({aggs_str})")
        else:
            lines.append(f"    {var} = {parent_var}.agg({aggs_str})")

    @classmethod
    def _compile_join_node(cls, lines: List[str], var: str, parents: List[str], cfg: Dict[str, Any]):
        left_var = cls._sanitize_var_name(parents[0]) if len(parents) > 0 else "df_left"
        right_var = cls._sanitize_var_name(parents[1]) if len(parents) > 1 else "df_right"

        how = (cfg.get("join_type") or "inner").lower()
        left_on = cfg.get("left_keys") or cfg.get("left_key") or ["id"]
        right_on = cfg.get("right_keys") or cfg.get("right_key") or ["id"]

        if isinstance(left_on, str):
            left_on = [left_on]
        if isinstance(right_on, str):
            right_on = [right_on]

        if left_on == right_on:
            keys_str = ", ".join(f'"{k}"' for k in left_on)
            lines.append(f'    {var} = {left_var}.join({right_var}, on=[{keys_str}], how="{how}")')
        else:
            conds = [f'{left_var}["{l}"] == {right_var}["{r}"]' for l, r in zip(left_on, right_on)]
            cond_str = " & ".join(f"({c})" for c in conds)
            lines.append(f'    {var} = {left_var}.join({right_var}, on={cond_str}, how="{how}")')

    @classmethod
    def _compile_union_node(cls, lines: List[str], var: str, parents: List[str]):
        if len(parents) < 2:
            lines.append(f"    {var} = {cls._sanitize_var_name(parents[0])}")
        else:
            p0 = cls._sanitize_var_name(parents[0])
            p1 = cls._sanitize_var_name(parents[1])
            lines.append(f"    {var} = {p0}.unionByName({p1})")

    @classmethod
    def _compile_sort_node(cls, lines: List[str], var: str, parent_var: str, cfg: Dict[str, Any]):
        cols = cfg.get("sort_columns") or cfg.get("columns") or ["id"]
        order_clauses = []
        for c in cols:
            if isinstance(c, dict):
                col_name = c.get("column", "id")
                is_desc = (c.get("direction", "") or "").lower() == "desc"
            else:
                col_name = str(c)
                is_desc = cfg.get("descending", False)
            order_clauses.append(f'F.col("{col_name}").desc()' if is_desc else f'F.col("{col_name}").asc()')
        order_str = ", ".join(order_clauses)
        lines.append(f"    {var} = {parent_var}.orderBy({order_str})")

    @classmethod
    def _compile_window_node(cls, lines: List[str], var: str, parent_var: str, cfg: Dict[str, Any]):
        part_cols = cfg.get("partition_by") or []
        order_cols = cfg.get("order_by") or []
        target_col = cfg.get("target_column", "rank")
        func_name = (cfg.get("function") or "row_number").lower()

        part_args = ", ".join(f'"{c}"' for c in part_cols)
        order_args = ", ".join(f'"{c}"' for c in order_cols)
        part_str = f".partitionBy({part_args})" if part_cols else ""
        order_str = f".orderBy({order_args})" if order_cols else ""

        w_var = f"w_{var}"
        lines.append(f"    {w_var} = Window{part_str}{order_str}")
        lines.append(f'    {var} = {parent_var}.withColumn("{target_col}", F.{func_name}().over({w_var}))')

    @classmethod
    def _compile_cast_node(cls, lines: List[str], var: str, parent_var: str, cfg: Dict[str, Any]):
        casts = cfg.get("casts") or {}
        lines.append(f"    {var} = {parent_var}")
        for col, target_type in casts.items():
            lines.append(f'    {var} = {var}.withColumn("{col}", F.col("{col}").cast("{target_type}"))')
