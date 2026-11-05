import pytest
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.connection import Connection
from backend.app.models.workspace import Workspace, Project
from backend.app.core.security import encrypt_secret
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.get_metadata import GetMetadataActivity
from backend.app.activities.delete_data import DeleteDataActivity
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.connectors.factory import get_connector


@pytest.fixture(scope="module")
def setup_test_connections():
    """Sets up live PostgreSQL and MySQL test connections in the test database."""
    db: Session = SessionLocal()
    try:
        proj = db.query(Project).first()
        proj_id = proj.id if proj else "proj_test"

        # 1. PostgreSQL Target Warehouse Connection
        pg_conn = db.query(Connection).filter(Connection.name == "Test_PG_Target").first()
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
                name="Test_PG_Target",
                connector_type="PostgreSQL",
                config_encrypted=encrypt_secret(pg_config)
            )
            db.add(pg_conn)
            db.commit()
            db.refresh(pg_conn)

        # 2. MySQL Source ERP Connection
        mysql_conn = db.query(Connection).filter(Connection.name == "Test_MySQL_Source").first()
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
                name="Test_MySQL_Source",
                connector_type="MySQL",
                config_encrypted=encrypt_secret(mysql_config)
            )
            db.add(mysql_conn)
            db.commit()
            db.refresh(mysql_conn)

        yield {"pg_conn_id": pg_conn.id, "mysql_conn_id": mysql_conn.id}
    finally:
        db.close()


