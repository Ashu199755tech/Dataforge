"""
Unit and integration tests for Phase 3 & Phase 4:
  - DQAssessActivity (read-only audit, DQI calculation, FactDQExecutionLog)
  - DQEnforceActivity (cleansing, two-phase tagging, cell-level audit DQCleansingLog)
  - Write strategies: insert, full, merge
  - Sink modes: Single-sink vs Dual-sink (Target + Quarantine)
  - End-to-end Pipeline DAG: Ingest -> DQAssess -> IfCondition -> DQEnforce -> Target / Quarantine
"""
import os
import json
import tempfile
import polars as pl
import pytest

from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.dq_assess import DQAssessActivity
from backend.app.activities.dq_enforce import DQEnforceActivity
from backend.app.activities.if_condition import IfConditionActivity
from backend.app.activities.factory import get_activity_instance
from backend.app.dataquality.dq_tagger import FLAG_COL, CLEANSED_COL


@pytest.fixture
def sample_bronze_csv(tmp_path):
    """Generates a mock bronze customers CSV file with mixed quality records."""
    csv_file = tmp_path / "bronze_customers.csv"
    df = pl.DataFrame({
        "customer_id": [101, 102, 103, None, 105],
        "full_name": ["  John   Doe  ", "Jane Smith", "Bob Wilson", "Ghost User", "Alice Wonder"],
        "email": ["john@example.com", "invalid-email", "bob@example.com", "ghost@example.com", "alice@example.com"],
        "status": ["ACTIVE", "N/A", "PENDING", "ACTIVE", "UNKNOWN"],
        "credit_score": [720.0, 650.0, -10.0, 700.0, 800.0]
    })
    df.write_csv(str(csv_file))
    return str(csv_file)


@pytest.fixture
def dq_rules():
    return [
        {
            "rule_id": "R_PK_NN",
            "rule_type": "ATR1",
            "target_column": "customer_id",
            "technical_description": "Customer ID must not be null"
        },
        {
            "rule_id": "R_EMAIL_FMT",
            "rule_type": "ATR4",
            "target_column": "email",
            "parameters": {"pattern": r"^[^@]+@[^@]+\.[^@]+$"},
            "technical_description": "Valid email address format"
        },
        {
            "rule_id": "R_STATUS_PH",
            "rule_type": "ATR3",
            "target_column": "status",
            "placeholder_values": ["N/A", "UNKNOWN"],
            "technical_description": "Status must not contain placeholders"
        },
        {
            "rule_id": "R_CREDIT_POS",
            "rule_type": "ATR6",
            "target_column": "credit_score",
            "technical_description": "Credit score must be positive"
        }
    ]


@pytest.fixture
def cleansing_steps():
    return [
        # Stage 0: trim names
        {"rule_id": "R_PK_NN", "target_column": "full_name", "strategy": "trim", "fire": "always"},
        # Stage 0: Remediate status placeholders to default "PENDING"
        {"rule_id": "R_STATUS_PH", "target_column": "status", "strategy": "hardcode_constant", "params": {"value": "PENDING"}},
        # Stage 0: Remediate negative credit scores to 0
        {"rule_id": "R_CREDIT_POS", "target_column": "credit_score", "strategy": "hardcode_constant", "params": {"value": 0.0}}
    ]


# ==============================================================================
# PHASE 3: DQAssessActivity Tests
# ==============================================================================

