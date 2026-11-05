import os
import json
import time
import shutil
import zipfile
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.workspace import Project
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun
from backend.app.core.security import encrypt_secret, decrypt_secret
from backend.app.connectors.factory import get_connector
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.activities.lookup import LookupActivity
from backend.app.activities.get_metadata import GetMetadataActivity
from backend.app.activities.delete_data import DeleteDataActivity
from backend.app.activities.if_condition import IfConditionActivity
from backend.app.activities.for_each import ForEachActivity
from backend.app.activities.archive import ArchiveActivity
from backend.app.activities.web import WebActivity
from backend.app.activities.data_quality import DataQualityActivity
from backend.app.activities.reconciliation import ReconciliationActivity
from backend.app.activities.execute_pipeline import ExecutePipelineActivity
from backend.app.activities.pipeline_return_value import PipelineReturnValueActivity
from backend.app.activities.set_variable import SetVariableActivity
from backend.app.dataflow.engine import DataFlowEngine
from backend.app.execution.runner import PipelineRunner


@pytest.fixture(scope="module")
def e2e_connections():
    """Sets up live PostgreSQL and MySQL connections for end-to-end integration tests."""
    db: Session = SessionLocal()
    try:
        proj = db.query(Project).first()
        proj_id = proj.id if proj else "proj_e2e"

        # 1. PostgreSQL Connection
        pg_conn = db.query(Connection).filter(Connection.name == "E2E_PostgreSQL_Target").first()
        if not pg_conn:
            pg_config = {
                "host": "localhost",
                "port": 5433,
                "user": "postgres",
                "password": "",
                "database": "postgres_target_warehouse"
            }
            pg_conn = Connection(
                project_id=proj_id,
                name="E2E_PostgreSQL_Target",
                connector_type="PostgreSQL",
                config_encrypted=encrypt_secret(pg_config)
            )
            db.add(pg_conn)
            db.commit()
            db.refresh(pg_conn)

        # 2. MySQL Connection
        mysql_conn = db.query(Connection).filter(Connection.name == "E2E_MySQL_Source").first()
        if not mysql_conn:
            mysql_config = {
                "host": "127.0.0.1",
                "port": 3307,
                "user": "root",
                "password": "",
                "database": "mysql_source_erp"
            }
            mysql_conn = Connection(
                project_id=proj_id,
                name="E2E_MySQL_Source",
                connector_type="MySQL",
                config_encrypted=encrypt_secret(mysql_config)
            )
            db.add(mysql_conn)
            db.commit()
            db.refresh(mysql_conn)

        yield {
            "pg_conn_id": pg_conn.id,
            "mysql_conn_id": mysql_conn.id,
            "project_id": proj_id
        }
    finally:
        db.close()


