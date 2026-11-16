"""
dq_enforce_core.py — Unified Cleansing & Two-Phase Tagging Execution Coordinator.

Orchestrates:
    1. Pre-cleanse string sanitization (trim, whitespace collapse, empty -> null).
    2. Pre-cleanse hashing (PREV_ROW_HASH over business columns).
    3. Phase 1 Tagging (evaluation against Rule Catalogue -> DQ_FAILED_RULE_IDS).
    4. Precedence-Based Cleansing (Stage 0 Simple -> Stage 1 Translate -> Stage 2 Complex).
    5. Phase 2 Re-Tagging (re-evaluation -> final DQ_FLAG: 1=Clean/Cleansed, 2=Soft Reject, 3=Hard Reject).
    6. Post-cleanse hashing (LAST_ROW_HASH over cleansed business columns) + Metadata stamps.
    7. Cell-level audit trail generation for DQ_CLEANSING_LOG.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import polars as pl

from backend.app.dataquality.dq_compiler import DQRuleCatalogueItem
from backend.app.dataquality.dq_tagger import (
    FLAG_COL,
    FAILED_COL,
    ORIG_FAILED_COL,
    TS_COL,
    CLEANSED_COL,
    CLEANSING_ID_COL,
    infer_pk_columns,
    pre_cleanse_sanitization,
    tag_dataframe,
    retag_after_cleanse,
)
from backend.app.dataquality.dq_cleanser import DQCleansingEngine

logger = logging.getLogger("dataforge.dataquality.enforce_core")

HASH_SEP = "\x1f"

LOAD_TS_COL = "LOAD_TIMESTAMP"
BATCH_ID_COL = "BATCH_ID"
PREV_HASH_COL = "PREV_ROW_HASH"
LAST_HASH_COL = "LAST_ROW_HASH"

EXCLUDE_FROM_BUSINESS = {
    FLAG_COL, FAILED_COL, ORIG_FAILED_COL, TS_COL, CLEANSED_COL, CLEANSING_ID_COL,
    LOAD_TS_COL, BATCH_ID_COL, PREV_HASH_COL, LAST_HASH_COL, "OP_TYPE",
    "RECORD_SOURCE", "SRC_FILE_NAME", "SRC_FILE_PATH"
}


def get_business_columns(columns: List[str]) -> List[str]:
    """Returns columns that represent business attributes (excluding audit & metadata)."""
    exclude = {c.upper() for c in EXCLUDE_FROM_BUSINESS}
    return [c for c in columns if c.upper() not in exclude and not c.startswith("__")]


def compute_row_hashes(df: pl.DataFrame, business_cols: List[str]) -> pl.Series:
    """Computes MD5 hash per row over business columns joined with unit separator."""
    if not business_cols or df.is_empty():
        empty_hash = hashlib.md5("".encode("utf-8")).hexdigest()
        return pl.Series([empty_hash] * len(df), dtype=pl.String)

    concat_expr = pl.concat_str(
        [pl.col(c).cast(pl.String).fill_null("") for c in business_cols],
        separator=HASH_SEP
    )
    payload_series = df.select(concat_expr.alias("payload"))["payload"]
    hashes = [hashlib.md5(p.encode("utf-8")).hexdigest() for p in payload_series.to_list()]
    return pl.Series(hashes, dtype=pl.String)


class DQEnforceCore:
    """
    Core executor for Data Quality Assessment and Enforcement pipelines.
    """

    @classmethod
    def run_enforcement(
        cls,
        df: pl.DataFrame,
        rules: List[Union[DQRuleCatalogueItem, Dict[str, Any]]],
        cleansing_steps: Optional[List[Dict[str, Any]]] = None,
        pk_columns: Optional[List[str]] = None,
        ref_frames: Optional[Dict[str, pl.DataFrame]] = None,
        table_name: str = "DEFAULT_TABLE",
        batch_id: Optional[str] = None,
        dqi_gate_threshold: float = 0.95,
        translate_maps: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> Tuple[pl.DataFrame, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Executes end-to-end two-phase enforcement.

        Returns:
            (final_df, cleansing_logs, execution_metrics)
        """
        ref_frames = ref_frames or {}
        cleansing_steps = cleansing_steps or []
        pk_cols = infer_pk_columns(df, rules, pk_columns)
        effective_batch_id = batch_id or f"DQ_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        if df.is_empty():
            empty_df = df.with_columns([
                pl.lit(1).cast(pl.Int32).alias(FLAG_COL),
                pl.lit("NONE").alias(FAILED_COL),
                pl.lit("NONE").alias(ORIG_FAILED_COL),
                pl.lit(0).cast(pl.Int32).alias(CLEANSED_COL),
                pl.lit(None).cast(pl.String).alias(CLEANSING_ID_COL),
                pl.lit(None).cast(pl.String).alias(PREV_HASH_COL),
                pl.lit(None).cast(pl.String).alias(LAST_HASH_COL),
                pl.lit(datetime.now(timezone.utc).isoformat()).alias(LOAD_TS_COL),
                pl.lit(effective_batch_id).alias(BATCH_ID_COL),
            ])
            metrics = {
                "total_rows": 0,
                "clean_rows": 0,
                "soft_reject_rows": 0,
                "hard_reject_rows": 0,
                "cleansed_rows": 0,
                "overall_dqi": 1.0,
                "gate_passed": True,
                "rule_metrics": {}
            }
            return empty_df, [], metrics

        # -------------------------------------------------------------
        # 1. Pre-cleanse Sanitization
        # -------------------------------------------------------------
        sanitized_df = pre_cleanse_sanitization(df)

        # -------------------------------------------------------------
        # 2. Pre-cleanse Hash Stamp (PREV_ROW_HASH)
        # -------------------------------------------------------------
        b_cols = get_business_columns(sanitized_df.columns)
        prev_hashes = compute_row_hashes(sanitized_df, b_cols)
        stamped_df = sanitized_df.with_columns(prev_hashes.alias(PREV_HASH_COL))

        # -------------------------------------------------------------
        # 3. Phase 1 Tagging
        # -------------------------------------------------------------
        phase1_tagged, p1_report = tag_dataframe(
            stamped_df,
            rules,
            pk_columns=pk_cols,
            ref_frames=ref_frames
        )

        # -------------------------------------------------------------
        # 4. Precedence-Based Cleansing
        # -------------------------------------------------------------
        cleansing_logs: List[Dict[str, Any]] = []
        if cleansing_steps:
            cleansed_df, cleansing_logs = DQCleansingEngine.apply_cleansing(
                phase1_tagged,
                steps=cleansing_steps,
                pk_columns=pk_cols,
                table_name=table_name,
                translate_maps=translate_maps,
                failed_ids_col=FAILED_COL
            )
        else:
            cleansed_df = phase1_tagged.with_columns([
                pl.lit(0).cast(pl.Int32).alias(CLEANSED_COL),
                pl.lit(None).cast(pl.String).alias(CLEANSING_ID_COL)
            ])

        # -------------------------------------------------------------
        # 5. Phase 2 Re-Tagging
        # -------------------------------------------------------------
        phase2_tagged, p2_report = retag_after_cleanse(
            cleansed_df,
            rules,
            pk_columns=pk_cols,
            ref_frames=ref_frames,
            keep_original_failed=True
        )

        # -------------------------------------------------------------
        # 6. Post-cleanse Hash Stamp (LAST_ROW_HASH) & Metadata
        # -------------------------------------------------------------
        post_b_cols = get_business_columns(phase2_tagged.columns)
        last_hashes = compute_row_hashes(phase2_tagged, post_b_cols)

        now_iso = datetime.now(timezone.utc).isoformat()
        final_df = phase2_tagged.with_columns([
            last_hashes.alias(LAST_HASH_COL),
            pl.lit(now_iso).alias(LOAD_TS_COL),
            pl.lit(effective_batch_id).alias(BATCH_ID_COL)
        ])

        # -------------------------------------------------------------
        # 7. Compute Execution Metrics & DQI
        # -------------------------------------------------------------
        flags = final_df[FLAG_COL].to_list()
        total_rows = len(flags)
        clean_rows = sum(1 for f in flags if f == 1)
        soft_reject_rows = sum(1 for f in flags if f == 2)
        hard_reject_rows = sum(1 for f in flags if f == 3)
        cleansed_rows = sum(1 for c in final_df[CLEANSED_COL].to_list() if c == 1)

        overall_dqi = round(clean_rows / total_rows, 4) if total_rows > 0 else 1.0
        gate_passed = bool(overall_dqi >= dqi_gate_threshold)

        metrics = {
            "total_rows": total_rows,
            "clean_rows": clean_rows,
            "soft_reject_rows": soft_reject_rows,
            "hard_reject_rows": hard_reject_rows,
            "cleansed_rows": cleansed_rows,
            "overall_dqi": overall_dqi,
            "gate_passed": gate_passed,
            "rules_applied": p2_report.get("rules_applied", 0),
            "pk_columns": pk_cols
        }

        return final_df, cleansing_logs, metrics