def test_dq_assess_activity_execution(sample_bronze_csv, dq_rules):
    """DQAssessActivity performs a read-only audit and computes overall DQI and metrics."""
    ctx = ActivityExecutionContext(
        pipeline_run_id="run_assess_01",
        activity_id="act_assess",
        activity_name="Assess_Customers",
        activity_type="DQAssessActivity",
        config={
            "typeProperties": {
                "sourceDataset": {"file_path": sample_bronze_csv},
                "ruleCatalogue": dq_rules,
                "dqiGateThreshold": 0.50,
                "key_columns": ["customer_id"]
            }
        }
    )

    activity = DQAssessActivity(ctx)
    res = activity.execute()

    assert res.status == "Succeeded"
    outputs = res.output_variables

    # 5 rows total
    assert outputs["totalRows"] == 5
    # Row 0 is clean (101)
    # Row 1 fails email (invalid-email) and status (N/A) -> soft reject
    # Row 2 fails credit score (-10) -> soft reject
    # Row 3 fails PK (None) -> hard reject
    # Row 4 fails status (UNKNOWN) -> soft reject
    assert outputs["cleanRows"] == 1
    assert outputs["softRejectRows"] == 3
    assert outputs["hardRejectRows"] == 1
    assert outputs["overallDQI"] == 0.20
    assert outputs["gatePassed"] is False  # 0.20 < 0.50 threshold
    assert "R_PK_NN" in outputs["ruleMetrics"]


def test_dq_assess_empty_dataset():
    """DQAssessActivity gracefully handles empty datasets."""
    empty_df = pl.DataFrame({"id": [], "val": []})
    ctx = ActivityExecutionContext(
        pipeline_run_id="run_assess_empty",
        activity_id="act_assess_empty",
        activity_name="Assess_Empty",
        activity_type="DQAssessActivity",
        config={"dataframe": empty_df, "rules": []}
    )
    activity = DQAssessActivity(ctx)
    res = activity.execute()
    assert res.status == "Succeeded"
    assert res.output_variables["totalRows"] == 0
    assert res.output_variables["overallDQI"] == 1.0
    assert res.output_variables["gatePassed"] is True


# ==============================================================================
# PHASE 3 & 4: DQEnforceActivity Tests
# ==============================================================================

def test_dq_enforce_single_sink_mode(sample_bronze_csv, dq_rules, cleansing_steps, tmp_path):
    """DQEnforceActivity in single-sink mode writes all rows to Target with DQ_FLAG."""
    target_file = str(tmp_path / "silver_single_sink.parquet")

    ctx = ActivityExecutionContext(
        pipeline_run_id="run_enforce_single",
        activity_id="act_enforce_01",
        activity_name="Enforce_Single_Sink",
        activity_type="DQEnforceActivity",
        config={
            "typeProperties": {
                "sourceDataset": {"file_path": sample_bronze_csv},
                "targetDataset": {"file_path": target_file, "format": "parquet"},
                "ruleCatalogue": dq_rules,
                "cleansingMap": cleansing_steps,
                "writeStrategy": "full",
                "cleansingEnabled": True,
                "dqiGateThreshold": 0.40,
                "key_columns": ["customer_id"]
            }
        }
    )

    activity = DQEnforceActivity(ctx)
    res = activity.execute()

    assert res.status == "Succeeded"
    outputs = res.output_variables
    assert outputs["totalRows"] == 5
    assert outputs["cleansedRows"] >= 2
    # Verify file was written
    assert os.path.exists(target_file)
    written_df = pl.read_parquet(target_file)
    assert len(written_df) == 5
    assert FLAG_COL in written_df.columns
    assert "PREV_ROW_HASH" in written_df.columns
    assert "LAST_ROW_HASH" in written_df.columns


