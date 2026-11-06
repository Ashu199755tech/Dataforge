import re
from typing import Dict, Any, List, Optional, Tuple

from backend.app.engine.pushdown.models import (
    SQLDialect,
    PushdownQueryPlan
)
from backend.app.engine.pushdown.dialect import DialectFormatter


class SQLPushdownTranspiler:
    """
    Compiles DataForge Visual Data Flow transformation graphs into multi-CTE ANSI SQL
    queries for in-database ELT pushdown execution.
    """

    @classmethod
    def compile_graph(
        cls,
        graph_json: Dict[str, Any],
        dialect: SQLDialect = SQLDialect.ANSI,
        write_mode: str = "ctas",
        target_table: Optional[str] = None,
        target_schema: Optional[str] = None,
        if_not_exists: bool = False
    ) -> PushdownQueryPlan:
        """
        Translates a Data Flow transformation graph into a chained Common Table Expression (CTE) query.
        """
        nodes = graph_json.get("nodes", [])
        edges = graph_json.get("edges", [])

        if not nodes:
            return PushdownQueryPlan(
                dialect=dialect,
                cte_chain=[],
                final_query="SELECT 1;",
                write_mode=write_mode
            )

        # 1. Topological sort
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
            raise ValueError("Cycle detected in Data Flow transformation graph during SQL transpilation.")

        nodes_by_id = {n["id"]: n for n in nodes}
        cte_chain: List[Tuple[str, str]] = []
        last_cte_name = None
        inferred_target_table = target_table
        inferred_target_schema = target_schema

        for node_id in exec_order:
            node = nodes_by_id[node_id]
            data = node.get("data", {})
            op_type = (
                data.get("operatorType") or data.get("operator") or node.get("type") or ""
            ).strip().lower()
            cfg = data.get("config", {})
            parents = incoming.get(node_id, [])

            cte_name = cls._sanitize_cte_name(node_id)

            if op_type == "source":
                select_sql = cls._transpile_source(cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "sink":
                # Sink node does not introduce a new CTE; it specifies the output target
                inferred_target_table = inferred_target_table or cfg.get("table_name") or cfg.get("dataset_name")
                inferred_target_schema = inferred_target_schema or cfg.get("schema_name") or cfg.get("schema")

            elif op_type == "filter":
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_filter(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "select":
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_select(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type in ("derivedcolumn", "derived_column"):
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_derived_column(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "aggregate":
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_aggregate(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "join":
                left_cte = cls._sanitize_cte_name(parents[0]) if len(parents) > 0 else "cte_left"
                right_cte = cls._sanitize_cte_name(parents[1]) if len(parents) > 1 else "cte_right"
                select_sql = cls._transpile_join(left_cte, right_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "union":
                left_cte = cls._sanitize_cte_name(parents[0]) if len(parents) > 0 else "cte_left"
                right_cte = cls._sanitize_cte_name(parents[1]) if len(parents) > 1 else "cte_right"
                select_sql = cls._transpile_union(left_cte, right_cte, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "sort":
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_sort(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "window":
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_window(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type in ("surrogatekey", "surrogate_key"):
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_surrogate_key(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            elif op_type == "cast":
                parent_cte = cls._sanitize_cte_name(parents[0])
                select_sql = cls._transpile_cast(parent_cte, cfg, dialect)
                cte_chain.append((cte_name, select_sql))
                last_cte_name = cte_name

            else:
                parent_cte = cls._sanitize_cte_name(parents[0]) if parents else "cte_prev"
                p_q = DialectFormatter.quote_identifier(parent_cte, dialect)
                cte_chain.append((cte_name, f"SELECT * FROM {p_q}"))
                last_cte_name = cte_name

        # 2. Assemble chained CTE query
        cte_parts = []
        for name, sql in cte_chain:
            q_name = DialectFormatter.quote_identifier(name, dialect)
            cte_parts.append(f"{q_name} AS (\n{sql}\n)")

        cte_block = "WITH " + ",\n".join(cte_parts)
        final_select = f"SELECT * FROM {DialectFormatter.quote_identifier(last_cte_name or 'cte_0', dialect)}"

        full_query = f"{cte_block}\n{final_select}"

        # 3. Apply target write mode (CTAS / INSERT / SELECT)
        if inferred_target_table and write_mode == "ctas":
            final_sql = DialectFormatter.render_ctas(
                table=inferred_target_table,
                select_query=full_query,
                schema=inferred_target_schema,
                dialect=dialect,
                if_not_exists=if_not_exists
            )
        elif inferred_target_table and write_mode == "insert":
            final_sql = DialectFormatter.render_insert_into(
                table=inferred_target_table,
                select_query=full_query,
                schema=inferred_target_schema,
                dialect=dialect
            )
        else:
            final_sql = f"{full_query};"

        return PushdownQueryPlan(
            dialect=dialect,
            cte_chain=cte_chain,
            final_query=final_sql,
            target_table=inferred_target_table,
            target_schema=inferred_target_schema,
            write_mode=write_mode
        )

    # ------------------------------------------------------------------
    # Operator Transpilers
    # ------------------------------------------------------------------

    @classmethod
    def _sanitize_cte_name(cls, node_id: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", node_id)
        return f"cte_{clean}"

    @classmethod
    def _transpile_source(cls, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        tbl = cfg.get("table_name") or cfg.get("dataset_name") or "source_table"
        sch = cfg.get("schema_name") or cfg.get("schema")
        table_q = DialectFormatter.qualify_table(tbl, sch, dialect)

        cols = cfg.get("columns") or []
        cols_clause = ", ".join(DialectFormatter.quote_identifier(c, dialect) for c in cols) if cols else "*"

        where_cond = cfg.get("filter_expr") or cfg.get("filter_expression") or cfg.get("condition")
        where_clause = f" WHERE ({where_cond})" if where_cond else ""

        return f"    SELECT {cols_clause} FROM {table_q}{where_clause}"

    @classmethod
    def _transpile_filter(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        cond = cfg.get("condition") or cfg.get("filter_expression") or "1 = 1"
        return f"    SELECT * FROM {parent_q} WHERE ({cond})"

    @classmethod
    def _transpile_select(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        cols = cfg.get("columns") or []
        renames = cfg.get("renames") or cfg.get("rename_columns") or {}

        if not cols and not renames:
            return f"    SELECT * FROM {parent_q}"

        select_items = []
        if cols:
            for c in cols:
                c_q = DialectFormatter.quote_identifier(c, dialect)
                if c in renames:
                    new_q = DialectFormatter.quote_identifier(renames[c], dialect)
                    select_items.append(f"{c_q} AS {new_q}")
                else:
                    select_items.append(c_q)
        else:
            select_items.append("*")
            for old_c, new_c in renames.items():
                old_q = DialectFormatter.quote_identifier(old_c, dialect)
                new_q = DialectFormatter.quote_identifier(new_c, dialect)
                select_items.append(f"{old_q} AS {new_q}")

        return f"    SELECT {', '.join(select_items)} FROM {parent_q}"

    @classmethod
    def _transpile_derived_column(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        cols = cfg.get("columns")
        if isinstance(cols, list) and cols:
            derived_items = []
            for c in cols:
                c_name = c.get("name") or c.get("column_name") or "new_col"
                c_expr = c.get("expression") or c.get("expr") or "NULL"
                c_q = DialectFormatter.quote_identifier(c_name, dialect)
                derived_items.append(f"({c_expr}) AS {c_q}")
            return f"    SELECT *, {', '.join(derived_items)} FROM {parent_q}"
        else:
            col_name = cfg.get("column_name") or cfg.get("target_column") or "new_col"
            expr = cfg.get("expression") or cfg.get("expr") or "NULL"
            col_q = DialectFormatter.quote_identifier(col_name, dialect)
            return f"    SELECT *, ({expr}) AS {col_q} FROM {parent_q}"

    @classmethod
    def _transpile_aggregate(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        group_cols = cfg.get("group_by") or cfg.get("group_columns") or []
        aggs = cfg.get("aggregates") or cfg.get("aggregations") or []

        group_items = [DialectFormatter.quote_identifier(c, dialect) for c in group_cols]
        agg_items = []

        for a in aggs:
            col = a.get("column")
            func = (a.get("function") or "COUNT").upper()
            alias = a.get("alias") or f"{func}_{col}"
            alias_q = DialectFormatter.quote_identifier(alias, dialect)
            if col and col != "*":
                col_q = DialectFormatter.quote_identifier(col, dialect)
                agg_items.append(f"{func}({col_q}) AS {alias_q}")
            else:
                agg_items.append(f"{func}(*) AS {alias_q}")

        if not agg_items:
            agg_items.append(f"COUNT(*) AS {DialectFormatter.quote_identifier('row_count', dialect)}")

        select_cols = group_items + agg_items
        select_clause = ", ".join(select_cols)

        group_clause = f" GROUP BY {', '.join(group_items)}" if group_items else ""
        return f"    SELECT {select_clause} FROM {parent_q}{group_clause}"

    @classmethod
    def _transpile_join(cls, left_cte: str, right_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        left_q = DialectFormatter.quote_identifier(left_cte, dialect)
        right_q = DialectFormatter.quote_identifier(right_cte, dialect)

        how = (cfg.get("join_type") or "INNER").upper()
        if how == "LEFT":
            how = "LEFT OUTER"
        elif how == "RIGHT":
            how = "RIGHT OUTER"
        elif how == "FULL":
            how = "FULL OUTER"

        left_keys = cfg.get("left_keys") or cfg.get("left_key") or ["id"]
        right_keys = cfg.get("right_keys") or cfg.get("right_key") or ["id"]

        if isinstance(left_keys, str):
            left_keys = [left_keys]
        if isinstance(right_keys, str):
            right_keys = [right_keys]

        on_conds = []
        for l, r in zip(left_keys, right_keys):
            l_q = f"{left_q}.{DialectFormatter.quote_identifier(l, dialect)}"
            r_q = f"{right_q}.{DialectFormatter.quote_identifier(r, dialect)}"
            on_conds.append(f"{l_q} = {r_q}")

        on_clause = " AND ".join(on_conds)
        return f"    SELECT * FROM {left_q} {how} JOIN {right_q} ON ({on_clause})"

    @classmethod
    def _transpile_union(cls, left_cte: str, right_cte: str, dialect: SQLDialect) -> str:
        left_q = DialectFormatter.quote_identifier(left_cte, dialect)
        right_q = DialectFormatter.quote_identifier(right_cte, dialect)
        return f"    SELECT * FROM {left_q}\n    UNION ALL\n    SELECT * FROM {right_q}"

    @classmethod
    def _transpile_sort(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        cols = cfg.get("sort_columns") or cfg.get("columns") or ["id"]
        sort_items = []
        for c in cols:
            if isinstance(c, dict):
                col_name = c.get("column", "id")
                direction = (c.get("direction", "") or "ASC").upper()
            else:
                col_name = str(c)
                descending = cfg.get("descending", False)
                direction = "DESC" if descending else "ASC"
            sort_items.append(f"{DialectFormatter.quote_identifier(col_name, dialect)} {direction}")
        return f"    SELECT * FROM {parent_q} ORDER BY {', '.join(sort_items)}"

    @classmethod
    def _transpile_window(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        part_cols = cfg.get("partition_by") or []
        order_cols = cfg.get("order_by") or []
        target_col = cfg.get("target_column", "rank")
        func_name = (cfg.get("function") or "ROW_NUMBER").upper()

        part_clause = f"PARTITION BY {', '.join(DialectFormatter.quote_identifier(c, dialect) for c in part_cols)}" if part_cols else ""
        order_clause = f"ORDER BY {', '.join(DialectFormatter.quote_identifier(c, dialect) for c in order_cols)}" if order_cols else "ORDER BY (SELECT 1)"

        window_spec = f"({part_clause} {order_clause})".strip()
        col_q = DialectFormatter.quote_identifier(target_col, dialect)

        return f"    SELECT *, {func_name}() OVER {window_spec} AS {col_q} FROM {parent_q}"

    @classmethod
    def _transpile_surrogate_key(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        key_col = cfg.get("key_column", "id")
        col_q = DialectFormatter.quote_identifier(key_col, dialect)
        return f"    SELECT *, ROW_NUMBER() OVER (ORDER BY (SELECT 1)) AS {col_q} FROM {parent_q}"

    @classmethod
    def _transpile_cast(cls, parent_cte: str, cfg: Dict[str, Any], dialect: SQLDialect) -> str:
        parent_q = DialectFormatter.quote_identifier(parent_cte, dialect)
        casts = cfg.get("casts") or {}
        if not casts:
            return f"    SELECT * FROM {parent_q}"

        cast_exprs = []
        for col, target_type in casts.items():
            col_q = DialectFormatter.quote_identifier(col, dialect)
            cast_exprs.append(f"CAST({col_q} AS {target_type}) AS {col_q}")

        return f"    SELECT *, {', '.join(cast_exprs)} FROM {parent_q}"
