"""
dq_cleanser.py — Precedence-based automated cleansing engine for Dataforge.

Applies remediations across three stages:
    Stage 0 (Simple): self-contained, single-column fixes (trim, strip_chars, strip_special,
                      set_null, hardcode_constant, set_value_conditional, value_remap, collapse_ws).
    Stage 1 (Translate): translation between sibling columns or dictionary mappings (Arabic <-> English).
    Stage 2 (Complex): cross-column / cross-table derivation (copy_from_column, lookup_source_col, derive_conditional).

Audit Trail:
    Generates a unique CLEANSING_ID UUID per changed row.
    Records cell-level change records in DQ_CLEANSING_LOG format.
    Sets DQ_CLEANSED = 1 for modified rows.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import polars as pl

logger = logging.getLogger("dataforge.dataquality.cleanser")

# Stages
STAGE_SIMPLE = 0
STAGE_TRANSLATE = 1
STAGE_COMPLEX = 2

STAGE_MAP: Dict[str, int] = {
    # Stage 0: Simple
    "trim": STAGE_SIMPLE,
    "collapse_ws": STAGE_SIMPLE,
    "strip_chars": STAGE_SIMPLE,
    "strip_special": STAGE_SIMPLE,
    "set_null": STAGE_SIMPLE,
    "hardcode_constant": STAGE_SIMPLE,
    "set_value_conditional": STAGE_SIMPLE,
    "value_remap": STAGE_SIMPLE,
    # Stage 1: Translate
    "translate": STAGE_TRANSLATE,
    # Stage 2: Complex
    "copy_from_column": STAGE_COMPLEX,
    "lookup_source_col": STAGE_COMPLEX,
    "derive_conditional": STAGE_COMPLEX,
}

_SPECIAL_PATTERN = r"[^0-9A-Za-z \u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]"


def _is_blank(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("null", "none", "nan")


def _eval_condition(row: Dict[str, Any], cond: Optional[Dict[str, Any]]) -> bool:
    """Evaluates declarative conditions: equals, in, is_null, not_null."""
    if not cond:
        return True
    col = cond.get("column")
    v = row.get(col) if col else None

    if cond.get("is_null"):
        return _is_blank(v)
    if cond.get("not_null"):
        return not _is_blank(v)
    if "equals" in cond:
        return ("" if v is None else str(v)) == str(cond["equals"])
    if "in" in cond:
        in_list = [str(x) for x in cond["in"]]
        return ("" if v is None else str(v)) in in_list
    return True


class DQCleansingEngine:
    """
    Executes precedence-based cleansing actions and logs cell-level audit diffs.
    """

    @classmethod
    def transform_value(
        cls,
        value: Any,
        step: Dict[str, Any],
        row: Dict[str, Any],
        run_date: str,
        translate_maps: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Any:
        strategy = (step.get("strategy") or step.get("op") or "").lower()
        params = step.get("params") or step

        # Stage 0: Simple
        if strategy == "trim":
            return str(value).strip() if value is not None else None

        elif strategy == "collapse_ws":
            return re.sub(r"\s+", " ", str(value)).strip() if value is not None else None

        elif strategy == "strip_chars":
            if value is None:
                return None
            s = str(value)
            chars = params.get("chars") or []
            for c in chars:
                s = s.replace(c, "")
            return s

        elif strategy == "strip_special":
            if value is None:
                return None
            pat = params.get("keep_pattern") or _SPECIAL_PATTERN
            return re.sub(pat, "", str(value))

        elif strategy == "set_null":
            return None

        elif strategy == "hardcode_constant":
            val = params.get("value")
            val_type = params.get("value_type", "string")
            if val_type == "date_expr" and str(val).upper() == "CURRENT_DATE":
                return run_date
            return val

        elif strategy == "set_value_conditional":
            cond = params.get("condition")
            if _eval_condition(row, cond):
                return params.get("value")
            return value

        elif strategy == "value_remap":
            mapping = params.get("mapping") or {}
            val_str = "" if value is None else str(value)
            if val_str in mapping:
                return mapping[val_str]
            default = params.get("default", "__keep__")
            return value if default == "__keep__" else default

        # Stage 1: Translate
        elif strategy == "translate":
            from_col = params.get("from_column") or params.get("source_column")
            sibling_val = row.get(from_col) if from_col else None
            # Check translation dictionary if available
            dict_name = params.get("dictionary") or "default"
            t_map = (translate_maps or {}).get(dict_name, {})
            if sibling_val is not None and str(sibling_val) in t_map:
                return t_map[str(sibling_val)]
            fallback_mode = params.get("fallback", "keep")
            if fallback_mode == "from_column" and sibling_val is not None:
                return sibling_val
            return value

        # Stage 2: Complex
        elif strategy == "copy_from_column":
            from_col = params.get("from_column") or params.get("source_column")
            if from_col and from_col in row:
                return row[from_col]
            return value

        elif strategy == "lookup_source_col":
            if _is_blank(value):
                from_col = params.get("from_column") or params.get("source_column")
                if from_col and not _is_blank(row.get(from_col)):
                    return row[from_col]
            return value

        elif strategy == "derive_conditional":
            branches = params.get("branches") or []
            for b in branches:
                if _eval_condition(row, b.get("condition")):
                    return b.get("value")
            default = params.get("default", "__keep__")
            return value if default == "__keep__" else default

        return value

    @classmethod
    def apply_cleansing(
        cls,
        df: pl.DataFrame,
        steps: List[Dict[str, Any]],
        pk_columns: Optional[List[str]] = None,
        table_name: str = "TARGET_TABLE",
        run_date: Optional[str] = None,
        translate_maps: Optional[Dict[str, Dict[str, str]]] = None,
        failed_ids_col: str = "DQ_FAILED_RULE_IDS"
    ) -> Tuple[pl.DataFrame, List[Dict[str, Any]]]:
        """
        Executes cleansing steps in precedence order on rows that violated corresponding rules.
        Returns:
            (cleansed_df, cleansing_logs)
        """
        if df.is_empty() or not steps:
            # Return unchanged df with default DQ_CLEANSED and CLEANSING_ID
            res = df
            if "DQ_CLEANSED" not in res.columns:
                res = res.with_columns(pl.lit(0).cast(pl.Int32).alias("DQ_CLEANSED"))
            if "CLEANSING_ID" not in res.columns:
                res = res.with_columns(pl.lit(None).cast(pl.String).alias("CLEANSING_ID"))
            return res, []

        pk_cols = pk_columns or []
        today_iso = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Sort steps by stage and original index
        norm_steps = []
        for i, s in enumerate(steps):
            strat = (s.get("strategy") or s.get("op") or "").lower()
            stage = STAGE_MAP.get(strat, STAGE_SIMPLE)
            rule_id = str(s.get("rule_id") or "")
            target_col = s.get("target_column") or s.get("attribute_id")
            fire = s.get("fire") or ("failed" if rule_id else "always")
            norm_steps.append({
                **s,
                "strategy": strat,
                "stage": stage,
                "rule_id": rule_id,
                "target_column": target_col,
                "fire": fire,
                "_orig_idx": i
            })

        norm_steps.sort(key=lambda x: (x["stage"], x["_orig_idx"]))

        # Convert to dictionary rows for precise per-cell diff tracking
        rows = df.to_dicts()
        cleansing_logs: List[Dict[str, Any]] = []

        cleansing_ids: List[Optional[str]] = [None] * len(rows)
        row_cleansed_flags: List[int] = [0] * len(rows)

        # Pre-index failed rule IDs per row
        row_failed_sets: List[Set[str]] = []
        for r in rows:
            raw_fails = r.get(failed_ids_col)
            if raw_fails and raw_fails != "NONE":
                row_failed_sets.append({x.strip() for x in str(raw_fails).split(",") if x.strip()})
            else:
                row_failed_sets.append(set())

        for step in norm_steps:
            target_col = step["target_column"]
            if not target_col or target_col not in df.columns:
                continue

            strat = step["strategy"]
            rule_id = step["rule_id"]
            fire = step["fire"]

            for idx, row in enumerate(rows):
                # Check firing scope: 'always' OR rule_id in row's failed set
                if fire != "always" and rule_id and (rule_id not in row_failed_sets[idx]):
                    continue

                before = row[target_col]
                after = cls.transform_value(before, step, row, today_iso, translate_maps)

                # Check if changed (null-safe)
                if (before is None and after is None) or before == after:
                    continue

                # Changed: update row value
                row[target_col] = after
                row_cleansed_flags[idx] = 1

                # Generate or retrieve CLEANSING_ID for row
                if not cleansing_ids[idx]:
                    cleansing_ids[idx] = str(uuid.uuid4())

                cleansing_logs.append({
                    "cleansing_id": cleansing_ids[idx],
                    "table_name": table_name,
                    "column_name": target_col,
                    "rule_id": rule_id,
                    "strategy": strat,
                    "primary_key_values": {k: row.get(k) for k in pk_cols},
                    "before_value": str(before) if before is not None else None,
                    "after_value": str(after) if after is not None else None,
                    "created_at": datetime.now(timezone.utc)
                })

        # Reconstruct DataFrame with preserved types
        new_schema = {}
        for col, dtype in df.schema.items():
            if dtype == pl.Null:
                if any(r.get(col) is not None for r in rows):
                    new_schema[col] = pl.String
                else:
                    new_schema[col] = pl.Null
            else:
                new_schema[col] = dtype

        try:
            cleansed_df = pl.DataFrame(rows, schema=new_schema)
        except Exception:
            cleansed_df = pl.DataFrame(rows)

        cleansed_df = cleansed_df.with_columns([
            pl.Series("DQ_CLEANSED", row_cleansed_flags, dtype=pl.Int32),
            pl.Series("CLEANSING_ID", cleansing_ids, dtype=pl.String)
        ])

        return cleansed_df, cleansing_logs