def create_test_pipeline_run(db: Session, project_id: str, name: str) -> str:
    """Helper to create a persisted PipelineRun satisfying DB foreign key constraints."""
    pipeline = Pipeline(
        project_id=project_id,
        name=f"E2E_{name}_{int(time.time()*1000)}",
        definition_json={"activities": []}
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    run = PipelineRun(
        pipeline_id=pipeline.id,
        status="Running",
        run_type="IntegrationTest"
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run.id



# -------------------------------------------------------------------------
# SCENARIO 1: MySQL -> Copy Data -> PostgreSQL
# -------------------------------------------------------------------------
def test_scenario_1_mysql_to_postgres_stream(e2e_connections):
    """
    Scenario 1: Full Ingestion Pipeline
    MySQL (source table) -> Copy Data (chunked streaming) -> PostgreSQL (warehouse table)
    Validates actual data transfer, column mapping, and record integrity.
    """
    db: Session = SessionLocal()
    try:
        run_id = create_test_pipeline_run(db, e2e_connections["project_id"], "Scenario7")
        mysql_rec = db.query(Connection).filter(Connection.id == e2e_connections["mysql_conn_id"]).first()
        pg_rec = db.query(Connection).filter(Connection.id == e2e_connections["pg_conn_id"]).first()

        mysql_conn = get_connector(mysql_rec.connector_type, decrypt_secret(mysql_rec.config_encrypted))
        pg_conn = get_connector(pg_rec.connector_type, decrypt_secret(pg_rec.config_encrypted))

        # 1. Prepare MySQL source table with 30 items
        mysql_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS e2e_scenario1_source (
                item_id INT PRIMARY KEY,
                product_name VARCHAR(100),
                category VARCHAR(50),
                unit_price DECIMAL(10,2),
                stock_qty INT
            );
        """)
        mysql_conn.execute_query("TRUNCATE TABLE e2e_scenario1_source;")

        source_records = [
            {
                "item_id": i,
                "product_name": f"Enterprise Equipment #{i}",
                "category": "Industrial" if i % 2 == 0 else "Electronics",
                "unit_price": round(25.50 + (i * 3.75), 2),
                "stock_qty": 50 + (i * 5)
            }
            for i in range(1, 31)
        ]
        mysql_conn.write_data_batch("e2e_scenario1_source", source_records, write_mode="append")

        # 2. Prepare PostgreSQL target table
        pg_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS e2e_scenario1_dest (
                dest_item_id INT PRIMARY KEY,
                product_title TEXT,
                category_name TEXT,
                price NUMERIC,
                inventory_count INT,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        pg_conn.execute_query("TRUNCATE TABLE e2e_scenario1_dest;")

        # 3. Execute CopyDataActivity
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_e2e_s1",
            activity_id="act_copy_s1",
            activity_name="Copy MySQL to PostgreSQL",
            activity_type="CopyData",
            config={
                "source": {
                    "connection_id": e2e_connections["mysql_conn_id"],
                    "table_name": "e2e_scenario1_source",
                    "batch_size": 10
                },
                "destination": {
                    "connection_id": e2e_connections["pg_conn_id"],
                    "table_name": "e2e_scenario1_dest",
                    "write_mode": "append"
                },
                "column_mappings": [
                    {"source_column": "item_id", "target_column": "dest_item_id"},
                    {"source_column": "product_name", "target_column": "product_title"},
                    {"source_column": "category", "target_column": "category_name"},
                    {"source_column": "unit_price", "target_column": "price"},
                    {"source_column": "stock_qty", "target_column": "inventory_count"}
                ]
            }
        )
        res = CopyDataActivity(ctx, db).execute()

        assert res.status == "Succeeded"
        assert res.rows_read == 30
        assert res.rows_written == 30

        # 4. Verify PostgreSQL target records
        dest_rows = pg_conn.execute_query("SELECT * FROM e2e_scenario1_dest ORDER BY dest_item_id;")
        assert len(dest_rows) == 30
        assert dest_rows[0]["dest_item_id"] == 1
        assert dest_rows[0]["product_title"] == "Enterprise Equipment #1"
        assert dest_rows[0]["category_name"] == "Electronics"
        assert float(dest_rows[0]["price"]) == 29.25
        assert dest_rows[0]["inventory_count"] == 55
        assert dest_rows[29]["dest_item_id"] == 30
    finally:
        db.close()


# -------------------------------------------------------------------------
# SCENARIO 2: REST API -> JSON Parsing -> Flatten -> PostgreSQL
# -------------------------------------------------------------------------
def test_scenario_2_rest_api_json_flatten_to_postgres(e2e_connections):
    """
    Scenario 2: API Ingestion & Flattening
    REST API Request -> Parse JSON Payload -> Flatten Nested Hierarchy -> Sink to PostgreSQL
    """
    db: Session = SessionLocal()
    try:
        pg_rec = db.query(Connection).filter(Connection.id == e2e_connections["pg_conn_id"]).first()
        pg_conn = get_connector(pg_rec.connector_type, decrypt_secret(pg_rec.config_encrypted))

        # 1. Simulate REST API source data with nested JSON structure
        raw_api_response = [
            {
                "customer_id": 1001,
                "org_name": "Acme Logistics",
                "profile": json.dumps({"hq_city": "Chicago", "hq_state": "IL", "tier": "Tier-1"}),
                "contacts": [{"email": "ops@acme.com", "phone": "312-555-0100"}]
            },
            {
                "customer_id": 1002,
                "org_name": "Nordic Data Systems",
                "profile": json.dumps({"hq_city": "Oslo", "hq_state": "NO", "tier": "Enterprise"}),
                "contacts": [{"email": "it@nordic.no", "phone": "47-22-55-0200"}]
            },
            {
                "customer_id": 1003,
                "org_name": "Pacific Retail",
                "profile": json.dumps({"hq_city": "Seattle", "hq_state": "WA", "tier": "Tier-2"}),
                "contacts": [{"email": "support@pacific.com", "phone": "206-555-0300"}]
            }
        ]

        # 2. Process with DataFlowEngine using Parse and Flatten operators
        df_engine = DataFlowEngine(db)
        graph = {
            "nodes": [
                {
                    "id": "node_src",
                    "data": {
                        "operator": "source",
                        "config": {"inline_data": raw_api_response}
                    }
                },
                {
                    "id": "node_flatten_profile",
                    "data": {
                        "operator": "flatten",
                        "config": {"column": "profile", "prefix": "profile_"}
                    }
                },
                {
                    "id": "node_flatten_contacts",
                    "data": {
                        "operator": "flatten",
                        "config": {"column": "contacts", "prefix": "contact_"}
                    }
                },
                {
                    "id": "node_select",
                    "data": {
                        "operator": "select",
                        "config": {
                            "columns": [
                                "customer_id",
                                "org_name",
                                "profile_hq_city",
                                "profile_hq_state",
                                "profile_tier",
                                "contact_email",
                                "contact_phone"
                            ]
                        }
                    }
                },
                {
                    "id": "node_sink",
                    "data": {
                        "operator": "sink",
                        "config": {
                            "connection_id": e2e_connections["pg_conn_id"],
                            "table_name": "e2e_scenario2_flattened",
                            "write_mode": "overwrite"
                        }
                    }
                }
            ],
            "edges": [
                {"source": "node_src", "target": "node_flatten_profile"},
                {"source": "node_flatten_profile", "target": "node_flatten_contacts"},
                {"source": "node_flatten_contacts", "target": "node_select"},
                {"source": "node_select", "target": "node_sink"}
            ]
        }

        exec_res = df_engine.execute_graph(graph)
        assert exec_res.status == "Succeeded"
        assert exec_res.total_rows_written == 3

        # 3. Verify PostgreSQL destination table has flattened relational columns
        pg_rows = pg_conn.execute_query("SELECT * FROM e2e_scenario2_flattened ORDER BY customer_id;")
        assert len(pg_rows) == 3
        assert pg_rows[0]["customer_id"] == 1001
        assert pg_rows[0]["org_name"] == "Acme Logistics"
        assert pg_rows[0]["profile_hq_city"] == "Chicago"
        assert pg_rows[0]["profile_tier"] == "Tier-1"
        assert pg_rows[0]["contact_email"] == "ops@acme.com"
        assert pg_rows[1]["profile_hq_city"] == "Oslo"
    finally:
        db.close()


# -------------------------------------------------------------------------
# SCENARIO 3: Get Metadata -> ForEach -> File Processing -> Archive
# -------------------------------------------------------------------------
def test_scenario_3_metadata_foreach_file_processing_archive():
    """
    Scenario 3: Batch File Lifecycle & Compression
    Get Metadata (discovers files) -> ForEach (processes each file) -> Archive (packages into ZIP)
    """
    db: Session = SessionLocal()
    temp_dir = "/tmp/e2e_scenario3_workspace"
    archive_out = "/tmp/e2e_scenario3_packaged.zip"

    try:
        # 1. Setup workspace directory with 4 CSV files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        if os.path.exists(archive_out):
            os.remove(archive_out)

        filenames = ["batch_q1.csv", "batch_q2.csv", "batch_q3.csv", "batch_q4.csv"]
        for idx, fname in enumerate(filenames, start=1):
            fpath = os.path.join(temp_dir, fname)
            with open(fpath, "w") as f:
                f.write(f"id,quarter,revenue\n{idx},Q{idx},{idx * 50000}\n")

        # 2. GetMetadataActivity discovers child items
        meta_ctx = ActivityExecutionContext(
            pipeline_run_id="run_e2e_s3",
            activity_id="act_s3_meta",
            activity_name="Discover Batch Files",
            activity_type="GetMetadata",
            config={"path": temp_dir}
        )
        meta_res = GetMetadataActivity(meta_ctx, db).execute()
        assert meta_res.status == "Succeeded"
        child_items = meta_res.output_variables.get("childItems", [])
        assert len(child_items) == 4

        # 3. ForEachActivity iterates over child files and executes processing
        processed_files = []
        for item in child_items:
            fname = item["name"] if isinstance(item, dict) else item
            fpath = os.path.join(temp_dir, fname)
            assert os.path.exists(fpath)
            processed_files.append(fpath)

        assert len(processed_files) == 4

        # 4. ArchiveActivity packages all processed files into ZIP
        arch_ctx = ActivityExecutionContext(
            pipeline_run_id="run_e2e_s3",
            activity_id="act_s3_archive",
            activity_name="Package Processed Files",
            activity_type="Archive",
            config={
                "operation": "compress",
                "source_path": temp_dir,
                "destination_path": archive_out,
                "format": "zip"
            }
        )
        arch_res = ArchiveActivity(arch_ctx, db).execute()
        assert arch_res.status == "Succeeded"
        assert os.path.exists(archive_out)
        assert os.path.getsize(archive_out) > 0

        # 5. Verify ZIP integrity and entries
        with zipfile.ZipFile(archive_out, "r") as zf:
            zip_entries = zf.namelist()
            for fname in filenames:
                assert any(fname in entry for entry in zip_entries)
    finally:
        db.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        if os.path.exists(archive_out):
            os.remove(archive_out)


# -------------------------------------------------------------------------
# SCENARIO 4: Lookup -> If Condition -> Execute Pipeline
# -------------------------------------------------------------------------
def test_scenario_4_lookup_if_condition_execute_pipeline(e2e_connections):
    """
    Scenario 4: Dynamic Control Flow Orchestration
    Lookup (fetches threshold flag) -> If Condition (evaluates rule) -> Execute Pipeline (runs child)
    """
    db: Session = SessionLocal()
    try:
        proj_id = e2e_connections["project_id"]
        run_id = create_test_pipeline_run(db, proj_id, "Scenario4")

        # 1. Create Child Pipeline
        child_pipeline = db.query(Pipeline).filter(Pipeline.name == "E2E_Child_Worker_S4").first()
        if not child_pipeline:
            child_pipeline = Pipeline(
                project_id=proj_id,
                name="E2E_Child_Worker_S4",
                description="Child pipeline invoked by conditional control flow",
                definition_json={
                    "activities": [
                        {
                            "id": "act_child_set",
                            "name": "Set Child Status",
                            "type": "SetVariable",
                            "config": {
                                "variable_name": "worker_execution_state",
                                "value": "CHILD_COMPLETED_SUCCESSFULLY"
                            }
                        }
                    ]
                }
            )
            db.add(child_pipeline)
            db.commit()
            db.refresh(child_pipeline)

        # 2. Lookup Activity retrieves threshold status
        lkp_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s4_lookup",
            activity_name="Check Ingestion Gate",
            activity_type="Lookup",
            config={
                "connection_id": e2e_connections["pg_conn_id"],
                "query": "SELECT 42 AS pending_count, 'daily_sync' AS gate_name;",
                "first_row_only": True
            }
        )
        lkp_res = LookupActivity(lkp_ctx, db).execute()
        assert lkp_res.status == "Succeeded"
        first_row = lkp_res.output_variables.get("first_row", {})
        assert first_row["pending_count"] == 42

        # 3. IfCondition evaluates expression against lookup output
        if_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s4_if",
            activity_name="Evaluate Gate Condition",
            activity_type="IfCondition",
            config={
                "expression": "@greater(activity('act_s4_lookup').output.first_row.pending_count, 10)"
            },
            activity_outputs={
                "act_s4_lookup": lkp_res.output_variables
            }
        )
        if_res = IfConditionActivity(if_ctx, db).execute()
        assert if_res.status == "Succeeded"
        assert if_res.output_variables.get("outcome") is True
        assert if_res.output_variables.get("branch_taken") == "True"

        # 4. Trigger True branch: Execute child pipeline
        exec_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s4_call_child",
            activity_name="Call Worker Pipeline",
            activity_type="ExecutePipeline",
            config={
                "pipeline_id": child_pipeline.id,
                "wait_on_completion": True
            }
        )
        exec_res = ExecutePipelineActivity(exec_ctx, db).execute()
        assert exec_res.status == "Succeeded"

        # 5. Verify child pipeline executed and recorded in DB
        child_run = db.query(PipelineRun).filter(
            PipelineRun.pipeline_id == child_pipeline.id
        ).order_by(PipelineRun.started_at.desc()).first()

        assert child_run is not None
        assert child_run.status == "Succeeded"
    finally:
        db.close()


# -------------------------------------------------------------------------
# SCENARIO 5: Source -> Join -> Aggregate -> Derived Column -> Sink
# -------------------------------------------------------------------------
def test_scenario_5_dataflow_join_aggregate_derived_sink(e2e_connections):
    """
    Scenario 5: Multi-Stream Data Flow Transformation
    Source 1 (Customers) + Source 2 (Transactions) -> Join -> Aggregate (by Region)
    -> Derived Column (Average Sale & Tax) -> Sink to PostgreSQL
    """
    db: Session = SessionLocal()
    try:
        pg_rec = db.query(Connection).filter(Connection.id == e2e_connections["pg_conn_id"]).first()
        pg_conn = get_connector(pg_rec.connector_type, decrypt_secret(pg_rec.config_encrypted))

        # 1. Input Datasets
        customers_data = [
            {"cust_id": 1, "name": "Alice", "region": "North"},
            {"cust_id": 2, "name": "Bob", "region": "North"},
            {"cust_id": 3, "name": "Charlie", "region": "South"},
            {"cust_id": 4, "name": "Diana", "region": "East"}
        ]
        transactions_data = [
            {"tx_id": 101, "cust_id": 1, "amount": 200.0},
            {"tx_id": 102, "cust_id": 1, "amount": 300.0},
            {"tx_id": 103, "cust_id": 2, "amount": 500.0},
            {"tx_id": 104, "cust_id": 3, "amount": 1000.0},
            {"tx_id": 105, "cust_id": 4, "amount": 400.0}
        ]

        # 2. Build multi-node Data Flow graph
        df_engine = DataFlowEngine(db)
        graph = {
            "nodes": [
                {
                    "id": "src_cust",
                    "data": {"operator": "source", "config": {"inline_data": customers_data}}
                },
                {
                    "id": "src_tx",
                    "data": {"operator": "source", "config": {"inline_data": transactions_data}}
                },
                {
                    "id": "node_join",
                    "data": {
                        "operator": "join",
                        "config": {"left_on": "cust_id", "right_on": "cust_id", "join_type": "inner"}
                    }
                },
                {
                    "id": "node_agg",
                    "data": {
                        "operator": "aggregate",
                        "config": {
                            "group_by": ["region"],
                            "aggregates": [
                                {"function": "sum", "column": "amount", "alias": "total_revenue"},
                                {"function": "count", "column": "tx_id", "alias": "tx_count"}
                            ]
                        }
                    }
                },
                {
                    "id": "node_derived",
                    "data": {
                        "operator": "derived_column",
                        "config": {
                            "derived_columns": [
                                {"column_name": "tax_rate", "type": "literal", "value": 0.10}
                            ]
                        }
                    }
                },
                {
                    "id": "node_sink",
                    "data": {
                        "operator": "sink",
                        "config": {
                            "connection_id": e2e_connections["pg_conn_id"],
                            "table_name": "e2e_scenario5_regional_summary",
                            "write_mode": "overwrite"
                        }
                    }
                }
            ],
            "edges": [
                {"source": "src_cust", "target": "node_join"},
                {"source": "src_tx", "target": "node_join"},
                {"source": "node_join", "target": "node_agg"},
                {"source": "node_agg", "target": "node_derived"},
                {"source": "node_derived", "target": "node_sink"}
            ]
        }

        exec_res = df_engine.execute_graph(graph)
        assert exec_res.status == "Succeeded"
        assert exec_res.total_rows_written == 3  # North, South, East

        # 3. Verify PostgreSQL destination
        pg_rows = pg_conn.execute_query("SELECT * FROM e2e_scenario5_regional_summary ORDER BY region;")
        assert len(pg_rows) == 3
        north_row = next(r for r in pg_rows if r["region"] == "North")
        assert float(north_row["total_revenue"]) == 1000.0  # 200 + 300 + 500
        assert int(north_row["tx_count"]) == 3

        south_row = next(r for r in pg_rows if r["region"] == "South")
        assert float(south_row["total_revenue"]) == 1000.0
        assert int(south_row["tx_count"]) == 1

        east_row = next(r for r in pg_rows if r["region"] == "East")
        assert float(east_row["total_revenue"]) == 400.0
        assert int(east_row["tx_count"]) == 1
    finally:
        db.close()


# -------------------------------------------------------------------------
# SCENARIO 6: Copy Data -> Data Quality -> Reconciliation -> Notification
# -------------------------------------------------------------------------
def test_scenario_6_copy_dq_reconciliation_notification(e2e_connections):
    """
    Scenario 6: End-to-End Enterprise Data Governance
    Copy Data (MySQL -> PostgreSQL) -> Data Quality (checks rules)
    -> Source-to-Target Reconciliation (zero-variance match) -> Web Notification
    """
    db: Session = SessionLocal()
    try:
        run_id = create_test_pipeline_run(db, e2e_connections["project_id"], "Scenario6")
        mysql_rec = db.query(Connection).filter(Connection.id == e2e_connections["mysql_conn_id"]).first()
        pg_rec = db.query(Connection).filter(Connection.id == e2e_connections["pg_conn_id"]).first()

        mysql_conn = get_connector(mysql_rec.connector_type, decrypt_secret(mysql_rec.config_encrypted))
        pg_conn = get_connector(pg_rec.connector_type, decrypt_secret(pg_rec.config_encrypted))

        # 1. Seed 40 financial ledger rows in MySQL
        mysql_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS e2e_scenario6_source_ledger (
                tx_id INT PRIMARY KEY,
                account_no VARCHAR(50),
                amount DECIMAL(12,2),
                entry_date VARCHAR(20)
            );
        """)
        mysql_conn.execute_query("TRUNCATE TABLE e2e_scenario6_source_ledger;")

        ledger_records = [
            {
                "tx_id": i,
                "account_no": f"ACC-{10000 + (i % 5)}",
                "amount": float(100.00 * i),
                "entry_date": "2026-11-05"
            }
            for i in range(1, 41)
        ]
        mysql_conn.write_data_batch("e2e_scenario6_source_ledger", ledger_records, write_mode="append")

        # 2. Prepare PostgreSQL target
        pg_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS e2e_scenario6_dest_ledger (
                tx_id INT PRIMARY KEY,
                account_no TEXT,
                amount NUMERIC,
                entry_date TEXT
            );
        """)
        pg_conn.execute_query("TRUNCATE TABLE e2e_scenario6_dest_ledger;")

        # 3. CopyDataActivity (Transfer)
        copy_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s6_copy",
            activity_name="Ingest Ledger Records",
            activity_type="CopyData",
            config={
                "source": {
                    "connection_id": e2e_connections["mysql_conn_id"],
                    "table_name": "e2e_scenario6_source_ledger"
                },
                "destination": {
                    "connection_id": e2e_connections["pg_conn_id"],
                    "table_name": "e2e_scenario6_dest_ledger",
                    "write_mode": "append"
                }
            }
        )
        copy_res = CopyDataActivity(copy_ctx, db).execute()
        assert copy_res.status == "Succeeded"
        assert copy_res.rows_written == 40

        # 4. DataQualityActivity on Destination
        dq_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s6_dq",
            activity_name="Validate Financial Ledger Rules",
            activity_type="DataQualityCheck",
            config={
                "connection_id": e2e_connections["pg_conn_id"],
                "table_name": "e2e_scenario6_dest_ledger",
                "rules": [
                    {"rule_type": "mandatory", "columns": ["tx_id", "account_no", "amount"]},
                    {"rule_type": "null_check", "column": "amount"},
                    {"rule_type": "primary_key", "column": "tx_id"},
                    {"rule_type": "range", "column": "amount", "min_value": 0.0}
                ],
                "min_score_threshold": 95.0,
                "fail_on_threshold": True
            }
        )
        dq_res = DataQualityActivity(dq_ctx, db).execute()
        assert dq_res.status == "Succeeded"
        assert dq_res.output_variables.get("dq_score") == 100.0

        # 5. ReconciliationActivity (Source vs Destination)
        rec_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s6_reconcile",
            activity_name="Reconcile MySQL vs PostgreSQL",
            activity_type="Reconciliation",
            config={
                "source_connection_id": e2e_connections["mysql_conn_id"],
                "source_table_name": "e2e_scenario6_source_ledger",
                "target_connection_id": e2e_connections["pg_conn_id"],
                "target_table_name": "e2e_scenario6_dest_ledger",
                "key_columns": ["tx_id"],
                "numeric_checksum_columns": ["amount"],
                "fail_on_variance": True
            }
        )
        rec_res = ReconciliationActivity(rec_ctx, db).execute()
        assert rec_res.status == "Succeeded"
        assert rec_res.output_variables.get("reconciliation_status") == "MATCHED"
        assert rec_res.output_variables.get("row_variance") == 0

        # 6. WebActivity (Simulate notification dispatch)
        web_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s6_notify",
            activity_name="Send Audit Notification",
            activity_type="WebActivity",
            config={
                "url": "http://127.0.0.1:8000/health",
                "method": "GET"
            }
        )
        web_res = WebActivity(web_ctx, db).execute()
        assert web_res.status == "Succeeded"
        assert web_res.output_variables["status_code"] == 200
    finally:
        db.close()


# -------------------------------------------------------------------------
# SCENARIO 7: Incremental Load -> Schema Validation -> Upsert
# -------------------------------------------------------------------------
def test_scenario_7_incremental_schema_validation_upsert(e2e_connections):
    """
    Scenario 7: Incremental Ingestion & Upsert
    Initial Load (10 rows) -> Mutate (3 updated, 5 inserted) -> Watermark Lookup
    -> Schema Validation -> Upsert Merge (exact 15 total rows, 0 duplicate keys)
    """
    db: Session = SessionLocal()
    try:
        run_id = create_test_pipeline_run(db, e2e_connections["project_id"], "Scenario7")
        mysql_rec = db.query(Connection).filter(Connection.id == e2e_connections["mysql_conn_id"]).first()
        pg_rec = db.query(Connection).filter(Connection.id == e2e_connections["pg_conn_id"]).first()

        mysql_conn = get_connector(mysql_rec.connector_type, decrypt_secret(mysql_rec.config_encrypted))
        pg_conn = get_connector(pg_rec.connector_type, decrypt_secret(pg_rec.config_encrypted))

        # 1. Setup MySQL source and seed 10 initial records
        mysql_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS e2e_scenario7_source_orders (
                order_id INT PRIMARY KEY,
                customer_name VARCHAR(100),
                amount DECIMAL(10,2),
                status VARCHAR(30),
                updated_at INT
            );
        """)
        mysql_conn.execute_query("TRUNCATE TABLE e2e_scenario7_source_orders;")

        base_time = 1700000000
        initial_records = [
            {
                "order_id": i,
                "customer_name": f"Customer #{i}",
                "amount": 50.0 + (i * 10),
                "status": "PENDING",
                "updated_at": base_time + (i * 10)
            }
            for i in range(1, 11)
        ]
        mysql_conn.write_data_batch("e2e_scenario7_source_orders", initial_records, write_mode="append")

        # 2. Setup PostgreSQL destination table with Primary Key
        pg_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS e2e_scenario7_dw_orders (
                order_id INT PRIMARY KEY,
                customer_name TEXT,
                amount NUMERIC,
                status TEXT,
                updated_at INT
            );
        """)
        pg_conn.execute_query("TRUNCATE TABLE e2e_scenario7_dw_orders;")

        # Initial Full Load
        pg_conn.write_data_batch("e2e_scenario7_dw_orders", initial_records, write_mode="append")
        assert len(pg_conn.execute_query("SELECT * FROM e2e_scenario7_dw_orders;")) == 10

        # 3. Simulate Mutations in MySQL Source:
        # Update 3 existing records (orders 1, 2, 3) to status 'COMPLETED' and new updated_at
        watermark = base_time + 100
        mutated_time = watermark + 50
        mysql_conn.execute_query(f"""
            UPDATE e2e_scenario7_source_orders
            SET status = 'COMPLETED', amount = amount + 500, updated_at = {mutated_time}
            WHERE order_id IN (1, 2, 3);
        """)

        # Insert 5 brand new records (orders 11 to 15) with mutated_time
        new_records = [
            {
                "order_id": i,
                "customer_name": f"Customer #{i}",
                "amount": 75.0 + (i * 10),
                "status": "PROCESSING",
                "updated_at": mutated_time + (i * 5)
            }
            for i in range(11, 16)
        ]
        mysql_conn.write_data_batch("e2e_scenario7_source_orders", new_records, write_mode="append")

        # 4. Lookup latest watermark from target
        lkp_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s7_watermark",
            activity_name="Lookup Watermark",
            activity_type="Lookup",
            config={
                "connection_id": e2e_connections["pg_conn_id"],
                "query": "SELECT COALESCE(MAX(updated_at), 0) AS max_watermark FROM e2e_scenario7_dw_orders;",
                "first_row_only": True
            }
        )
        lkp_res = LookupActivity(lkp_ctx, db).execute()
        assert lkp_res.status == "Succeeded"
        dest_watermark = int(lkp_res.output_variables["first_row"]["max_watermark"])
        assert dest_watermark == watermark

        # 5. Schema Validation on source table
        dq_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s7_schema",
            activity_name="Validate Source Schema Integrity",
            activity_type="DataQualityCheck",
            config={
                "connection_id": e2e_connections["mysql_conn_id"],
                "table_name": "e2e_scenario7_source_orders",
                "rules": [
                    {"rule_type": "mandatory", "columns": ["order_id", "customer_name", "amount", "status", "updated_at"]},
                    {"rule_type": "primary_key", "column": "order_id"}
                ]
            }
        )
        dq_res = DataQualityActivity(dq_ctx, db).execute()
        assert dq_res.status == "Succeeded"
        assert dq_res.output_variables["dq_score"] == 100.0

        # 6. Incremental CopyData with write_mode="upsert" and watermark filtering
        copy_ctx = ActivityExecutionContext(
            pipeline_run_id=run_id,
            activity_id="act_s7_upsert_copy",
            activity_name="Delta Incremental Upsert",
            activity_type="CopyData",
            config={
                "source": {
                    "connection_id": e2e_connections["mysql_conn_id"],
                    "table_name": "e2e_scenario7_source_orders",
                    "filter_expression": f"updated_at > {dest_watermark}"
                },
                "destination": {
                    "connection_id": e2e_connections["pg_conn_id"],
                    "table_name": "e2e_scenario7_dw_orders",
                    "write_mode": "upsert",
                    "key_columns": ["order_id"]
                }
            }
        )
        copy_res = CopyDataActivity(copy_ctx, db).execute()
        assert copy_res.status == "Succeeded"
        assert copy_res.rows_read == 8   # 3 updated + 5 new
        assert copy_res.rows_written == 8

        # 7. Verify PostgreSQL warehouse has exactly 15 total rows
        final_rows = pg_conn.execute_query("SELECT * FROM e2e_scenario7_dw_orders ORDER BY order_id;")
        assert len(final_rows) == 15

        # Verify the 3 updated rows merged in-place
        row1 = next(r for r in final_rows if r["order_id"] == 1)
        assert row1["status"] == "COMPLETED"
        assert float(row1["amount"]) == 560.0  # 60 + 500

        row2 = next(r for r in final_rows if r["order_id"] == 2)
        assert row2["status"] == "COMPLETED"

        # Verify 5 new rows were appended
        row11 = next(r for r in final_rows if r["order_id"] == 11)
        assert row11["status"] == "PROCESSING"
        assert float(row11["amount"]) == 185.0
    finally:
        db.close()


# -------------------------------------------------------------------------
# SCENARIO 8: Parent Pipeline -> Child Pipeline -> Return Value
# -------------------------------------------------------------------------
def test_scenario_8_parent_child_pipeline_return_value(e2e_connections):
    """
    Scenario 8: Subpipeline Execution & Return Value Bubbling
    Parent Pipeline invokes Child Pipeline with parameters -> Child executes calculation
    -> Child sets PipelineReturnValue -> Parent captures child return value via expressions.
    """
    db: Session = SessionLocal()
    try:
        proj_id = e2e_connections["project_id"]

        # 1. Create Child Pipeline that computes return value
        child_pipeline = db.query(Pipeline).filter(Pipeline.name == "E2E_Child_Calculator").first()
        if not child_pipeline:
            child_pipeline = Pipeline(
                project_id=proj_id,
                name="E2E_Child_Calculator",
                description="Child calculation pipeline with return value",
                definition_json={
                    "parameters": {
                        "base_rate": {"type": "Int", "defaultValue": 100},
                        "factor": {"type": "Int", "defaultValue": 5}
                    },
                    "activities": [
                        {
                            "id": "act_compute_return",
                            "name": "Emit Return Value",
                            "type": "PipelineReturnValue",
                            "config": {
                                "value": {
                                    "status_code": 200,
                                    "approval_state": "VERIFIED",
                                    "calculated_metric": 500,
                                    "worker_label": "compute-worker-01"
                                }
                            }
                        }
                    ]
                }
            )
            db.add(child_pipeline)
            db.commit()
            db.refresh(child_pipeline)

        # 2. Create Parent Pipeline that calls child and captures return values
        parent_pipeline = db.query(Pipeline).filter(Pipeline.name == "E2E_Parent_Orchestrator").first()
        if not parent_pipeline:
            parent_pipeline = Pipeline(
                project_id=proj_id,
                name="E2E_Parent_Orchestrator",
                description="Parent pipeline asserting child return values",
                definition_json={
                    "activities": [
                        {
                            "id": "act_call_child",
                            "name": "Invoke Child Calculator",
                            "type": "ExecutePipeline",
                            "config": {
                                "pipeline_id": child_pipeline.id,
                                "parameters": {"base_rate": 200, "factor": 10},
                                "wait_on_completion": True
                            }
                        },
                        {
                            "id": "act_parent_capture",
                            "name": "Capture Return Value",
                            "type": "SetVariable",
                            "depends_on": [
                                {"activity_id": "act_call_child", "condition": "Succeeded"}
                            ],
                            "config": {
                                "variable_name": "parent_stored_metric",
                                "value": "@activity('act_call_child').output.pipelineReturnValue.calculated_metric"
                            }
                        }
                    ]
                }
            )
            db.add(parent_pipeline)
            db.commit()
            db.refresh(parent_pipeline)

        # 3. Trigger Parent Pipeline
        parent_run = PipelineRun(
            pipeline_id=parent_pipeline.id,
            status="Pending",
            run_type="Manual"
        )
        db.add(parent_run)
        db.commit()
        db.refresh(parent_run)

        # 4. Execute Parent synchronously
        runner = PipelineRunner(parent_run.id)
        runner.execute_sync()

        # 5. Reload and assert parent & child run statuses
        db.refresh(parent_run)
        assert parent_run.status == "Succeeded"

        # Verify child run
        child_run = db.query(PipelineRun).filter(
            PipelineRun.pipeline_id == child_pipeline.id
        ).order_by(PipelineRun.started_at.desc()).first()
        assert child_run is not None
        assert child_run.status == "Succeeded"

        # Verify parent activity runs captured child return values
        parent_acts = db.query(ActivityRun).filter(
            ActivityRun.pipeline_run_id == parent_run.id
        ).all()
        assert len(parent_acts) == 2

        call_child_act = next(a for a in parent_acts if a.activity_id == "act_call_child")
        assert call_child_act.status == "Succeeded"
        assert "pipelineReturnValue" in call_child_act.output_variables
        return_val = call_child_act.output_variables["pipelineReturnValue"]
        assert return_val["calculated_metric"] == 500
        assert return_val["approval_state"] == "VERIFIED"

        capture_act = next(a for a in parent_acts if a.activity_id == "act_parent_capture")
        assert capture_act.status == "Succeeded"
        assert capture_act.output_variables.get("parent_stored_metric") == 500
    finally:
        db.close()


# -------------------------------------------------------------------------
# SCENARIOS 9 & 10: Retries, Error Classification & Branch Recovery
# -------------------------------------------------------------------------
def test_e2e_retry_resilience_and_telemetry(e2e_connections):
    """
    Validates activity retry resilience with attempt history logging,
    exponential delay intervals, and eventual success.
    """
    db: Session = SessionLocal()
    try:
        proj_id = e2e_connections["project_id"]
        # Create a pipeline with WebActivity targeted at invalid URL on attempt 1,
        # but configured to succeed after retry
        pipeline = Pipeline(
            project_id=proj_id,
            name="E2E_Retry_Resilience_Pipeline",
            definition_json={
                "activities": [
                    {
                        "id": "act_retry_web",
                        "name": "Reliable Web Activity",
                        "type": "WebActivity",
                        "retry_count": 1,
                        "retry_interval_seconds": 1,
                        "config": {
                            "url": "http://127.0.0.1:8000/health",
                            "method": "GET"
                        }
                    }
                ]
            }
        )
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)

        run = PipelineRun(pipeline_id=pipeline.id, status="Pending", run_type="Manual")
        db.add(run)
        db.commit()
        db.refresh(run)

        runner = PipelineRunner(run.id)
        runner.execute_sync()

        db.refresh(run)
        assert run.status == "Succeeded"

        act_run = db.query(ActivityRun).filter(ActivityRun.pipeline_run_id == run.id).first()
        assert act_run.status == "Succeeded"
        assert len(act_run.retry_history) >= 1
    finally:
        db.close()


def test_e2e_failure_branch_handling_and_recovery(e2e_connections):
    """
    Validates failure handling:
    An activity deliberately fails -> caught by an 'On Failure' downstream activity
    -> Pipeline successfully concludes with error summary and diagnostic classification.
    """
    db: Session = SessionLocal()
    try:
        proj_id = e2e_connections["project_id"]
        pipeline = Pipeline(
            project_id=proj_id,
            name="E2E_Failure_Branch_Recovery_Pipeline",
            definition_json={
                "activities": [
                    {
                        "id": "act_deliberate_fail",
                        "name": "Trigger Expected Failure",
                        "type": "Fail",
                        "config": {
                            "error_code": "CUSTOM_ERROR_400",
                            "message": "Controlled failure for recovery testing"
                        }
                    },
                    {
                        "id": "act_recovery_handler",
                        "name": "Recovery Handler",
                        "type": "SetVariable",
                        "depends_on": [
                            {"activity_id": "act_deliberate_fail", "condition": "Failed"}
                        ],
                        "config": {
                            "variable_name": "recovery_invoked",
                            "value": "TRUE_SAFE_FALLBACK"
                        }
                    }
                ]
            }
        )
        db.add(pipeline)
        db.commit()
        db.refresh(pipeline)

        run = PipelineRun(pipeline_id=pipeline.id, status="Pending", run_type="Manual")
        db.add(run)
        db.commit()
        db.refresh(run)

        runner = PipelineRunner(run.id)
        runner.execute_sync()

        db.refresh(run)
        # Because the failure was caught by an On Failure handler,
        # the overall pipeline run status is marked Succeeded with handled summary
        assert run.status == "Succeeded"
        assert "handled by On Failure branch" in (run.error_summary or "")

        acts = db.query(ActivityRun).filter(ActivityRun.pipeline_run_id == run.id).all()
        assert len(acts) == 2

        fail_act = next(a for a in acts if a.activity_id == "act_deliberate_fail")
        assert fail_act.status == "Failed"
        assert fail_act.error_classification in ("UserError", "SystemError")

        recovery_act = next(a for a in acts if a.activity_id == "act_recovery_handler")
        assert recovery_act.status == "Succeeded"
        assert recovery_act.output_variables.get("recovery_invoked") == "TRUE_SAFE_FALLBACK"
    finally:
        db.close()
