"""
dq_enforce.py — Native Dataforge DQEnforceActivity conforming to ADF JSON standards.

Executes:
    1. Reads source dataset.
    2. Runs Phase 2 Cleansing and Two-Phase Tagging via DQEnforceCore.
    3. Persists audit records to DQ_CLEANSING_LOG and FACT_DQ_EXECUTION_LOG.
    4. Routes records to target and quarantine sinks:
       - Single-sink mode: all rows written to target with DQ_FLAG.
       - Dual-sink mode: clean rows (DQ_FLAG=1) to target; rejected rows (DQ_FLAG in 2,3) to quarantine.
    5. Write strategies: 'insert' (append), 'full' (overwrite), 'merge' (upsert on PKs).
    6. Emits ADF execution outputs (cleanRows, softRejectRows, hardRejectRows, cleansedRows, overallDQI, gatePassed).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import polars as pl
from sqlalchemy.orm import Session

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.data_quality import FactDQExecutionLog, DQCleansingLog
from backend.app.dataquality.dq_enforce_core import DQEnforceCore
from backend.app.dataquality.dq_tagger import FLAG_COL, CLEANSED_COL, infer_pk_columns
from backend.app.dataquality.dq_io import (
    resolve_dataset_config,
    load_dataset_as_polars,
    write_polars_dataset,
    resolve_rule_catalogue,
    resolve_cleansing_map
)

logger = logging.getLogger("dataforge.activities.dq_enforce")


class DQEnforceActivity(BaseActivity):
    """
    Native ADF-compatible Data Quality Enforcement Activity.
    """

    def execute(self) -> ActivityExecutionResult:
        cfg = self.context.config
        type_props = cfg.get("typeProperties", cfg)

        # 1. Resolve Source Dataset
        src_ref = type_props.get("sourceDataset") or cfg.get("sourceDataset") or cfg.get("source") or cfg
        src_cfg = resolve_dataset_config(src_ref, db=self.db, default_cfg=cfg)
        dataset_name = src_cfg.get("dataset_name") or src_cfg.get("table_name") or src_cfg.get("file_path") or "SourceDataset"

        # 2. Resolve Target and Quarantine Datasets
        tgt_ref = type_props.get("targetDataset") or cfg.get("targetDataset") or cfg.get("destination") or cfg.get("target") or {}
        tgt_cfg = resolve_dataset_config(tgt_ref, db=self.db)

        quarantine_ref = type_props.get("quarantineDataset") or cfg.get("quarantineDataset") or cfg.get("quarantine") or {}
        quarantine_cfg = resolve_dataset_config(quarantine_ref, db=self.db) if quarantine_ref else {}

        write_strategy = (type_props.get("writeStrategy") or cfg.get("writeStrategy") or cfg.get("write_mode") or "merge").lower()
        dqi_threshold = float(type_props.get("dqiGateThreshold") or cfg.get("dqiGateThreshold") or cfg.get("min_score_threshold", 0.95))
        if dqi_threshold > 1.0:
            dqi_threshold = dqi_threshold / 100.0

        cleansing_enabled = bool(type_props.get("cleansingEnabled", True) if "cleansingEnabled" in type_props else cfg.get("cleansingEnabled", True))

        self.log("INFO", f"Starting DQEnforceActivity: source='{dataset_name}', writeStrategy='{write_strategy}', cleansingEnabled={cleansing_enabled}")

        # 3. Load Source Data
        df = load_dataset_as_polars(src_cfg, db=self.db)
        if df.is_empty():
            self.log("WARNING", f"Source dataset '{dataset_name}' is empty")
            empty_out = {
                "status": "Succeeded",
                "totalRows": 0,
                "cleanRows": 0,
                "softRejectRows": 0,
                "hardRejectRows": 0,
                "cleansedRows": 0,
                "overallDQI": 1.0,
                "gatePassed": True
            }
            return ActivityExecutionResult(
                status="Succeeded",
                rows_read=0,
                rows_written=0,
                output_variables=empty_out,
                metrics=empty_out
            )

        # 4. Resolve Rules & Cleansing Map
        rule_ref = type_props.get("ruleCatalogue") or cfg.get("ruleCatalogue") or cfg.get("rules") or []
        rules = resolve_rule_catalogue(rule_ref, db=self.db, dataset_name=dataset_name)
        if not rules:
            rules = cfg.get("rules") or type_props.get("rules") or []

        cleansing_steps: List[Dict[str, Any]] = []
        if cleansing_enabled:
            map_ref = type_props.get("cleansingMap") or cfg.get("cleansingMap") or cfg.get("cleansing_steps") or []
            cleansing_steps = resolve_cleansing_map(map_ref, db=self.db)
            if not cleansing_steps and isinstance(cfg.get("cleansing_steps"), list):
                cleansing_steps = cfg["cleansing_steps"]

        pk_cols = type_props.get("key_columns") or cfg.get("key_columns") or cfg.get("pk_columns")
        pk_columns = infer_pk_columns(df, rules, pk_cols)

        # 5. Execute Core Enforcement & Cleansing
        final_df, cell_logs, metrics = DQEnforceCore.run_enforcement(
            df=df,
            rules=rules,
            cleansing_steps=cleansing_steps,
            pk_columns=pk_columns,
            table_name=dataset_name,
            batch_id=self.context.pipeline_run_id,
            dqi_gate_threshold=dqi_threshold
        )

        # 6. Sinks & Persistence (Single-Sink vs Dual-Sink routing)
        rows_written = 0
        is_dual_sink = bool(quarantine_cfg)

        if is_dual_sink:
            # Dual sink: route clean (flag 1) to target, and rejected (flag 2, 3) to quarantine
            clean_df = final_df.filter(pl.col(FLAG_COL) == 1)
            quarantine_df = final_df.filter(pl.col(FLAG_COL).is_in([2, 3]))

            if tgt_cfg:
                w1 = write_polars_dataset(clean_df, tgt_cfg, write_strategy=write_strategy, pk_columns=pk_columns, db=self.db)
                rows_written += w1
                self.log("INFO", f"Dual-sink Target write: {len(clean_df)} clean rows written")

            if quarantine_cfg:
                w2 = write_polars_dataset(quarantine_df, quarantine_cfg, write_strategy="insert", pk_columns=pk_columns, db=self.db)
                rows_written += w2
                self.log("INFO", f"Dual-sink Quarantine write: {len(quarantine_df)} rejected rows written")
        else:
            # Single sink: all records written to target with DQ_FLAG
            if tgt_cfg:
                rows_written = write_polars_dataset(final_df, tgt_cfg, write_strategy=write_strategy, pk_columns=pk_columns, db=self.db)
                self.log("INFO", f"Single-sink write: {rows_written} rows written to target with DQ_FLAG")

        # In-memory output retention for immediate verification / pipeline context
        self.context.activity_outputs["enforced_dataset"] = final_df

        # 7. Persist Cell Diffs to DQ_CLEANSING_LOG
        if self.db and cell_logs:
            try:
                for cl in cell_logs:
                    log_rec = DQCleansingLog(
                        cleansing_id=cl["cleansing_id"],
                        table_name=cl["table_name"],
                        column_name=cl["column_name"],
                        rule_id=cl["rule_id"],
                        strategy=cl["strategy"],
                        primary_key_values=cl.get("primary_key_values"),
                        before_value=cl.get("before_value"),
                        after_value=cl.get("after_value"),
                        batch_id=self.context.pipeline_run_id,
                        created_at=cl.get("created_at") or datetime.now(timezone.utc)
                    )
                    self.db.add(log_rec)
                self.db.commit()
            except Exception as e:
                logger.warning(f"Could not persist DQCleansingLog entries: {e}")

        # 8. Persist Summary to FACT_DQ_EXECUTION_LOG
        if self.db:
            try:
                exec_log = FactDQExecutionLog(
                    pipeline_run_id=self.context.pipeline_run_id,
                    activity_run_id=self.activity_run_id or self.context.activity_id,
                    activity_type="DQEnforceActivity",
                    dataset_name=str(dataset_name),
                    total_records=metrics["total_rows"],
                    clean_records=metrics["clean_rows"],
                    soft_reject_records=metrics["soft_reject_rows"],
                    hard_reject_records=metrics["hard_reject_rows"],
                    cleansed_records=metrics["cleansed_rows"],
                    overall_dqi=metrics["overall_dqi"],
                    gate_passed=metrics["gate_passed"],
                    rule_metrics={},
                    executed_at=datetime.now(timezone.utc)
                )
                self.db.add(exec_log)
                self.db.commit()
            except Exception as e:
                logger.warning(f"Could not persist FactDQExecutionLog entry: {e}")

        output_payload = {
            "status": "Succeeded",
            "totalRows": metrics["total_rows"],
            "cleanRows": metrics["clean_rows"],
            "softRejectRows": metrics["soft_reject_rows"],
            "hardRejectRows": metrics["hard_reject_rows"],
            "cleansedRows": metrics["cleansed_rows"],
            "overallDQI": metrics["overall_dqi"],
            "gatePassed": metrics["gate_passed"]
        }

        self.log(
            "INFO",
            f"DQEnforce complete: totalRows={metrics['total_rows']}, cleanRows={metrics['clean_rows']}, "
            f"cleansedRows={metrics['cleansed_rows']}, overallDQI={metrics['overall_dqi']:.4f}, gatePassed={metrics['gate_passed']}"
        )

        return ActivityExecutionResult(
            status="Succeeded",
            rows_read=metrics["total_rows"],
            rows_written=rows_written,
            output_variables=output_payload,
            metrics=output_payload
        )