def test_get_metadata_activity(setup_test_connections):
    """Verifies that GetMetadataActivity inspects table existence, structure, and row counts."""
    db: Session = SessionLocal()
    try:
        mysql_conn_id = setup_test_connections["mysql_conn_id"]

        from backend.app.core.security import decrypt_secret
        mysql_rec = db.query(Connection).filter(Connection.id == mysql_conn_id).first()
        mysql_conn = get_connector(mysql_rec.connector_type, decrypt_secret(mysql_rec.config_encrypted))

        # Setup test table
        mysql_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS test_meta_customers (
                customer_id INT PRIMARY KEY,
                name VARCHAR(100),
                email VARCHAR(100),
                status VARCHAR(20)
            );
        """)
        mysql_conn.execute_query("TRUNCATE TABLE test_meta_customers;")
        mysql_conn.execute_query("""
            INSERT INTO test_meta_customers (customer_id, name, email, status) VALUES 
            (1, 'Alice Smith', 'alice@corp.com', 'ACTIVE'),
            (2, 'Bob Jones', 'bob@corp.com', 'ACTIVE'),
            (3, 'Charlie Brown', 'charlie@corp.com', 'INACTIVE');
        """)

        # 1. Existing table
        ctx = ActivityExecutionContext(
            pipeline_run_id="run_meta_test",
            activity_id="act_get_meta",
            activity_name="Inspect Test Customers",
            activity_type="GetMetadata",
            config={
                "connection_id": mysql_conn_id,
                "table_name": "test_meta_customers"
            }
        )
        activity = GetMetadataActivity(ctx, db)
        res = activity.execute()

        assert res.status == "Succeeded"
        assert res.output_variables["exists"] is True
        assert res.output_variables["rowCount"] == 3
        assert res.output_variables["columnCount"] == 4

        cols = [c["name"] for c in res.output_variables["structure"]]
        assert "customer_id" in cols
        assert "name" in cols
        assert "email" in cols

        # 2. Non-existent table returns exists=False
        ctx_missing = ActivityExecutionContext(
            pipeline_run_id="run_meta_test",
            activity_id="act_get_meta_missing",
            activity_name="Inspect Missing Table",
            activity_type="GetMetadata",
            config={
                "connection_id": mysql_conn_id,
                "table_name": "non_existent_table_9999"
            }
        )
        res_missing = GetMetadataActivity(ctx_missing, db).execute()
        assert res_missing.status == "Succeeded"
        assert res_missing.output_variables["exists"] is False
        assert res_missing.output_variables["rowCount"] == 0
    finally:
        db.close()


def test_delete_data_conditional_and_truncate(setup_test_connections):
    """Verifies DeleteDataActivity with both conditional deletion and table truncation."""
    db: Session = SessionLocal()
    try:
        pg_conn_id = setup_test_connections["pg_conn_id"]

        # Setup test table in PostgreSQL
        pg_conn_record = db.query(Connection).filter(Connection.id == pg_conn_id).first()
        from backend.app.core.security import decrypt_secret
        pg_conn = get_connector(pg_conn_record.connector_type, decrypt_secret(pg_conn_record.config_encrypted))

        pg_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS test_delete_staging (
                id INT PRIMARY KEY,
                category VARCHAR(50),
                amount NUMERIC
            );
        """)
        pg_conn.execute_query("TRUNCATE TABLE test_delete_staging;")
        pg_conn.execute_query("""
            INSERT INTO test_delete_staging (id, category, amount) VALUES 
            (1, 'ACTIVE', 100),
            (2, 'OBSOLETE', 200),
            (3, 'OBSOLETE', 300),
            (4, 'ACTIVE', 400);
        """)

        # 1. Test Conditional Deletion
        del_ctx = ActivityExecutionContext(
            pipeline_run_id="run_del_test",
            activity_id="act_delete_conditional",
            activity_name="Delete Obsolete Records",
            activity_type="DeleteData",
            config={
                "connection_id": pg_conn_id,
                "table_name": "test_delete_staging",
                "delete_mode": "conditional",
                "filter_expr": "category = 'OBSOLETE'"
            }
        )
        del_act = DeleteDataActivity(del_ctx, db)
        del_res = del_act.execute()

        assert del_res.status == "Succeeded"
        assert del_res.output_variables["rows_deleted"] == 2

        # Verify 2 active rows remain
        meta_ctx = ActivityExecutionContext(
            pipeline_run_id="run_del_test",
            activity_id="act_meta_verify",
            activity_name="Verify Remaining Rows",
            activity_type="GetMetadata",
            config={
                "connection_id": pg_conn_id,
                "table_name": "test_delete_staging"
            }
        )
        meta_act = GetMetadataActivity(meta_ctx, db)
        meta_res = meta_act.execute()
        assert meta_res.output_variables["rowCount"] == 2

        # 2. Test Table Truncation
        trunc_ctx = ActivityExecutionContext(
            pipeline_run_id="run_del_test",
            activity_id="act_delete_trunc",
            activity_name="Truncate Staging",
            activity_type="DeleteData",
            config={
                "connection_id": pg_conn_id,
                "table_name": "test_delete_staging",
                "delete_mode": "truncate"
            }
        )
        trunc_act = DeleteDataActivity(trunc_ctx, db)
        trunc_res = trunc_act.execute()
        assert trunc_res.status == "Succeeded"

        # Verify 0 rows remain
        meta_res2 = meta_act.execute()
        assert meta_res2.output_variables["rowCount"] == 0
    finally:
        db.close()