def test_dq_enforce_dual_sink_mode(sample_bronze_csv, dq_rules, cleansing_steps, tmp_path):
    """DQEnforceActivity in dual-sink mode routes clean rows to Target and rejected to Quarantine."""
    target_file = str(tmp_path / "silver_clean.parquet")
    quarantine_file = str(tmp_path / "silver_quarantine.parquet")

    ctx = ActivityExecutionContext(
        pipeline_run_id="run_enforce_dual",
        activity_id="act_enforce_02",
        activity_name="Enforce_Dual_Sink",
        activity_type="DQEnforceActivity",
        config={
            "typeProperties": {
                "sourceDataset": {"file_path": sample_bronze_csv},
                "targetDataset": {"file_path": target_file, "format": "parquet"},
                "quarantineDataset": {"file_path": quarantine_file, "format": "parquet"},
                "ruleCatalogue": dq_rules,
                "cleansingMap": cleansing_steps,
                "writeStrategy": "full",
                "cleansingEnabled": True,
                "key_columns": ["customer_id"]
            }
        }
    )

    activity = DQEnforceActivity(ctx)
    res = activity.execute()

    assert res.status == "Succeeded"
    assert os.path.exists(target_file)
    assert os.path.exists(quarantine_file)

    clean_df = pl.read_parquet(target_file)
    quarantine_df = pl.read_parquet(quarantine_file)

    # All rows in target must have DQ_FLAG = 1
    assert all(f == 1 for f in clean_df[FLAG_COL].to_list())
    # All rows in quarantine must have DQ_FLAG IN (2, 3)
    assert all(f in (2, 3) for f in quarantine_df[FLAG_COL].to_list())
    # Clean count + Quarantine count == total rows (5)
    assert len(clean_df) + len(quarantine_df) == 5


def test_write_strategies_insert_full_merge(tmp_path):
    """Verifies insert, full, and merge write strategies."""
    target_file = str(tmp_path / "write_strat_test.parquet")

    # Initial batch: rows 1 and 2
    batch1 = pl.DataFrame({
        "id": [1, 2],
        "name": ["Alpha", "Beta"],
        FLAG_COL: [1, 1]
    })
    batch1.write_parquet(target_file)

    # Batch 2: row 2 updated, row 3 new
    batch2 = pl.DataFrame({
        "id": [2, 3],
        "name": ["Beta_Updated", "Gamma"],
        FLAG_COL: [1, 1]
    })

    # 1. Test MERGE (upsert on 'id')
    ctx_merge = ActivityExecutionContext(
        pipeline_run_id="run_merge",
        activity_id="act_merge",
        activity_name="Enforce_Merge",
        activity_type="DQEnforceActivity",
        config={
            "dataframe": batch2,
            "targetDataset": {"file_path": target_file, "format": "parquet"},
            "writeStrategy": "merge",
            "key_columns": ["id"]
        }
    )
    DQEnforceActivity(ctx_merge).execute()
    merged_df = pl.read_parquet(target_file).sort("id")
    assert len(merged_df) == 3
    assert merged_df["id"].to_list() == [1, 2, 3]
    assert merged_df["name"].to_list() == ["Alpha", "Beta_Updated", "Gamma"]

    # 2. Test FULL (overwrite target)
    ctx_full = ActivityExecutionContext(
        pipeline_run_id="run_full",
        activity_id="act_full",
        activity_name="Enforce_Full",
        activity_type="DQEnforceActivity",
        config={
            "dataframe": pl.DataFrame({"id": [99], "name": ["OnlyRow"], FLAG_COL: [1]}),
            "targetDataset": {"file_path": target_file, "format": "parquet"},
            "writeStrategy": "full"
        }
    )
    DQEnforceActivity(ctx_full).execute()
    overwritten_df = pl.read_parquet(target_file)
    assert len(overwritten_df) == 1
    assert overwritten_df["id"][0] == 99


# ==============================================================================
# PHASE 4: End-to-End Pipeline DAG Verification
# Ingest Raw -> DQAssess -> IfCondition (DQI >= 0.80) -> DQEnforce -> Target
# ==============================================================================

