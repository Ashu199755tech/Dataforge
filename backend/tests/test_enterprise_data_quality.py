import os
import json
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


def test_custom_sql_conditions_and_queries():
    df = pl.DataFrame({
        "order_id": [101, 102, 103, 104],
        "subtotal": [100.0, 50.0, 200.0, 75.0],
        "discount": [10.0, 60.0, 20.0, 90.0]  # rows 1 and 3 violate discount <= subtotal
    })

    # 1. SQL Condition check: discount <= subtotal
    rules_cond = [
        {
            "rule_name": "Discount Cannot Exceed Subtotal",
            "rule_type": "CustomSqlCheck",
            "sql_condition": "discount <= subtotal",
            "threshold_percent": 100.0
        }
    ]
    res_cond = DataQualityEngine.evaluate_rules(df, rules_cond)
    assert res_cond["overall_status"] == "Failed"
    assert res_cond["quarantine_count"] == 2
    assert res_cond["composite_dq_score"] == 50.0  # 2 of 4 passed -> 50%
    assert res_cond["rule_results"][0]["failed_records_count"] == 2

    # 2. Violation WHERE clause: discount > subtotal
    rules_where = [
        {
            "rule_name": "Excessive Discount Filter",
            "rule_type": "CustomSqlCheck",
            "where_clause": "discount > subtotal",
            "threshold_percent": 100.0
        }
    ]
    res_where = DataQualityEngine.evaluate_rules(df, rules_where)
    assert res_where["overall_status"] == "Failed"
    assert res_where["quarantine_count"] == 2
    assert res_where["composite_dq_score"] == 50.0

    # 3. Full SELECT query returning violating rows
    rules_query = [
        {
            "rule_name": "Select Violating Discount Orders",
            "rule_type": "CustomSqlCheck",
            "sql_query": "SELECT * FROM dataset WHERE discount > subtotal",
            "threshold_percent": 100.0
        }
    ]
    res_query = DataQualityEngine.evaluate_rules(df, rules_query)
    assert res_query["overall_status"] == "Failed"
    assert res_query["quarantine_count"] == 2
    assert len(res_query["quarantine_records"]) == 2

    # 4. Valid condition where 100% pass
    rules_valid = [
        {
            "rule_name": "Subtotal Is Positive",
            "rule_type": "CustomSqlCheck",
            "sql_condition": "subtotal > 0",
            "threshold_percent": 100.0
        }
    ]
    res_valid = DataQualityEngine.evaluate_rules(df, rules_valid)
    assert res_valid["overall_status"] == "Passed"
    assert res_valid["composite_dq_score"] == 100.0
    assert res_valid["quarantine_count"] == 0


def test_custom_sql_reference_join():
    orders_df = pl.DataFrame({
        "order_id": [1, 2, 3],
        "customer_id": [10, 20, 30],
        "amount": [150.0, 75.0, 300.0]
    })
    customers_df = pl.DataFrame({
        "id": [10, 20, 30],
        "status": ["ACTIVE", "SUSPENDED", "ACTIVE"]  # customer 20 is suspended
    })

    # Join dataset with reference table and find orders placed by non-active customers
    join_rule = [
        {
            "rule_name": "Orders Only By Active Customers",
            "rule_type": "CustomSqlCheck",
            "sql_query": "SELECT dataset.__df_row_idx__ FROM dataset JOIN reference ON dataset.customer_id = reference.id WHERE reference.status = 'SUSPENDED'",
            "threshold_percent": 100.0
        }
    ]
    res = DataQualityEngine.evaluate_rules(orders_df, join_rule, ref_df=customers_df)
    assert res["overall_status"] == "Failed"
    assert res["quarantine_count"] == 1
    assert res["quarantine_records"][0]["customer_id"] == 20


def test_custom_sql_security_guard_disallows_ddl():
    df = pl.DataFrame({"id": [1, 2], "val": [10, 20]})
    ddl_rules = [
        {
            "rule_name": "Malicious DDL Injection",
            "rule_type": "CustomSqlCheck",
            "sql_query": "DROP TABLE dataset",
            "threshold_percent": 100.0
        }
    ]
    res = DataQualityEngine.evaluate_rules(df, ddl_rules)
    assert res["overall_status"] == "Failed"
    assert "Disallowed SQL statement detected" in res["rule_results"][0]["error_message"]