def test_acceptance_scenario_mysql_to_postgres(setup_test_connections):
    """
    Mandatory Acceptance Scenario:
    MySQL -> GetMetadata -> DeleteData (truncate destination) -> Copy Data -> GetMetadata (verify destination)
    Records must actually be transferred and verified.
    """
    db: Session = SessionLocal()
    try:
        mysql_conn_id = setup_test_connections["mysql_conn_id"]
        pg_conn_id = setup_test_connections["pg_conn_id"]

        from backend.app.core.security import decrypt_secret
        mysql_rec = db.query(Connection).filter(Connection.id == mysql_conn_id).first()
        pg_rec = db.query(Connection).filter(Connection.id == pg_conn_id).first()

        mysql_conn = get_connector(mysql_rec.connector_type, decrypt_secret(mysql_rec.config_encrypted))
        pg_conn = get_connector(pg_rec.connector_type, decrypt_secret(pg_rec.config_encrypted))

        # 1. Seed 50 test products in MySQL source
        mysql_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS phase2_source_inventory (
                item_id INT PRIMARY KEY,
                sku VARCHAR(100),
                unit_price DECIMAL(10,2),
                stock_quantity INT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
        """)
        mysql_conn.execute_query("TRUNCATE TABLE phase2_source_inventory;")

        # Populate batch
        test_items = [
            {"item_id": i, "sku": f"SKU-{1000 + i}", "unit_price": 19.99 + i, "stock_quantity": 10 + (i * 2)}
            for i in range(1, 51)
        ]
        mysql_conn.write_data_batch("phase2_source_inventory", test_items, write_mode="append")

        # 2. GetMetadata on Source: verify 50 rows exist
        src_meta_ctx = ActivityExecutionContext(
            pipeline_run_id="run_acceptance",
            activity_id="act_src_meta",
            activity_name="Discover Source Count",
            activity_type="GetMetadata",
            config={
                "connection_id": mysql_conn_id,
                "table_name": "phase2_source_inventory"
            }
        )
        src_meta_res = GetMetadataActivity(src_meta_ctx, db).execute()
        assert src_meta_res.output_variables["rowCount"] == 50

        # 3. DeleteData on Destination: clean target table
        pg_conn.execute_query("""
            CREATE TABLE IF NOT EXISTS phase2_dest_inventory (
                item_id INT PRIMARY KEY,
                sku VARCHAR(100),
                unit_price NUMERIC,
                stock_quantity INT,
                last_updated TIMESTAMP
            );
        """)
        clean_ctx = ActivityExecutionContext(
            pipeline_run_id="run_acceptance",
            activity_id="act_clean_dst",
            activity_name="Clean Target Staging",
            activity_type="DeleteData",
            config={
                "connection_id": pg_conn_id,
                "table_name": "phase2_dest_inventory",
                "delete_mode": "truncate"
            }
        )
        DeleteDataActivity(clean_ctx, db).execute()

        # 4. CopyData: MySQL -> PostgreSQL with pre_copy_script & column mappings
        copy_ctx = ActivityExecutionContext(
            pipeline_run_id="run_acceptance",
            activity_id="act_copy_pipeline",
            activity_name="Transfer Inventory to Warehouse",
            activity_type="CopyData",
            config={
                "source": {
                    "connection_id": mysql_conn_id,
                    "table_name": "phase2_source_inventory",
                    "batch_size": 25
                },
                "destination": {
                    "connection_id": pg_conn_id,
                    "table_name": "phase2_dest_inventory",
                    "write_mode": "append"
                },
                "column_mappings": [
                    {"source_column": "item_id", "target_column": "item_id"},
                    {"source_column": "sku", "target_column": "sku"},
                    {"source_column": "unit_price", "target_column": "unit_price"},
                    {"source_column": "stock_quantity", "target_column": "stock_quantity"},
                    {"source_column": "last_updated", "target_column": "last_updated"}
                ]
            }
        )
        copy_res = CopyDataActivity(copy_ctx, db).execute()
        assert copy_res.status == "Succeeded"
        assert copy_res.rows_read == 50
        assert copy_res.rows_written == 50

        # 5. GetMetadata on Destination: verify exact 50 rows arrived
        dst_meta_ctx = ActivityExecutionContext(
            pipeline_run_id="run_acceptance",
            activity_id="act_dst_meta",
            activity_name="Verify Destination Count",
            activity_type="GetMetadata",
            config={
                "connection_id": pg_conn_id,
                "table_name": "phase2_dest_inventory"
            }
        )
        dst_meta_res = GetMetadataActivity(dst_meta_ctx, db).execute()
        assert dst_meta_res.output_variables["rowCount"] == 50

        # 6. Verify row values in PostgreSQL directly
        pg_rows = pg_conn.execute_query("SELECT item_id, sku, stock_quantity FROM phase2_dest_inventory ORDER BY item_id LIMIT 5;")
        assert len(pg_rows) == 5
        assert pg_rows[0]["item_id"] == 1
        assert pg_rows[0]["sku"] == "SKU-1001"
        assert pg_rows[0]["stock_quantity"] == 12

    finally:
        db.close()
