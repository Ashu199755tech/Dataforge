#!/usr/bin/env python3
"""
DataFlow Enterprise — Milestone 1 End-to-End Verification Script
Tests real data ingestion:
  MySQL Source (port 3307) -> Copy Data Activity -> PostgreSQL Destination (port 5433)
"""

import sys
import os
import time
import json
import psycopg2
import pymysql

# Add root directory to pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import SessionLocal
from backend.app.models.workspace import Workspace, Project
from backend.app.models.connection import Connection
from backend.app.models.pipeline import Pipeline
from backend.app.models.execution import PipelineRun, ActivityRun, ExecutionLog
from backend.app.models.data_quality import DataQualityResult
from backend.app.core.security import encrypt_secret, decrypt_secret
from backend.app.connectors.factory import get_connector
from backend.app.execution.runner import PipelineRunner
from backend.app.execution.dag_engine import PipelineDAG


def run_e2e_verification():
    print("=" * 70)
    print("  DATAFLOW ENTERPRISE — MILESTONE 1 END-TO-END VERIFICATION")
    print("=" * 70)

    db = SessionLocal()

    try:
        # Reset source and destination tables for clean idempotent test
        with psycopg2.connect(host="127.0.0.1", port=5433, user="postgres", password="", dbname="postgres_target_warehouse") as pg_c:
            with pg_c.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS target_orders;")
            pg_c.commit()

        with pymysql.connect(host="127.0.0.1", port=3307, user="root", password="", database="mysql_source_erp") as my_c:
            with my_c.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS source_orders (
                        order_id INT PRIMARY KEY,
                        customer_id INT NOT NULL,
                        customer_name VARCHAR(100) NOT NULL,
                        product_category VARCHAR(50) NOT NULL,
                        total_amount DECIMAL(10, 2) NOT NULL,
                        order_status VARCHAR(30) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    );
                """)
                cur.execute("TRUNCATE TABLE source_orders;")
                cur.execute("""
                    INSERT INTO source_orders VALUES
                    (1001, 501, 'Acme Corp', 'Electronics', 1250.00, 'COMPLETED', '2026-01-01 10:00:00', '2026-01-01 10:00:00'),
                    (1002, 502, 'Global Logistics', 'Logistics', 450.50, 'COMPLETED', '2026-01-01 11:30:00', '2026-01-01 11:30:00'),
                    (1003, 503, 'Starlight Retail', 'Apparel', 89.99, 'PENDING', '2026-01-02 09:15:00', '2026-01-02 09:15:00'),
                    (1004, 504, 'Apex Technologies', 'Cloud Services', 3200.00, 'COMPLETED', '2026-01-02 14:00:00', '2026-01-02 14:00:00'),
                    (1005, 505, 'Nordic Solutions', 'Hardware', 740.25, 'PROCESSING', '2026-01-03 16:45:00', '2026-01-03 16:45:00');
                """)
            my_c.commit()
        project = db.query(Project).filter(Project.name == "Core Analytics & Ingestion").first()
        if not project:
            print("[FAIL] Default project not found!")
            return False
        print(f"[OK] Workspace & Project validated: '{project.name}' (ID: {project.id})")

        # Step 2: Register MySQL Source Connection
        mysql_cfg = {
            "host": "127.0.0.1",
            "port": 3307,
            "user": "root",
            "password": "",
            "database": "mysql_source_erp"
        }
        mysql_conn = db.query(Connection).filter(Connection.name == "MySQL ERP Source").first()
        if not mysql_conn:
            mysql_conn = Connection(
                project_id=project.id,
                name="MySQL ERP Source",
                connector_type="mysql",
                description="Production ERP transactional source database",
                config_encrypted=encrypt_secret(mysql_cfg),
                status="Unverified"
            )
            db.add(mysql_conn)
            db.commit()
            db.refresh(mysql_conn)
        print(f"[OK] MySQL Connection registered: '{mysql_conn.name}' (ID: {mysql_conn.id})")

        # Step 3: Register PostgreSQL Target Warehouse Connection
        pg_cfg = {
            "host": "127.0.0.1",
            "port": 5433,
            "user": "postgres",
            "password": "",
            "database": "postgres_target_warehouse"
        }
        pg_conn = db.query(Connection).filter(Connection.name == "PostgreSQL Warehouse Destination").first()
        if not pg_conn:
            pg_conn = Connection(
                project_id=project.id,
                name="PostgreSQL Warehouse Destination",
                connector_type="postgres",
                description="Enterprise Data Warehouse analytical target",
                config_encrypted=encrypt_secret(pg_cfg),
                status="Unverified"
            )
            db.add(pg_conn)
            db.commit()
            db.refresh(pg_conn)
        print(f"[OK] PostgreSQL Connection registered: '{pg_conn.name}' (ID: {pg_conn.id})")

        # Step 4: Test Connection Health
        print("\n--- Testing Connector Health ---")
        src_connector = get_connector("mysql", mysql_cfg)
        src_test = src_connector.test_connection()
        assert src_test.success, f"MySQL connection failed: {src_test.message}"
        print(f"[OK] MySQL test passed: {src_test.message} (Latency: {src_test.latency_ms}ms, Server: {src_test.server_version})")

        dst_connector = get_connector("postgres", pg_cfg)
        dst_test = dst_connector.test_connection()
        assert dst_test.success, f"PostgreSQL connection failed: {dst_test.message}"
        print(f"[OK] PostgreSQL test passed: {dst_test.message} (Latency: {dst_test.latency_ms}ms, Server: {dst_test.server_version})")

        # Step 5: Test Schema & Table Discovery
        print("\n--- Discovering Source Metadata ---")
        tables = src_connector.discover_tables("mysql_source_erp")
        print(f"[OK] Discovered {len(tables)} tables in MySQL: {[t.name for t in tables]}")
        cols = src_connector.discover_columns("source_orders", "mysql_source_erp")
        print(f"[OK] Discovered {len(cols)} columns in 'source_orders': {[c.name + ' (' + c.data_type + ')' for c in cols]}")

        # Step 6: Construct and Save Pipeline Definition (JSON)
        pipeline_def = {
            "parameters": {
                "batch_size": 2000,
                "environment": "production"
            },
            "variables": {
                "high_watermark": "1970-01-01 00:00:00"
            },
            "activities": [
                {
                    "id": "act_copy_orders",
                    "name": "Copy Orders from MySQL to PG",
                    "type": "CopyData",
                    "depends_on": [],
                    "retry_policy": {
                        "max_retries": 2,
                        "retry_interval_seconds": 1
                    },
                    "config": {
                        "source": {
                            "connection_id": mysql_conn.id,
                            "table_name": "source_orders",
                            "schema_name": "mysql_source_erp",
                            "batch_size": 1000,
                            "incremental": {
                                "mode": "watermark",
                                "column": "updated_at",
                                "watermark_value": "@variables('high_watermark')"
                            }
                        },
                        "destination": {
                            "connection_id": pg_conn.id,
                            "table_name": "target_orders",
                            "schema_name": "public",
                            "write_mode": "upsert",
                            "key_columns": ["order_id"],
                            "auto_create_table": True
                        },
                        "column_mappings": [
                            {"source_column": "order_id", "target_column": "order_id"},
                            {"source_column": "customer_id", "target_column": "customer_id"},
                            {"source_column": "customer_name", "target_column": "customer_name"},
                            {"source_column": "product_category", "target_column": "product_category"},
                            {"source_column": "total_amount", "target_column": "total_amount"},
                            {"source_column": "order_status", "target_column": "order_status"},
                            {"source_column": "created_at", "target_column": "created_at"},
                            {"source_column": "updated_at", "target_column": "updated_at"}
                        ]
                    }
                },
                {
                    "id": "act_validate_quality",
                    "name": "Validate Target Orders Quality",
                    "type": "DataQualityCheck",
                    "depends_on": [
                        {"activity_id": "act_copy_orders", "condition": "Succeeded"}
                    ],
                    "config": {
                        "connection_id": pg_conn.id,
                        "table_name": "target_orders",
                        "rules": [
                            {"rule_type": "NotNull", "column": "order_id", "threshold_percent": 100.0},
                            {"rule_type": "NotNull", "column": "customer_name", "threshold_percent": 100.0},
                            {"rule_type": "PositiveNumeric", "column": "total_amount", "threshold_percent": 100.0},
                            {"rule_type": "Unique", "column": "order_id", "threshold_percent": 100.0}
                        ],
                        "fail_pipeline_on_error": True
                    }
                }
            ]
        }

        # Validate DAG
        dag = PipelineDAG(pipeline_def["activities"])
        print("\n--- DAG Structural Validation ---")
        print(f"[OK] Validated DAG: {len(pipeline_def['activities'])} nodes. Root activities: {dag.get_root_activities()}")

        pipeline = db.query(Pipeline).filter(Pipeline.name == "MySQL-to-PostgreSQL Orders Ingestion").first()
        if not pipeline:
            pipeline = Pipeline(
                project_id=project.id,
                name="MySQL-to-PostgreSQL Orders Ingestion",
                description="Visual ingestion pipeline extracting ERP orders from MySQL into analytical PostgreSQL warehouse",
                definition_json=pipeline_def,
                status="Published",
                current_version=1
            )
            db.add(pipeline)
        else:
            pipeline.definition_json = pipeline_def
            pipeline.current_version += 1
        db.commit()
        db.refresh(pipeline)
        print(f"[OK] Pipeline persisted in PostgreSQL: '{pipeline.name}' (ID: {pipeline.id})")

        # Step 7: EXECUTE RUN #1 (Full Ingestion)
        print("\n" + "=" * 50)
        print("  TRIGGERING RUN #1: INITIAL FULL INGESTION")
        print("=" * 50)
        run_1 = PipelineRun(
            pipeline_id=pipeline.id,
            run_type="Manual",
            status="Pending",
            parameters={"env": "prod"}
        )
        db.add(run_1)
        db.commit()
        db.refresh(run_1)

        runner = PipelineRunner(run_1.id)
        runner.execute_sync()

        # Check Run #1 Results
        db.refresh(run_1)
        print(f"\n[RUN #1 RESULT] Status: {run_1.status}")
        print(f"Activities: Total {run_1.total_activities}, Succeeded: {run_1.succeeded_activities}, Failed: {run_1.failed_activities}")
        print(f"Metrics: Rows Read: {run_1.total_rows_read}, Rows Written: {run_1.total_rows_written}, Duration: {run_1.duration_seconds}s")
        assert run_1.status == "Succeeded", f"Run #1 failed: {run_1.error_summary}"

        # Verify Target Database Data directly in PostgreSQL
        with psycopg2.connect(host="127.0.0.1", port=5433, user="postgres", password="", dbname="postgres_target_warehouse") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM target_orders;")
                pg_count = cur.fetchone()[0]
                cur.execute("SELECT order_id, customer_name, total_amount, order_status, updated_at FROM target_orders ORDER BY order_id;")
                pg_rows = cur.fetchall()

        print(f"\n[OK] Direct SQL check on PostgreSQL: Found {pg_count} records in 'target_orders'!")
        for r in pg_rows:
            print(f"   -> Order #{r[0]}: {r[1]} | ${r[2]} | Status: {r[3]} | Updated: {r[4]}")
        assert pg_count == 5, f"Expected 5 records, found {pg_count}"

        # Check Data Quality Results for Run #1
        dq_results = db.query(DataQualityResult).filter(DataQualityResult.pipeline_run_id == run_1.id).all()
        print(f"\n[OK] Data Quality Results: {len(dq_results)} rules evaluated.")
        for dqr in dq_results:
            print(f"   -> [{dqr.status}] {dqr.rule_name}: Score {dqr.pass_percentage}% (Failed: {dqr.failed_records_count})")
            assert dqr.status == "Passed"

        # Step 8: EXECUTE RUN #2 (Incremental Ingestion with Delta Records)
        print("\n" + "=" * 50)
        print("  TRIGGERING RUN #2: INCREMENTAL WATERMARK INGESTION")
        print("=" * 50)
        print("Inserting 2 new records into MySQL source with updated timestamps...")
        mysql_conn_raw = pymysql.connect(host="127.0.0.1", port=3307, user="root", password="", database="mysql_source_erp")
        with mysql_conn_raw.cursor() as cur:
            cur.execute("""
                INSERT INTO source_orders VALUES 
                (1006, 506, 'Horizon Media Group', 'Advertising', 1850.75, 'COMPLETED', '2026-01-04 10:00:00', '2026-01-04 10:00:00'),
                (1007, 507, 'Quantum Bio Labs', 'Healthcare', 9400.00, 'PENDING', '2026-01-04 11:30:00', '2026-01-04 11:30:00');
            """)
        mysql_conn_raw.commit()
        mysql_conn_raw.close()
        print("[OK] New records inserted into MySQL source.")

        # Update pipeline watermark variable to only ingest records after 2026-01-03 16:45:00
        new_def = json.loads(json.dumps(pipeline.definition_json))
        new_def["variables"]["high_watermark"] = "2026-01-03 16:45:00"
        pipeline.definition_json = new_def
        db.commit()

        run_2 = PipelineRun(
            pipeline_id=pipeline.id,
            run_type="Scheduled",
            status="Pending",
            parameters={"env": "prod"}
        )
        db.add(run_2)
        db.commit()
        db.refresh(run_2)

        runner_2 = PipelineRunner(run_2.id)
        runner_2.execute_sync()

        db.refresh(run_2)
        print(f"\n[RUN #2 RESULT] Status: {run_2.status}")
        print(f"Metrics: Delta Rows Read: {run_2.total_rows_read}, Delta Rows Written: {run_2.total_rows_written}, Duration: {run_2.duration_seconds}s")
        assert run_2.status == "Succeeded", f"Run #2 failed: {run_2.error_summary}"
        assert run_2.total_rows_written == 2, f"Expected exactly 2 delta records written, got {run_2.total_rows_written}"

        # Verify Total Count in PostgreSQL is now 7
        with psycopg2.connect(host="127.0.0.1", port=5433, user="postgres", password="", dbname="postgres_target_warehouse") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM target_orders;")
                final_pg_count = cur.fetchone()[0]

        print(f"\n[OK] Final Target Record Count in PostgreSQL: {final_pg_count} rows!")
        assert final_pg_count == 7, f"Expected total 7 records in PG, found {final_pg_count}"

        # Fetch and display Activity Logs
        print("\n--- Sample Activity Execution Logs from Run #1 ---")
        logs = db.query(ExecutionLog).join(ActivityRun).filter(ActivityRun.pipeline_run_id == run_1.id).limit(6).all()
        for log in logs:
            print(f"[{log.level}] {log.timestamp.strftime('%H:%M:%S')} - {log.message}")

        print("\n" + "=" * 70)
        print("  [SUCCESS] ALL MILESTONE 1 END-TO-END CRITERIA MET AND VERIFIED!")
        print("=" * 70)
        return True

    finally:
        db.close()


if __name__ == "__main__":
    success = run_e2e_verification()
    sys.exit(0 if success else 1)
