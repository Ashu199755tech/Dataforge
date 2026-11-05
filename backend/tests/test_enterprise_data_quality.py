import os
import tempfile
import pytest
import polars as pl
from sqlalchemy.orm import Session

from backend.app.core.database import SessionLocal, Base, engine
from backend.app.models.workspace import Workspace, Project
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.registry import activity_registry
from backend.app.dataquality.engine import DataQualityEngine
from backend.app.activities.data_quality import DataQualityActivity
from backend.app.activities.data_profiling import DataProfilingActivity
from backend.app.activities.reconciliation import ReconciliationActivity
from backend.app.activities.data_masking import DataMaskingActivity
import backend.app.activities.factory  # registers all activities


@pytest.fixture(scope="module")
def setup_dq_db():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    ws = db.query(Workspace).first()
    if not ws:
        ws = Workspace(name="DQ Test Workspace", description="Workspace for DQ testing")
        db.add(ws)
        db.commit()
        db.refresh(ws)

    proj = db.query(Project).first()
    if not proj:
        proj = Project(workspace_id=ws.id, name="DQ Project", description="DQ Project")
        db.add(proj)
        db.commit()
        db.refresh(proj)

    yield {"workspace_id": ws.id, "project_id": proj.id}
    db.close()


def test_registry_contains_phase8_activities():
    types = [a["activity_type"] for a in activity_registry.list_activities()]
    assert "DataQualityCheck" in types
    assert "DataProfiling" in types
    assert "Reconciliation" in types
    assert "DataMasking" in types


def test_mandatory_field_and_non_blank_checks():
    df = pl.DataFrame({
        "customer_id": [1, 2, 3],
        "name": ["Alice Smith", "   ", "Charlie Brown"],
        "email": ["alice@corp.com", "bob@corp.com", ""]
    })

    # Mandatory field check: passing
    res1 = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "MandatoryFieldCheck", "columns": ["customer_id", "name", "email"]}
    ])
    assert res1["overall_status"] == "Passed"
    assert res1["composite_dq_score"] == 100.0

    # Mandatory field check: missing column
    res2 = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "MandatoryFieldCheck", "columns": ["customer_id", "missing_tax_id"]}
    ])
    assert res2["overall_status"] == "Failed"
    assert res2["rules_failed"] == 1

    # Non-blank check: detects whitespace and empty string
    res3 = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "NonBlankCheck", "column": "name", "threshold_percent": 100.0}
    ])
    assert res3["rules_failed"] == 1
    assert res3["quarantine_count"] == 1
    assert res3["quarantine_records"][0]["customer_id"] == 2


def test_null_validation_and_duplicate_check():
    df = pl.DataFrame({
        "order_id": [101, 102, 102, 103, 104],
        "amount": [150.0, None, None, 299.9, 50.0],
        "store": ["NYC", "LON", "LON", "NYC", "TOK"]
    })

    # Null validation
    res_null = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "NullValidation", "column": "amount", "threshold_percent": 70.0}
    ])
    # 2 nulls out of 5 = 60% non-null -> fails 70% threshold
    assert res_null["overall_status"] == "Failed"
    assert res_null["quarantine_count"] == 2

    # Duplicate check on order_id
    res_dup = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "DuplicateCheck", "columns": ["order_id"], "threshold_percent": 100.0}
    ])
    assert res_dup["overall_status"] == "Failed"
    assert res_dup["quarantine_count"] == 2  # both duplicate rows flagged


def test_primary_key_uniqueness():
    df_clean = pl.DataFrame({
        "user_id": [1, 2, 3, 4],
        "username": ["usr1", "usr2", "usr3", "usr4"]
    })
    res_clean = DataQualityEngine.evaluate_rules(df_clean, [
        {"rule_type": "PrimaryKeyUniqueness", "columns": ["user_id"]}
    ])
    assert res_clean["overall_status"] == "Passed"

    df_dirty = pl.DataFrame({
        "user_id": [1, 2, 2, None],
        "username": ["usr1", "usr2", "usr2_dup", "usr4"]
    })
    res_dirty = DataQualityEngine.evaluate_rules(df_dirty, [
        {"rule_type": "PrimaryKeyUniqueness", "columns": ["user_id"]}
    ])
    assert res_dirty["overall_status"] == "Failed"
    assert res_dirty["quarantine_count"] == 3  # duplicate (2 rows) + null (1 row)