def test_end_to_end_dq_pipeline_dag(tmp_path):
    """
    Executes a complete Dataforge pipeline DAG:
        Copy/Ingest Raw -> DQAssess -> IfCondition (overallDQI >= 0.80) -> DQEnforce -> Silver
    """
    raw_file = str(tmp_path / "raw_events.csv")
    silver_file = str(tmp_path / "silver_events.parquet")
    quarantine_file = str(tmp_path / "quarantine_events.parquet")

    # Seed Raw Data: 10 events (9 valid, 1 blank customer)
    raw_df = pl.DataFrame({
        "event_id": [f"E{i}" for i in range(1, 11)],
        "customer_id": ["C100", "C101", "C102", "C103", "C104", "C105", "C106", "C107", "C108", ""],
        "amount": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    })
    raw_df.write_csv(raw_file)

    rules = [
        {"rule_id": "R_EVT_PK", "rule_type": "ATR1", "target_column": "event_id", "technical_description": "PK not null"},
        {"rule_id": "R_CUST_NB", "rule_type": "ATR2", "target_column": "customer_id", "technical_description": "Customer non-blank"}
    ]

    activity_outputs = {}

    # STEP 1: DQAssessActivity
    assess_ctx = ActivityExecutionContext(
        pipeline_run_id="dag_run_01",
        activity_id="act_assess",
        activity_name="Assess_Events",
        activity_type="DQAssessActivity",
        config={
            "typeProperties": {
                "sourceDataset": {"file_path": raw_file},
                "ruleCatalogue": rules,
                "dqiGateThreshold": 0.80,
                "key_columns": ["event_id"]
            }
        },
        activity_outputs=activity_outputs
    )
    assess_act = DQAssessActivity(assess_ctx)
    assess_res = assess_act.execute()

    assert assess_res.status == "Succeeded"
    activity_outputs["Assess_Events"] = assess_res.output_variables
    # 9 of 10 clean -> DQI = 0.90 >= 0.80 threshold
    assert assess_res.output_variables["overallDQI"] == 0.90
    assert assess_res.output_variables["gatePassed"] is True

    # STEP 2: IfConditionActivity
    if_ctx = ActivityExecutionContext(
        pipeline_run_id="dag_run_01",
        activity_id="act_if",
        activity_name="Check_DQI_Gate",
        activity_type="IfCondition",
        config={
            "expression": "@greaterOrEquals(activity('Assess_Events').output.overallDQI, 0.80)"
        },
        activity_outputs=activity_outputs
    )
    if_act = IfConditionActivity(if_ctx)
    if_res = if_act.execute()

    assert if_res.status == "Succeeded"
    assert if_res.output_variables["outcome"] is True
    assert if_res.output_variables["branch_taken"] == "True"
    activity_outputs["Check_DQI_Gate"] = if_res.output_variables

    # STEP 3: DQEnforceActivity (Executed when IfCondition branch is True)
    enforce_ctx = ActivityExecutionContext(
        pipeline_run_id="dag_run_01",
        activity_id="act_enforce",
        activity_name="Enforce_Events",
        activity_type="DQEnforceActivity",
        config={
            "typeProperties": {
                "sourceDataset": {"file_path": raw_file},
                "targetDataset": {"file_path": silver_file, "format": "parquet"},
                "quarantineDataset": {"file_path": quarantine_file, "format": "parquet"},
                "ruleCatalogue": rules,
                "writeStrategy": "merge",
                "key_columns": ["event_id"],
                "cleansingEnabled": True
            }
        },
        activity_outputs=activity_outputs
    )
    enforce_act = DQEnforceActivity(enforce_ctx)
    enforce_res = enforce_act.execute()

    assert enforce_res.status == "Succeeded"
    assert enforce_res.output_variables["cleanRows"] == 9
    assert enforce_res.output_variables["softRejectRows"] == 1

    # Verify silver target and quarantine persistence
    assert os.path.exists(silver_file)
    assert os.path.exists(quarantine_file)

    silver_df = pl.read_parquet(silver_file)
    quarantine_df = pl.read_parquet(quarantine_file)

    assert len(silver_df) == 9
    assert len(quarantine_df) == 1
    assert quarantine_df["customer_id"][0] is None  # empty was pre-cleansed to null
    assert quarantine_df[FLAG_COL][0] == 2
