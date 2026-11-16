"""
dq_assess.py — Native Dataforge DQAssessActivity conforming to ADF JSON standards.

Performs a read-only data quality assessment against the Rule Catalogue.
Emits ADF execution outputs (overallDQI, cleanRows, softRejectRows, hardRejectRows, gatePassed)
and records execution metrics in FACT_DQ_EXECUTION_LOG. Does not write datasets.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import polars as pl
from sqlalchemy.orm import Session

from backend.app.activities.base import BaseActivity, ActivityExecutionResult
from backend.app.models.data_quality import FactDQExecutionLog
from backend.app.dataquality.dq_compiler import DQPredicateCompiler, DQRuleCatalogueItem
from backend.app.dataquality.dq_tagger import tag_dataframe, FLAG_COL, FAILED_COL, infer_pk_columns
from backend.app.dataquality.dq_io import (
    resolve_dataset_config,
    load_dataset_as_polars,
    resolve_rule_catalogue
)

logger = logging.getLogger("dataforge.activities.dq_assess")


class DQAssessActivity(BaseActivity):
    """
    Native ADF-compatible Data Quality Assessment Activity.
    Evaluates rule violations and computes overall Data Quality Index (DQI).
    Emits output metrics for downstream ADF conditional branching (IfCondition, Switch).
    """

    def execute(self) -> ActivityExecutionResult:
        cfg = self.context.config
        type_props = cfg.get("typeProperties", cfg)

        # 1. Resolve Source Dataset
        src_ref = type_props.get("sourceDataset") or cfg.get("sourceDataset") or cfg.get("source") or cfg
        src_cfg = resolve_dataset_config(src_ref, db=self.db, default_cfg=cfg)
        dataset_name = src_cfg.get("dataset_name") or src_cfg.get("table_name") or src_cfg.get("file_path") or "SourceDataset"

        self.log("INFO", f"Starting DQAssessActivity on '{dataset_name}'")

        df = load_dataset_as_polars(src_cfg, db=self.db)
        if df.is_empty():
            self.log("WARNING", f"Source dataset '{dataset_name}' is empty")
            empty_out = {
                "status": "Succeeded",
                "totalRows": 0,
                "cleanRows": 0,
                "softRejectRows": 0,
                "hardRejectRows": 0,
                "overallDQI": 1.0,
                "gatePassed": True,
                "ruleMetrics": {}
            }
            return ActivityExecutionResult(
                status="Succeeded",
                rows_read=0,
                rows_written=0,
                output_variables=empty_out,
                metrics=empty_out
            )

        # 2. Resolve Rules
        rule_ref = type_props.get("ruleCatalogue") or cfg.get("ruleCatalogue") or cfg.get("rules") or []
        rules = resolve_rule_catalogue(rule_ref, db=self.db, dataset_name=dataset_name)
        if not rules:
            # Fallback to direct rules in config
            rules = cfg.get("rules") or type_props.get("rules") or []

        dqi_threshold = float(type_props.get("dqiGateThreshold") or cfg.get("dqiGateThreshold") or cfg.get("min_score_threshold", 0.95))
        # Support percentage threshold if passed as 95.0 instead of 0.95
        if dqi_threshold > 1.0:
            dqi_threshold = dqi_threshold / 100.0

        pk_cols = type_props.get("key_columns") or cfg.get("key_columns") or cfg.get("pk_columns")
        pk_columns = infer_pk_columns(df, rules, pk_cols)

        # 3. Evaluate Rule Violations
        tagged_df, report = tag_dataframe(df, rules, pk_columns=pk_columns)

        flags = tagged_df[FLAG_COL].to_list()
        total_rows = len(flags)
        clean_rows = sum(1 for f in flags if f == 1)
        soft_reject_rows = sum(1 for f in flags if f == 2)
        hard_reject_rows = sum(1 for f in flags if f == 3)

        overall_dqi = round(clean_rows / total_rows, 4) if total_rows > 0 else 1.0
        gate_passed = bool(overall_dqi >= dqi_threshold)

        # Rule-level breakdown
        rule_metrics = {}
        all_failed_strs = tagged_df[FAILED_COL].to_list()
        for r in rules:
            rid = r.get("rule_id") if isinstance(r, dict) else r.rule_id
            fail_count = sum(1 for s in all_failed_strs if rid and rid in s)
            rule_metrics[rid] = {
                "failedRecords": fail_count,
                "passRate": round(1.0 - (fail_count / total_rows), 4) if total_rows > 0 else 1.0
            }

        # 4. Record to FACT_DQ_EXECUTION_LOG
        if self.db:
            try:
                log_entry = FactDQExecutionLog(
                    pipeline_run_id=self.context.pipeline_run_id,
                    activity_run_id=self.activity_run_id or self.context.activity_id,
                    activity_type="DQAssessActivity",
                    dataset_name=str(dataset_name),
                    total_records=total_rows,
                    clean_records=clean_rows,
                    soft_reject_records=soft_reject_rows,
                    hard_reject_records=hard_reject_rows,
                    cleansed_records=0,
                    overall_dqi=overall_dqi,
                    gate_passed=gate_passed,
                    rule_metrics=rule_metrics,
                    executed_at=datetime.now(timezone.utc)
                )
                self.db.add(log_entry)
                self.db.commit()
            except Exception as e:
                logger.warning(f"Failed to persist FactDQExecutionLog: {e}")

        output_payload = {
            "status": "Succeeded",
            "totalRows": total_rows,
            "cleanRows": clean_rows,
            "softRejectRows": soft_reject_rows,
            "hardRejectRows": hard_reject_rows,
            "overallDQI": overall_dqi,
            "gatePassed": gate_passed,
            "ruleMetrics": rule_metrics
        }

        self.log(
            "INFO",
            f"DQAssess complete: totalRows={total_rows}, cleanRows={clean_rows}, "
            f"overallDQI={overall_dqi:.4f}, gatePassed={gate_passed}"
        )

        fail_on_error = cfg.get("fail_pipeline_on_error", False) or cfg.get("fail_on_threshold", False)
        status = "Failed" if (fail_on_error and not gate_passed) else "Succeeded"

        return ActivityExecutionResult(
            status=status,
            rows_read=total_rows,
            rows_written=0,
            output_variables=output_payload,
            metrics=output_payload
        )
