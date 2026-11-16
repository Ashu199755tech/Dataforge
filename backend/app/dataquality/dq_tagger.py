"""
dq_tagger.py — Two-phase rule evaluation and row tagging engine for Dataforge.

Assigns and manages Data Quality audit columns:
    DQ_FLAG:
        1 = Clean / Cleansed: passed all rules initially or all failures remediated.
        2 = Soft reject: valid PK, but still violates >= 1 rule.
        3 = Hard reject: single-column Primary Key is NULL.
            (Composite PK is never assigned flag 3).
    DQ_FAILED_RULE_IDS:
        Comma-separated list of rule_ids that the row currently violates ('NONE' if clean).
    DQ_ORIG_FAILED_RULE_IDS:
        Snapshot of pre-cleanse rule failures for provenance.
    DQ_PROCESSED_TS:
        Timestamp of evaluation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import polars as pl

from backend.app.dataquality.dq_compiler import DQPredicateCompiler, DQRuleCatalogueItem

logger = logging.getLogger("dataforge.dataquality.tagger")

FLAG_COL = "DQ_FLAG"
FAILED_COL = "DQ_FAILED_RULE_IDS"
ORIG_FAILED_COL = "DQ_ORIG_FAILED_RULE_IDS"
TS_COL = "DQ_PROCESSED_TS"
CLEANSED_COL = "DQ_CLEANSED"
CLEANSING_ID_COL = "CLEANSING_ID"

NONE_SENTINEL = "NONE"

TAG_COLUMNS = [FLAG_COL, FAILED_COL, ORIG_FAILED_COL, TS_COL, CLEANSED_COL, CLEANSING_ID_COL]


def pre_cleanse_sanitization(
    df: pl.DataFrame,
    string_columns: Optional[List[str]] = None
) -> pl.DataFrame:
    r"""
    Step-0 Sanitization:
      - Strips leading/trailing whitespace.
      - Collapses multiple whitespace characters (\s+) to a single space.
      - Converts empty strings or whitespace-only strings to NULL (None).
    """
    if df.is_empty():
        return df

    target_cols = string_columns or [
        col for col, dtype in zip(df.columns, df.dtypes)
        if dtype == pl.String
    ]

    exprs = []
    for col in target_cols:
        if col not in df.columns:
            continue
        cleaned = (
            pl.col(col)
            .str.strip_chars()
            .str.replace_all(r"\s+", " ")
        )
        exprs.append(
            pl.when(cleaned == "")
            .then(None)
            .otherwise(cleaned)
            .alias(col)
        )

    return df.with_columns(exprs) if exprs else df


def infer_pk_columns(
    df: pl.DataFrame,
    rules: List[Union[DQRuleCatalogueItem, Dict[str, Any]]],
    provided_pk: Optional[List[str]] = None
) -> List[str]:
    """
    Infers primary key columns from DS1 primary-key uniqueness rules or provided keys.
    """
    if provided_pk:
        return [c for c in provided_pk if c in df.columns]

    for r in rules:
        if isinstance(r, DQRuleCatalogueItem):
            rtid = r.rule_type.upper()
            keys = r.key_columns
            desc = r.technical_description or ""
        else:
            rtid = str(r.get("rule_type") or r.get("rule_type_id") or "").upper()
            keys = r.get("key_columns")
            desc = str(r.get("technical_description") or "")

        if rtid == "DS1" and ("primary" in desc.lower() or "pk" in desc.lower() or "id" in desc.lower()):
            if keys:
                pks = [k.strip() for k in keys if k.strip() in df.columns]
                if pks:
                    return pks

    for candidate in ["id", "ID", "pk", "PK", "key", "KEY"]:
        if candidate in df.columns:
            return [candidate]

    return []


def tag_dataframe(
    df: pl.DataFrame,
    rules: List[Union[DQRuleCatalogueItem, Dict[str, Any]]],
    pk_columns: Optional[List[str]] = None,
    ref_frames: Optional[Dict[str, pl.DataFrame]] = None
) -> Tuple[pl.DataFrame, Dict[str, Any]]:
    """
    Evaluates rules and assigns interim DQ_FLAG (1=clean, 2=soft reject, 3=PK null)
    and DQ_FAILED_RULE_IDS.
    """
    ref_frames = ref_frames or {}
    pk_cols = infer_pk_columns(df, rules, pk_columns)
    is_composite = len(pk_cols) > 1

    applied_rules: List[str] = []
    skipped_rules: List[Dict[str, str]] = []

    # Map each row to a list of violated rule IDs
    if df.is_empty():
        empty_tagged = df.with_columns([
            pl.lit(1).cast(pl.Int32).alias(FLAG_COL),
            pl.lit(NONE_SENTINEL).alias(FAILED_COL),
            pl.lit(datetime.now(timezone.utc).isoformat()).alias(TS_COL)
        ])
        return empty_tagged, {
            "rules_total": len(rules),
            "rules_applied": 0,
            "rules_skipped": 0,
            "pk_columns": pk_cols,
            "pk_composite": is_composite
        }

    # Evaluate each rule to obtain a boolean Series of violations
    v_exprs: List[pl.Expr] = []
    for r in rules:
        item = r if isinstance(r, DQRuleCatalogueItem) else DQRuleCatalogueItem.from_dict(r)
        rid = item.rule_id
        viol_expr = DQPredicateCompiler.compile_violation(item, df.columns, ref_frames)

        if viol_expr is None:
            skipped_rules.append({
                "rule_id": rid,
                "rule_type": item.rule_type,
                "reason": "cannot compile expression or missing target column"
            })
            continue

        vcol = f"__v_{rid}"
        # When violated, literal rid, else null
        v_exprs.append(
            pl.when(viol_expr).then(pl.lit(rid)).otherwise(None).alias(vcol)
        )
        applied_rules.append(rid)

    tagged = df.with_columns(v_exprs) if v_exprs else df

    # Concat violated rule IDs
    if applied_rules:
        scratch_cols = [f"__v_{rid}" for rid in applied_rules]
        concat_expr = pl.concat_str(
            [pl.col(c) for c in scratch_cols],
            separator=",",
            ignore_nulls=True
        )
        tagged = tagged.with_columns(
            pl.when(concat_expr.str.len_chars() > 0)
            .then(concat_expr)
            .otherwise(pl.lit(NONE_SENTINEL))
            .alias(FAILED_COL)
        )
        tagged = tagged.drop(scratch_cols)
    else:
        tagged = tagged.with_columns(pl.lit(NONE_SENTINEL).alias(FAILED_COL))

    # Single-column PK null check (Flag 3)
    if pk_cols and not is_composite:
        pk_is_null_expr = pl.col(pk_cols[0]).is_null()
    else:
        pk_is_null_expr = pl.lit(False)

    has_failures_expr = pl.col(FAILED_COL) != NONE_SENTINEL

    tagged = tagged.with_columns([
        pl.when(pk_is_null_expr)
        .then(pl.lit(3))
        .when(has_failures_expr)
        .then(pl.lit(2))
        .otherwise(pl.lit(1))
        .cast(pl.Int32)
        .alias(FLAG_COL),
        pl.lit(datetime.now(timezone.utc).isoformat()).alias(TS_COL)
    ])

    report = {
        "rules_total": len(rules),
        "rules_applied": len(applied_rules),
        "rules_skipped": len(skipped_rules),
        "pk_columns": pk_cols,
        "pk_composite": is_composite,
        "skipped": skipped_rules
    }
    return tagged, report


def retag_after_cleanse(
    df: pl.DataFrame,
    rules: List[Union[DQRuleCatalogueItem, Dict[str, Any]]],
    pk_columns: Optional[List[str]] = None,
    ref_frames: Optional[Dict[str, pl.DataFrame]] = None,
    keep_original_failed: bool = True
) -> Tuple[pl.DataFrame, Dict[str, Any]]:
    """
    Phase 2 Re-Tagging:
      Re-evaluates rules on cleansed DataFrame.
      - Preserves pre-cleanse failures in DQ_ORIG_FAILED_RULE_IDS.
      - Refreshes DQ_FAILED_RULE_IDS with active live failures.
      - DQ_FLAG:
          3 if single-PK is null
          2 if row still violates >= 1 rule
          1 if clean initially OR all failures successfully remediated by cleansing.
    """
    retag_df = df
    if keep_original_failed and FAILED_COL in retag_df.columns:
        if ORIG_FAILED_COL not in retag_df.columns:
            retag_df = retag_df.with_columns(pl.col(FAILED_COL).alias(ORIG_FAILED_COL))

    # Drop prior flag & live failed columns before retagging
    cols_to_drop = [c for c in [FLAG_COL, FAILED_COL, TS_COL] if c in retag_df.columns]
    if cols_to_drop:
        retag_df = retag_df.drop(cols_to_drop)

    new_tagged, report = tag_dataframe(retag_df, rules, pk_columns=pk_columns, ref_frames=ref_frames)

    return new_tagged, report