def test_manual_rulebook_evaluation_json_and_yaml():
    import json
    import yaml

    df = pl.DataFrame({
        "sku": ["A100", "B200", "C300"],
        "cost": [10.0, 25.0, 40.0],
        "retail_price": [15.0, 20.0, 60.0]  # row 1 violates retail_price >= cost * 1.2
    })

    # 1. JSON rulebook file
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_json:
        json_path = f_json.name
        json.dump({
            "dataset_name": "product_pricing",
            "min_score_threshold": 90.0,
            "rules": [
                {
                    "rule_name": "Non-null SKU",
                    "rule_type": "MandatoryFieldCheck",
                    "columns": ["sku"]
                },
                {
                    "rule_name": "Minimum Margin Assertion",
                    "rule_type": "CustomSqlCheck",
                    "sql_condition": "retail_price >= cost * 1.2"
                }
            ]
        }, f_json)

    # 2. YAML rulebook file
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f_yaml:
        yaml_path = f_yaml.name
        yaml.dump({
            "dataset_name": "product_pricing_yaml",
            "min_score_threshold": 50.0,
            "rules": [
                {
                    "rule_name": "Positive Cost Check",
                    "rule_type": "CustomSqlCheck",
                    "sql_condition": "cost > 0"
                }
            ]
        }, f_yaml)

    try:
        # Evaluate JSON rulebook
        res_json = DataQualityEngine.evaluate_rulebook(df, json_path)
        assert res_json["rules_evaluated"] == 2
        # Minimum margin rule failed (1 of 3 failed -> 66.67% on rule 2, 100% on rule 1 -> composite 83.33% < 90%)
        assert res_json["overall_status"] == "Failed"

        # Evaluate YAML rulebook
        res_yaml = DataQualityEngine.evaluate_rulebook(df, yaml_path)
        assert res_yaml["rules_evaluated"] == 1
        assert res_yaml["overall_status"] == "Passed"
        assert res_yaml["composite_dq_score"] == 100.0

    finally:
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(yaml_path):
            os.remove(yaml_path)


def test_data_quality_activity_with_rulebook_file(setup_dq_db):
    import json
    db = SessionLocal()
    try:
        pipe = db.query(Pipeline).first()
        if not pipe:
            pipe = Pipeline(
                project_id=setup_dq_db["project_id"],
                name="DQ Rulebook Pipeline",
                activities=[]
            )
            db.add(pipe)
            db.commit()
            db.refresh(pipe)

        run = db.query(PipelineRun).filter(PipelineRun.id == "run_dq_rulebook_test").first()
        if not run:
            run = PipelineRun(id="run_dq_rulebook_test", pipeline_id=pipe.id, status="Running")
            db.add(run)
            db.commit()

        # Create dataset CSV
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f_csv:
            csv_path = f_csv.name
            f_csv.write("item_id,price,tax\n1,100,10\n2,50,60\n3,30,3\n")

        # Create rulebook JSON
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rulebook:
            rulebook_path = f_rulebook.name
            json.dump({
                "dataset_name": "invoice_items",
                "min_score_threshold": 90.0,
                "rules": [
                    {
                        "rule_name": "Tax Cannot Exceed Price",
                        "rule_type": "CustomSqlCheck",
                        "sql_condition": "tax <= price"
                    }
                ]
            }, f_rulebook)

        ctx = ActivityExecutionContext(
            pipeline_run_id="run_dq_rulebook_test",
            activity_id="act_rulebook_exec",
            activity_name="Rulebook Test Activity",
            activity_type="DataQualityCheck",
            config={
                "file_path": csv_path,
                "rulebook_path": rulebook_path,
                "fail_pipeline_on_error": True
            }
        )
        act = DataQualityActivity(ctx, db)
        res = act.execute()
        # Item 2 has tax 60 > price 50, so rule fails and composite score is 66.67% < 90% threshold
        assert res.status == "Failed"
        assert "Data Quality threshold failed" in res.error_message
        assert res.outputs["quarantine_count"] == 1
        assert res.outputs["rules_failed"] == 1

    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)
        if os.path.exists(rulebook_path):
            os.remove(rulebook_path)
        db.close()


def test_data_quality_api_validate_with_custom_sql_and_catalog():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    # 1. Verify rules-catalog includes CustomSqlCheck
    cat_res = client.get("/api/v1/data-quality/rules-catalog")
    assert cat_res.status_code == 200
    rule_types = [r["rule_type"] for r in cat_res.json()]
    assert "CustomSqlCheck" in rule_types

    # 2. Test validate endpoint with custom SQL rule
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("id,gross,net\n1,100,90\n2,50,60\n")
        temp_csv = f.name

    try:
        val_res = client.post("/api/v1/data-quality/validate", json={
            "file_path": temp_csv,
            "min_score_threshold": 90.0,
            "rules": [
                {
                    "rule_name": "Net Cannot Exceed Gross",
                    "rule_type": "CustomSqlCheck",
                    "sql_condition": "net <= gross"
                }
            ]
        })
        assert val_res.status_code == 200
        val_data = val_res.json()
        assert val_data["overall_status"] == "Failed"
        assert val_data["composite_dq_score"] == 50.0
        assert val_data["quarantine_count"] == 1
        assert val_data["quarantine_records"][0]["id"] == 2

    finally:
        if os.path.exists(temp_csv):
            os.remove(temp_csv)