def test_referential_integrity():
    parent_df = pl.DataFrame({
        "dept_id": [10, 20, 30],
        "dept_name": ["Engineering", "Sales", "Finance"]
    })
    child_df = pl.DataFrame({
        "emp_id": [101, 102, 103, 104],
        "emp_name": ["Alice", "Bob", "Charlie", "Dave"],
        "dept_id": [10, 20, 99, 10]  # 99 does not exist in parent_df
    })

    res = DataQualityEngine.evaluate_rules(
        df=child_df,
        rules=[
            {
                "rule_type": "ReferentialIntegrity",
                "column": "dept_id",
                "reference_column": "dept_id",
                "threshold_percent": 100.0
            }
        ],
        ref_df=parent_df
    )
    assert res["overall_status"] == "Failed"
    assert res["quarantine_count"] == 1
    assert res["quarantine_records"][0]["emp_id"] == 103


def test_range_date_and_controlled_list_validation():
    df = pl.DataFrame({
        "age": [25, 45, 120, -5],
        "status": ["ACTIVE", "PENDING", "UNKNOWN_STATUS", "ACTIVE"],
        "join_date": ["2026-01-15", "2026-02-20", "invalid-date", "2026-03-01"]
    })

    rules = [
        {"rule_type": "RangeValidation", "column": "age", "min_value": 0, "max_value": 100},
        {"rule_type": "ControlledListValidation", "column": "status", "allowed_values": ["ACTIVE", "PENDING", "INACTIVE"]},
        {"rule_type": "DateValidation", "column": "join_date", "date_format": "%Y-%m-%d"}
    ]

    res = DataQualityEngine.evaluate_rules(df, rules)
    assert res["rules_evaluated"] == 3
    # Age has 2 violations (120, -5), Status has 1 violation, Date has 1 violation
    assert res["rules_failed"] == 3
    assert res["quarantine_count"] == 2


def test_schema_validation_and_drift_detection():
    df = pl.DataFrame({
        "id": [1, 2],
        "name": ["A", "B"],
        "unapproved_extra_col": [True, False]
    })

    # Schema Validation expecting specific columns
    res_schema = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "SchemaValidation", "expected_schema": {"id": "int", "name": "str", "created_at": "datetime"}}
    ])
    assert res_schema["overall_status"] == "Failed"

    # Schema Drift Detection
    res_drift = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "SchemaDriftDetection", "baseline_columns": ["id", "name"], "allow_drift": False}
    ])
    assert res_drift["overall_status"] == "Failed"


def test_pii_detection_and_data_masking():
    df = pl.DataFrame({
        "customer_id": [1, 2, 3],
        "email": ["john.doe@example.com", "jane.smith@corp.org", "not-an-email"],
        "ssn": ["123-45-6789", "987-65-4321", "plain-text"],
        "account_num": ["1234567890123456", "9876543210987654", "0000"]
    })

    # 1. PII Detection
    res_pii = DataQualityEngine.evaluate_rules(df, [
        {"rule_type": "PIIDetection", "column": "email", "pii_types": ["email"]},
        {"rule_type": "PIIDetection", "column": "ssn", "pii_types": ["ssn"]}
    ])
    # PII found in email (2 rows) and ssn (2 rows)
    assert res_pii["quarantine_count"] == 2

    # 2. Data Masking
    masked_df = DataQualityEngine.apply_masking(df, [
        {"column": "email", "strategy": "redact"},
        {"column": "ssn", "strategy": "hash"},
        {"column": "account_num", "strategy": "partial_mask"}
    ])

    assert masked_df["email"][0] == "[REDACTED]"
    assert masked_df["email"][1] == "[REDACTED]"
    assert len(masked_df["ssn"][0]) == 64  # SHA-256 hash
    assert masked_df["account_num"][0] == "************3456"
    assert masked_df["account_num"][1] == "************7654"


def test_statistical_data_profiling():
    df = pl.DataFrame({
        "price": [10.0, 20.0, 30.0, 40.0, 50.0, None],
        "category": ["Electronics", "Electronics", "Books", "Clothing", "Books", "Books"]
    })

    profile = DataQualityEngine.profile_dataset(df)
    assert profile["total_rows"] == 6
    assert profile["total_columns"] == 2

    # Price column profile
    price_prof = next(c for c in profile["columns"] if c["column_name"] == "price")
    assert price_prof["null_count"] == 1
    assert price_prof["min"] == 10.0
    assert price_prof["max"] == 50.0
    assert price_prof["mean"] == 30.0
    assert price_prof["median"] == 30.0

    # Category column profile
    cat_prof = next(c for c in profile["columns"] if c["column_name"] == "category")
    assert cat_prof["null_count"] == 0
    assert cat_prof["distinct_count"] == 3
    assert cat_prof["top_frequent_values"][0]["value"] == "Books"
    assert cat_prof["top_frequent_values"][0]["count"] == 3


