import os
import tempfile
import shutil
import io
import pytest
import boto3
from moto import mock_aws

from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.connectors.storage.aws_s3 import AmazonS3Connector
from backend.app.connectors.sqlite import SQLiteConnector
from backend.app.transfer.models import CancellationToken, TransferProgress
from backend.app.transfer.engine import TransferEngine
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.models.connection import Connection
from backend.app.models.workspace import Project
from backend.app.core.database import SessionLocal
from backend.app.core.security import encrypt_secret


@pytest.fixture
def moto_s3_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        s3.create_bucket(Bucket="dataforge-cloud-source")
        s3.create_bucket(Bucket="dataforge-cloud-dest")
        yield s3


@pytest.fixture
def temp_hybrid_env():
    temp_dir = tempfile.mkdtemp(prefix="dataforge_hybrid_")
    db_file = os.path.join(temp_dir, "test_hybrid.db")
    storage_dir = os.path.join(temp_dir, "storage")
    os.makedirs(storage_dir, exist_ok=True)

    db_conn = SQLiteConnector({"database_path": db_file})
    storage_conn = LocalStorageConnector({"base_path": storage_dir})

    # Initialize sqlite table
    db_conn.execute_query("""
        CREATE TABLE source_products (
            product_id INTEGER PRIMARY KEY,
            name TEXT,
            price REAL,
            category TEXT
        );
    """)
    db_conn.execute_query("""
        INSERT INTO source_products VALUES 
        (1, 'Laptop', 1299.99, 'Electronics'),
        (2, 'Keyboard', 79.50, 'Accessories'),
        (3, 'Monitor', 349.00, 'Electronics');
    """)

    yield db_conn, storage_conn, temp_dir, db_file, storage_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