def test_rulebook_resolver_cloud_storage_and_snowflake_table(setup_dq_db):
    """
    Test RulebookResolver across:
      1. Cloud Storage (Local Storage / S3 simulation)
      2. Direct Cloud URI (s3://...)
      3. Cloud Data Warehouse / Snowflake table (Row-per-rule catalog)
      4. Cloud Data Warehouse / Snowflake table (Document-in-table JSON/YAML)
    """
    from backend.app.models.connection import Connection
    from backend.app.core.security import encrypt_secret
    from backend.app.dataquality.rulebook_resolver import RulebookResolver

    db = SessionLocal()
    try:
        proj_id = setup_dq_db["project_id"]

        # -------------------------------------------------------------
        # 1. Cloud Storage Simulation (Local storage / bucket)
        # -------------------------------------------------------------
        with tempfile.TemporaryDirectory() as storage_root:
            container_dir = os.path.join(storage_root, "rules-bucket")
            os.makedirs(container_dir, exist_ok=True)
            rulebook_file = os.path.join(container_dir, "finance_rules.yaml")
            with open(rulebook_file, "w") as f:
                f.write("""
dataset_name: orders
min_score_threshold: 85.0
rules:
  - rule_name: S3 Non-Negative Total
    rule_type: CustomSqlCheck
    sql_condition: "total_amount >= 0"
  - rule_name: S3 Mandatory Customer
    rule_type: MandatoryFieldCheck
    columns: ["customer_id"]
""")

            conn_storage = Connection(
                project_id=proj_id,
                name="Cloud Storage Rules Bucket",
                connector_type="local_storage",
                config_encrypted=encrypt_secret({"base_path": storage_root})
            )
            db.add(conn_storage)
            db.commit()
            db.refresh(conn_storage)

            # Resolve using connection ID + container + key
            rules, score = RulebookResolver.resolve_rules({
                "rulebook_source": "cloud_storage",
                "rulebook_connection_id": conn_storage.id,
                "rulebook_container": "rules-bucket",
                "rulebook_file_key": "finance_rules.yaml"
            }, db=db)

            assert len(rules) == 2
            assert score == 85.0
            assert rules[0]["rule_name"] == "S3 Non-Negative Total"
            assert rules[1]["rule_name"] == "S3 Mandatory Customer"

        # -------------------------------------------------------------
        # 2. Direct Cloud URI Parsing Test
        # -------------------------------------------------------------
        prov, cont, key = RulebookResolver._parse_cloud_uri("s3://analytics-governance/rules/daily_dq.yaml")
        assert prov == "aws_s3"
        assert cont == "analytics-governance"
        assert key == "rules/daily_dq.yaml"

        prov, cont, key = RulebookResolver._parse_cloud_uri("abfss://rules-cont@myacct.dfs.core.windows.net/sales/rules.json")
        assert prov == "azure_adls"
        assert cont == "rules-cont"
        assert key == "sales/rules.json"

        prov, cont, key = RulebookResolver._parse_cloud_uri("gs://gcp-dq-bucket/inventory/rules.yaml")
        assert prov == "gcp_storage"
        assert cont == "gcp-dq-bucket"
        assert key == "inventory/rules.yaml"

        # -------------------------------------------------------------
        # 3. Cloud Data Warehouse / Snowflake Table (Row-per-rule catalog)
        # -------------------------------------------------------------
        mock_snowflake_catalog = [
            {
                "RULE_NAME": "Snowflake Minimum Amount Check",
                "RULE_TYPE": "CustomSqlCheck",
                "SQL_CONDITION": "amount > 0",
                "COLUMNS": "amount",
                "IS_ACTIVE": True
            },
            {
                "RULE_NAME": "Snowflake Mandatory User Check",
                "RULE_TYPE": "MandatoryFieldCheck",
                "COLUMNS": "user_id, account_id",
                "IS_ACTIVE": True
            },
            {
                "RULE_NAME": "Disabled Rule",
                "RULE_TYPE": "CustomSqlCheck",
                "SQL_CONDITION": "1 = 0",
                "IS_ACTIVE": False
            }
        ]

        conn_snowflake = Connection(
            project_id=proj_id,
            name="Production Snowflake Warehouse",
            connector_type="snowflake",
            config_encrypted=encrypt_secret({
                "account": "xy12345.us-east-1",
                "user": "DATA_ENGINEER",
                "warehouse": "COMPUTE_WH",
                "database": "ANALYTICS",
                "schema": "GOVERNANCE",
                "mock_mode": True,
                "_mock_tables": {
                    "GOVERNANCE.RULES_CATALOG": mock_snowflake_catalog,
                    "RULES_CATALOG": mock_snowflake_catalog
                }
            })
        )
        db.add(conn_snowflake)
        db.commit()
        db.refresh(conn_snowflake)

        rules_sf, score_sf = RulebookResolver.resolve_rules({
            "rulebook_source": "database_table",
            "rulebook_connection_id": conn_snowflake.id,
            "rulebook_table_name": "RULES_CATALOG"
        }, db=db)

        # 3 rules in table, but 1 is inactive -> 2 active rules resolved
        assert len(rules_sf) == 2
        assert rules_sf[0]["rule_name"] == "Snowflake Minimum Amount Check"
        assert rules_sf[0]["sql_condition"] == "amount > 0"
        assert rules_sf[1]["rule_name"] == "Snowflake Mandatory User Check"
        assert rules_sf[1]["columns"] == ["user_id", "account_id"]

        # -------------------------------------------------------------
        # 4. Snowflake Table (Document-in-table JSON/YAML)
        # -------------------------------------------------------------
        mock_doc_table = [
            {
                "DATASET_NAME": "orders",
                "RULEBOOK_CONTENT": json.dumps({
                    "min_score_threshold": 92.5,
                    "rules": [
                        {
                            "rule_name": "JSON Doc Currency Check",
                            "rule_type": "CustomSqlCheck",
                            "sql_condition": "currency IN ('USD', 'EUR', 'INR')"
                        }
                    ]
                })
            }
        ]

        conn_sf_doc = Connection(
            project_id=proj_id,
            name="Snowflake Rulebook Document Store",
            connector_type="snowflake",
            config_encrypted=encrypt_secret({
                "account": "xy12345.us-east-1",
                "user": "DATA_ENGINEER",
                "warehouse": "COMPUTE_WH",
                "database": "ANALYTICS",
                "schema": "GOVERNANCE",
                "mock_mode": True,
                "_mock_tables": {
                    "DQ_RULEBOOKS": mock_doc_table
                }
            })
        )
        db.add(conn_sf_doc)
        db.commit()
        db.refresh(conn_sf_doc)

        rules_doc, score_doc = RulebookResolver.resolve_rules({
            "rulebook_source": "database_table",
            "rulebook_connection_id": conn_sf_doc.id,
            "rulebook_table_name": "DQ_RULEBOOKS"
        }, db=db)

        assert len(rules_doc) == 1
        assert score_doc == 92.5
        assert rules_doc[0]["rule_name"] == "JSON Doc Currency Check"

        # -------------------------------------------------------------
        # 5. Execute DataQualityActivity with Snowflake Rulebook
        # -------------------------------------------------------------
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f_csv:
            csv_path = f_csv.name
            f_csv.write("amount,user_id,account_id\n100,u1,a1\n-5,u2,a2\n")

        pipe = db.query(Pipeline).first()
        run = db.query(PipelineRun).filter(PipelineRun.id == "run_dq_cloud_test").first()
        if not run:
            run = PipelineRun(id="run_dq_cloud_test", pipeline_id=pipe.id, status="Running")
            db.add(run)
            db.commit()

        ctx = ActivityExecutionContext(
            pipeline_run_id="run_dq_cloud_test",
            activity_id="act_sf_dq",
            activity_name="Snowflake Rulebook DQ Activity",
            activity_type="DataQualityCheck",
            config={
                "file_path": csv_path,
                "rulebook_source": "database_table",
                "rulebook_connection_id": conn_snowflake.id,
                "rulebook_table_name": "RULES_CATALOG",
                "min_score_threshold": 90.0,
                "fail_pipeline_on_error": True
            }
        )
        act = DataQualityActivity(ctx, db)
        res = act.execute()
        # Row 2 has amount -5 <= 0, so rule fails -> status is Failed
        assert res.status == "Failed"
        assert res.outputs["rules_evaluated"] == 2
        assert res.outputs["quarantine_count"] == 1

        if os.path.exists(csv_path):
            os.remove(csv_path)

    finally:
        db.close()