def test_source_to_target_reconciliation():
    source_df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "amount": [100.0, 250.0, 50.0, 75.0]
    })
    target_match_df = pl.DataFrame({
        "id": [1, 2, 3, 4],
        "amount": [100.0, 250.0, 50.0, 75.0]
    })
    target_discrepancy_df = pl.DataFrame({
        "id": [1, 2, 3],
        "amount": [100.0, 250.0, 50.0]  # missing id 4
    })

    # Case 1: Match
    res_match = DataQualityEngine.reconcile(
        source_df=source_df,
        target_df=target_match_df,
        key_columns=["id"],
        numeric_sum_columns=["amount"]
    )
    assert res_match["reconciliation_status"] == "MATCHED"
    assert res_match["row_parity"] is True
    assert res_match["row_variance"] == 0

    # Case 2: Discrepancy
    res_discrepancy = DataQualityEngine.reconcile(
        source_df=source_df,
        target_df=target_discrepancy_df,
        key_columns=["id"],
        numeric_sum_columns=["amount"]
    )
    assert res_discrepancy["reconciliation_status"] == "DISCREPANCY_DETECTED"
    assert res_discrepancy["row_parity"] is False
    assert res_discrepancy["missing_in_target"] == 1


def test_data_quality_activity_pipeline_execution_with_quarantine(setup_dq_db):
    db: Session = SessionLocal()
    try:
        proj_id = setup_dq_db["project_id"]
        # Ensure test pipeline and runs exist to satisfy FK constraints
        pipe = db.query(Pipeline).filter(Pipeline.name == "DQ_Test_Pipeline").first()
        if not pipe:
            pipe = Pipeline(project_id=proj_id, name="DQ_Test_Pipeline", definition_json={})
            db.add(pipe)
            db.commit()
            db.refresh(pipe)

        run_pass = db.query(PipelineRun).filter(PipelineRun.id == "run_dq_test_pass").first()
        if not run_pass:
            run_pass = PipelineRun(id="run_dq_test_pass", pipeline_id=pipe.id, status="Running")
            db.add(run_pass)

        run_fail = db.query(PipelineRun).filter(PipelineRun.id == "run_dq_test_fail").first()
        if not run_fail:
            run_fail = PipelineRun(id="run_dq_test_fail", pipeline_id=pipe.id, status="Running")
            db.add(run_fail)
        db.commit()

        # Create temporary CSV dataset with mixed valid and invalid records
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("customer_id,name,email,score\n")
            f.write("1,Alice,alice@domain.com,95\n")
            f.write("2,,bob@domain.com,80\n")           # blank name
            f.write("3,Charlie,invalid-email,120\n")     # invalid email, score > 100
            f.write("4,David,david@domain.com,70\n")
            temp_csv = f.name

        quarantine_csv = temp_csv.replace(".csv", "_quarantine.csv")

        # 1. Pipeline execution with threshold 60% -> succeeds
        ctx_pass = ActivityExecutionContext(
            pipeline_run_id="run_dq_test_pass",
            activity_id="act_dq_gate_1",
            activity_name="DQ Validation Pass",
            activity_type="DataQualityCheck",
            config={
                "file_path": temp_csv,
                "min_score_threshold": 60.0,
                "quarantine_path": quarantine_csv,
                "rules": [
                    {"rule_type": "NonBlankCheck", "column": "name", "threshold_percent": 70.0},
                    {"rule_type": "RangeValidation", "column": "score", "min_value": 0, "max_value": 100, "threshold_percent": 70.0}
                ]
            }
        )
        act_pass = DataQualityActivity(ctx_pass, db)
        res_pass = act_pass.execute()
        assert res_pass.status == "Succeeded"
        assert res_pass.outputs["dq_score"] >= 60.0
        assert os.path.exists(quarantine_csv)

        # 2. Pipeline execution with strict threshold 100% -> fails
        ctx_fail = ActivityExecutionContext(
            pipeline_run_id="run_dq_test_fail",
            activity_id="act_dq_gate_2",
            activity_name="DQ Validation Strict",
            activity_type="DataQualityCheck",
            config={
                "file_path": temp_csv,
                "min_score_threshold": 100.0,
                "fail_pipeline_on_error": True,
                "rules": [
                    {"rule_type": "NonBlankCheck", "column": "name", "threshold_percent": 100.0}
                ]
            }
        )
        act_fail = DataQualityActivity(ctx_fail, db)
        res_fail = act_fail.execute()
        assert res_fail.status == "Failed"
        assert "Data Quality threshold failed" in res_fail.error_message

        # Clean up
        if os.path.exists(temp_csv):
            os.remove(temp_csv)
        if os.path.exists(quarantine_csv):
            os.remove(quarantine_csv)

    finally:
        db.close()