class TestCrossCloudTransfers:
    def test_cross_cloud_s3_to_local_binary(self, moto_s3_env, temp_hybrid_env):
        _, storage_conn, _, _, _ = temp_hybrid_env

        s3_conn = AmazonS3Connector({
            "bucket": "dataforge-cloud-source",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })

        content = b"user_id,action,ts\n101,LOGIN,2026-05-10\n102,LOGOUT,2026-05-10\n"
        s3_conn.write_file("dataforge-cloud-source", "audit.csv", content)

        config = {
            "source": {"container": "dataforge-cloud-source", "path": "audit.csv"},
            "destination": {"container": "local-lake", "path": "audit.csv"},
            "source_settings": {"format": "csv"},
            "destination_settings": {"format": "csv"},
            "advanced": {"checksum_algorithm": "md5"}
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=s3_conn,
            dst_connector=storage_conn,
            src_container="dataforge-cloud-source",
            src_path="audit.csv",
            dst_container="local-lake",
            dst_path="audit.csv",
            config=config
        )

        assert res.success is True
        assert res.bytes_transferred == len(content)
        assert res.checksum_verified is True

        local_read = storage_conn.read_file("local-lake", "audit.csv")
        assert local_read == content

    def test_cross_cloud_local_to_s3_transcoding_parquet(self, moto_s3_env, temp_hybrid_env):
        _, storage_conn, _, _, _ = temp_hybrid_env

        s3_conn = AmazonS3Connector({
            "bucket": "dataforge-cloud-dest",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })

        csv_payload = b"id,city,temp\n1,Seattle,15.2\n2,Austin,28.5\n"
        storage_conn.write_file("inbound", "weather.csv", csv_payload)

        config = {
            "source": {"container": "inbound", "path": "weather.csv"},
            "destination": {"container": "dataforge-cloud-dest", "path": "weather.parquet", "format": "parquet"},
            "source_settings": {"format": "csv", "has_header": True},
            "destination_settings": {"format": "parquet", "compression": "snappy"}
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=storage_conn,
            dst_connector=s3_conn,
            src_container="inbound",
            src_path="weather.csv",
            dst_container="dataforge-cloud-dest",
            dst_path="weather.parquet",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 2
        assert res.bytes_transferred > 0

        # Read back from S3
        s3_bytes = s3_conn.read_file("dataforge-cloud-dest", "weather.parquet")
        assert len(s3_bytes) > 0

    def test_empty_file_cross_cloud_transfer(self, moto_s3_env, temp_hybrid_env):
        _, storage_conn, _, _, _ = temp_hybrid_env

        s3_conn = AmazonS3Connector({
            "bucket": "dataforge-cloud-source",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })

        s3_conn.write_file("dataforge-cloud-source", "empty.txt", b"")

        config = {
            "source": {"container": "dataforge-cloud-source", "path": "empty.txt"},
            "destination": {"container": "local-empty", "path": "empty.txt"},
            "source_settings": {"format": "text"},
            "destination_settings": {"format": "text"}
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=s3_conn,
            dst_connector=storage_conn,
            src_container="dataforge-cloud-source",
            src_path="empty.txt",
            dst_container="local-empty",
            dst_path="empty.txt",
            config=config
        )

        assert res.success is True
        assert res.bytes_transferred == 0

    def test_cross_cloud_missing_source_fails(self, moto_s3_env, temp_hybrid_env):
        _, storage_conn, _, _, _ = temp_hybrid_env

        s3_conn = AmazonS3Connector({
            "bucket": "dataforge-cloud-source",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })

        config = {
            "source": {"container": "dataforge-cloud-source", "path": "does_not_exist.parquet"},
            "destination": {"container": "local-dest", "path": "out.parquet"}
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=s3_conn,
            dst_connector=storage_conn,
            src_container="dataforge-cloud-source",
            src_path="does_not_exist.parquet",
            dst_container="local-dest",
            dst_path="out.parquet",
            config=config
        )

        assert res.success is False
        assert any(term in res.error_message.lower() for term in ["not_found", "not found", "nosuchkey", "404", "does not exist"])


class TestHybridTransfers:
    def test_database_to_cloud_csv(self, temp_hybrid_env):
        db_conn, storage_conn, _, _, _ = temp_hybrid_env

        config = {
            "source": {"table_name": "source_products"},
            "destination": {"container": "exports", "path": "products.csv", "format": "csv"},
            "destination_settings": {"format": "csv", "has_header": True}
        }

        res = TransferEngine.execute_database_to_storage(
            db_connector=db_conn,
            dst_connector=storage_conn,
            src_table="source_products",
            dst_container="exports",
            dst_path="products.csv",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 3
        assert res.bytes_transferred > 0

        data = storage_conn.read_file("exports", "products.csv").decode("utf-8")
        assert "Laptop" in data
        assert "Keyboard" in data

    def test_database_to_cloud_parquet(self, temp_hybrid_env):
        db_conn, storage_conn, _, _, _ = temp_hybrid_env

        config = {
            "source": {"table_name": "source_products"},
            "destination": {"container": "lake", "path": "products.parquet", "format": "parquet"},
            "destination_settings": {"format": "parquet", "compression": "snappy"}
        }

        res = TransferEngine.execute_database_to_storage(
            db_connector=db_conn,
            dst_connector=storage_conn,
            src_table="source_products",
            dst_container="lake",
            dst_path="products.parquet",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 3

        parquet_bytes = storage_conn.read_file("lake", "products.parquet")
        assert len(parquet_bytes) > 0

    def test_cloud_to_database_append(self, temp_hybrid_env):
        db_conn, storage_conn, _, _, _ = temp_hybrid_env

        # Seed cloud file
        csv_content = b"product_id,name,price,category\n4,Smartphone,899.0,Electronics\n5,Headphones,199.99,Accessories\n"
        storage_conn.write_file("staging", "new_products.csv", csv_content)

        config = {
            "source": {"container": "staging", "path": "new_products.csv"},
            "destination": {"table_name": "source_products", "write_mode": "append"},
            "source_settings": {"format": "csv", "has_header": True}
        }

        res = TransferEngine.execute_storage_to_database(
            src_connector=storage_conn,
            db_connector=db_conn,
            src_container="staging",
            src_path="new_products.csv",
            dst_table="source_products",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 2

        # Verify database has 5 rows
        rows = db_conn.execute_query("SELECT COUNT(*) as cnt FROM source_products;")
        assert rows[0]["cnt"] == 5

    def test_cloud_to_database_column_mapping(self, temp_hybrid_env):
        db_conn, storage_conn, _, _, _ = temp_hybrid_env

        # Create target table with different column names
        db_conn.execute_query("""
            CREATE TABLE target_inventory (
                item_sku TEXT PRIMARY KEY,
                item_label TEXT,
                unit_price REAL
            );
        """)

        csv_content = b"sku,title,cost\nSKU-99,Monitor Arm,49.99\nSKU-100,USB Hub,25.00\n"
        storage_conn.write_file("inbound", "inventory.csv", csv_content)

        config = {
            "source": {"container": "inbound", "path": "inventory.csv"},
            "destination": {"table_name": "target_inventory", "write_mode": "append"},
            "source_settings": {"format": "csv", "has_header": True},
            "column_mappings": [
                {"source_column": "sku", "destination_column": "item_sku"},
                {"source_column": "title", "destination_column": "item_label"},
                {"source_column": "cost", "destination_column": "unit_price"}
            ]
        }

        res = TransferEngine.execute_storage_to_database(
            src_connector=storage_conn,
            db_connector=db_conn,
            src_container="inbound",
            src_path="inventory.csv",
            dst_table="target_inventory",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 2

        rows = db_conn.execute_query("SELECT item_sku, item_label FROM target_inventory;")
        assert len(rows) == 2
        assert rows[0]["item_sku"] == "SKU-99"
        assert rows[0]["item_label"] == "Monitor Arm"

    def test_database_to_cloud_with_filter(self, temp_hybrid_env):
        db_conn, storage_conn, _, _, _ = temp_hybrid_env

        config = {
            "source": {
                "table_name": "source_products",
                "filter_expression": "price > 200"
            },
            "destination": {"container": "filtered_lake", "path": "expensive.csv", "format": "csv"},
            "destination_settings": {"format": "csv", "has_header": True}
        }

        res = TransferEngine.execute_database_to_storage(
            db_connector=db_conn,
            dst_connector=storage_conn,
            src_table="source_products",
            dst_container="filtered_lake",
            dst_path="expensive.csv",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 2
        content = storage_conn.read_file("filtered_lake", "expensive.csv").decode("utf-8")
        assert "Laptop" in content
        assert "Monitor" in content
        assert "Keyboard" not in content

    def test_cloud_to_database_upsert(self, temp_hybrid_env):
        db_conn, storage_conn, _, _, _ = temp_hybrid_env

        csv_content = b"product_id,name,price,category\n2,Mechanical Keyboard,119.50,Accessories\n4,Webcam,69.99,Electronics\n"
        storage_conn.write_file("staging", "upsert_products.csv", csv_content)

        config = {
            "source": {"container": "staging", "path": "upsert_products.csv"},
            "destination": {
                "table_name": "source_products",
                "write_mode": "upsert",
                "key_columns": ["product_id"]
            },
            "source_settings": {"format": "csv", "has_header": True}
        }

        res = TransferEngine.execute_storage_to_database(
            src_connector=storage_conn,
            db_connector=db_conn,
            src_container="staging",
            src_path="upsert_products.csv",
            dst_table="source_products",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 2

        # Verify product 2 was updated and product 4 was inserted
        rows = db_conn.execute_query("SELECT product_id, name, price FROM source_products ORDER BY product_id;")
        assert len(rows) == 4
        assert rows[1]["product_id"] == 2
        assert rows[1]["name"] == "Mechanical Keyboard"
        assert rows[1]["price"] == 119.50
        assert rows[3]["product_id"] == 4
        assert rows[3]["name"] == "Webcam"

    def test_hybrid_cancellation_during_ingestion(self, temp_hybrid_env):
        db_conn, storage_conn, _, _, _ = temp_hybrid_env
        token = CancellationToken()
        token.cancel("Cancelled before transfer")

        config = {
            "source": {"table_name": "source_products"},
            "destination": {"container": "cancelled", "path": "out.csv", "format": "csv"}
        }

        res = TransferEngine.execute_database_to_storage(
            db_connector=db_conn,
            dst_connector=storage_conn,
            src_table="source_products",
            dst_container="cancelled",
            dst_path="out.csv",
            config=config,
            cancellation_token=token
        )

        assert res.success is False
        assert res.cancelled is True


class TestCopyDataActivityHybridExecution:
    def test_copy_data_activity_db_to_storage_end_to_end(self, temp_hybrid_env):
        db_conn, storage_conn, _, db_file, storage_dir = temp_hybrid_env
        db = SessionLocal()

        try:
            proj = db.query(Project).first()
            if not proj:
                proj = Project(name="Hybrid Project")
                db.add(proj)
                db.commit()
                db.refresh(proj)

            db_conn_rec = Connection(
                project_id=proj.id,
                name="SQLite ERP",
                connector_type="sqlite",
                config_encrypted=encrypt_secret({"database_path": db_file})
            )
            storage_conn_rec = Connection(
                project_id=proj.id,
                name="Storage Destination",
                connector_type="local_storage",
                config_encrypted=encrypt_secret({"base_path": storage_dir})
            )
            db.add_all([db_conn_rec, storage_conn_rec])
            db.commit()

            config = {
                "source": {
                    "connection_id": db_conn_rec.id,
                    "table_name": "source_products"
                },
                "destination": {
                    "connection_id": storage_conn_rec.id,
                    "container": "dw-outbound",
                    "path": "products.csv",
                    "format": "csv"
                },
                "destination_settings": {"format": "csv", "has_header": True}
            }

            ctx = ActivityExecutionContext(
                pipeline_run_id="run_hybrid_1",
                activity_id="act_db_to_storage",
                activity_name="Extract_Products_To_Lake",
                activity_type="CopyData",
                config=config
            )

            activity = CopyDataActivity(ctx, db)
            res = activity.execute()

            assert res.status == "Succeeded"
            assert res.rows_written == 3
            assert res.bytes_processed > 0

            # Verify file exists in storage
            copied = storage_conn.read_file("dw-outbound", "products.csv")
            assert b"Laptop" in copied

            # Cleanup
            db.delete(db_conn_rec)
            db.delete(storage_conn_rec)
            db.commit()
        finally:
            db.close()

    def test_copy_data_activity_hybrid_storage_to_db(self, temp_hybrid_env):
        db_conn, storage_conn, _, db_file, storage_dir = temp_hybrid_env
        db = SessionLocal()

        try:
            proj = db.query(Project).first()
            if not proj:
                proj = Project(name="Hybrid Project")
                db.add(proj)
                db.commit()
                db.refresh(proj)

            storage_conn_rec = Connection(
                project_id=proj.id,
                name="Storage Source",
                connector_type="local_storage",
                config_encrypted=encrypt_secret({"base_path": storage_dir})
            )
            db_conn_rec = Connection(
                project_id=proj.id,
                name="SQLite Destination",
                connector_type="sqlite",
                config_encrypted=encrypt_secret({"database_path": db_file})
            )
            db.add_all([storage_conn_rec, db_conn_rec])
            db.commit()

            # Create table in SQLite
            db_conn.execute_query("""
                CREATE TABLE customers (
                    cust_id INTEGER PRIMARY KEY,
                    cust_name TEXT
                );
            """)

            # Seed file in storage
            storage_conn.write_file("lake", "customers.csv", b"cust_id,cust_name\n1,Alice\n2,Bob\n")

            config = {
                "source": {
                    "connection_id": storage_conn_rec.id,
                    "container": "lake",
                    "path": "customers.csv"
                },
                "destination": {
                    "connection_id": db_conn_rec.id,
                    "table_name": "customers",
                    "write_mode": "append"
                },
                "source_settings": {"format": "csv", "has_header": True}
            }

            ctx = ActivityExecutionContext(
                pipeline_run_id="run_hybrid_2",
                activity_id="act_storage_to_db",
                activity_name="Ingest_Customers_From_Lake",
                activity_type="CopyData",
                config=config
            )

            activity = CopyDataActivity(ctx, db)
            res = activity.execute()

            assert res.status == "Succeeded"
            assert res.rows_written == 2

            rows = db_conn.execute_query("SELECT COUNT(*) as cnt FROM customers;")
            assert rows[0]["cnt"] == 2

            db.delete(storage_conn_rec)
            db.delete(db_conn_rec)
            db.commit()
        finally:
            db.close()

    def test_copy_data_activity_cloud_to_cloud_end_to_end(self, moto_s3_env, temp_hybrid_env):
        _, storage_conn, _, _, storage_dir = temp_hybrid_env
        s3 = moto_s3_env
        s3.put_object(Bucket="dataforge-cloud-source", Key="e2e.jsonl", Body=b'{"id": 1, "val": "A"}\n{"id": 2, "val": "B"}\n')

        db = SessionLocal()
        try:
            proj = db.query(Project).first()
            if not proj:
                proj = Project(name="Cloud Project")
                db.add(proj)
                db.commit()
                db.refresh(proj)

            s3_conn_rec = Connection(
                project_id=proj.id,
                name="S3 Source",
                connector_type="aws_s3",
                config_encrypted=encrypt_secret({
                    "bucket": "dataforge-cloud-source",
                    "region_name": "us-east-1",
                    "access_key_id": "testing",
                    "secret_access_key": "testing"
                })
            )
            local_conn_rec = Connection(
                project_id=proj.id,
                name="Local Dest",
                connector_type="local_storage",
                config_encrypted=encrypt_secret({"base_path": storage_dir})
            )
            db.add_all([s3_conn_rec, local_conn_rec])
            db.commit()

            config = {
                "source": {
                    "connection_id": s3_conn_rec.id,
                    "container": "dataforge-cloud-source",
                    "path": "e2e.jsonl"
                },
                "destination": {
                    "connection_id": local_conn_rec.id,
                    "container": "cloud_landing",
                    "path": "e2e.jsonl"
                },
                "source_settings": {"format": "jsonl"},
                "destination_settings": {"format": "jsonl"}
            }

            ctx = ActivityExecutionContext(
                pipeline_run_id="run_c2c_1",
                activity_id="act_s3_to_local",
                activity_name="Replicate_S3_To_Local",
                activity_type="CopyData",
                config=config
            )

            activity = CopyDataActivity(ctx, db)
            res = activity.execute()

            assert res.status == "Succeeded"
            assert res.bytes_processed > 0

            # Verify local file
            dest_content = storage_conn.read_file("cloud_landing", "e2e.jsonl")
            assert b'"val": "A"' in dest_content

            db.delete(s3_conn_rec)
            db.delete(local_conn_rec)
            db.commit()
        finally:
            db.close()
