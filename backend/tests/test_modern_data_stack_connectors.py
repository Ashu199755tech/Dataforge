import pytest
import os
import tempfile
import polars as pl

import backend.app.connectors.factory
from backend.app.connectors.factory import get_connector
from backend.app.connectors.duckdb import DuckDBConnector
from backend.app.connectors.bigquery import BigQueryConnector
from backend.app.connectors.redshift import RedshiftConnector


# ==========================================
# 1. DuckDB In-Process Analytical Engine Tests
# ==========================================

def test_duckdb_connector_registration():
    """Verify DuckDB connector registration in connector factory."""
    connector = get_connector("duckdb", {"database_path": ":memory:"})
    assert isinstance(connector, DuckDBConnector)
    assert connector.database_path == ":memory:"


def test_duckdb_connection_test():
    """Test DuckDB test_connection returns version and success."""
    connector = DuckDBConnector({"database_path": ":memory:"})
    res = connector.test_connection()
    assert res.success is True
    assert "DuckDB" in res.server_version
    assert res.latency_ms >= 0


def test_duckdb_schema_and_table_discovery():
    """Test discovering schemas, tables, and column metadata in DuckDB."""
    connector = DuckDBConnector({"database_path": ":memory:"})
    
    # Create test tables in DuckDB
    connector.execute_query("CREATE SCHEMA staging;")
    connector.execute_query("CREATE TABLE staging.products (sku VARCHAR PRIMARY KEY, price DOUBLE, stock INT);")
    connector.execute_query("INSERT INTO staging.products VALUES ('SKU1', 19.99, 100), ('SKU2', 49.50, 40);")

    schemas = connector.discover_schemas()
    assert "main" in schemas
    assert "staging" in schemas

    tables = connector.discover_tables("staging")
    tbl_names = [t.name for t in tables]
    assert "products" in tbl_names

    cols = connector.discover_columns("products", "staging")
    col_names = [c.name for c in cols]
    assert "sku" in col_names
    assert "price" in col_names
    assert "stock" in col_names


def test_duckdb_read_stream_and_write_batch_append_overwrite_upsert():
    """Test DuckDB streaming reads and batch writes (append, overwrite, upsert)."""
    connector = DuckDBConnector({"database_path": ":memory:"})

    records = [
        {"user_id": 1, "username": "alice", "score": 90.5},
        {"user_id": 2, "username": "bob", "score": 75.0}
    ]

    # 1. Append Mode
    rows_written = connector.write_data_batch("user_scores", records, write_mode="append")
    assert rows_written == 2

    # Verify rows via stream
    stream = list(connector.read_data_stream("user_scores", batch_size=1))
    assert len(stream) == 2
    assert stream[0][0]["username"] == "alice"

    # 2. Overwrite Mode
    overwrite_records = [{"user_id": 3, "username": "charlie", "score": 99.0}]
    connector.write_data_batch("user_scores", overwrite_records, write_mode="overwrite")
    stream_ov = list(connector.read_data_stream("user_scores"))
    assert len(stream_ov[0]) == 1
    assert stream_ov[0][0]["username"] == "charlie"

    # 3. Upsert / Merge Mode
    upsert_records = [
        {"user_id": 3, "username": "charlie_updated", "score": 100.0},  # Update
        {"user_id": 4, "username": "diana", "score": 88.0}              # Insert
    ]
    connector.write_data_batch("user_scores", upsert_records, write_mode="upsert", key_columns=["user_id"])
    stream_up = list(connector.read_data_stream("user_scores"))
    all_users = {r["user_id"]: r["username"] for r in stream_up[0]}
    assert all_users[3] == "charlie_updated"
    assert all_users[4] == "diana"
    assert len(all_users) == 2


def test_duckdb_direct_parquet_query():
    """Test DuckDB querying Parquet files directly with zero copy."""
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f_pq:
        pq_path = f_pq.name

    try:
        df = pl.DataFrame({
            "sensor_id": ["S1", "S2", "S3"],
            "temp_c": [22.4, 25.1, 19.8]
        })
        df.write_parquet(pq_path)

        connector = DuckDBConnector({"database_path": ":memory:"})
        query = f"SELECT sensor_id, temp_c * 1.8 + 32 AS temp_f FROM read_parquet('{pq_path}') WHERE temp_c > 20"
        rows = connector.execute_query(query)
        assert len(rows) == 2
        sensor_ids = {r["sensor_id"] for r in rows}
        assert "S1" in sensor_ids
        assert "S2" in sensor_ids
    finally:
        if os.path.exists(pq_path):
            os.remove(pq_path)


# ==========================================
# 2. Google Cloud BigQuery Connector Tests
# ==========================================

def test_bigquery_connector_registration():
    """Verify BigQuery connector is registered in factory."""
    config = {
        "project_id": "corp-gcp-prod",
        "dataset_id": "analytics",
        "mock_mode": True
    }
    connector = get_connector("bigquery", config)
    assert isinstance(connector, BigQueryConnector)
    assert connector.project_id == "corp-gcp-prod"
    assert connector.dataset_id == "analytics"


def test_bigquery_connection_test():
    """Test BigQuery connection validation under mock and param check modes."""
    bad_conn = BigQueryConnector({"mock_mode": False})
    res_bad = bad_conn.test_connection()
    assert res_bad.success is False
    assert "requires 'project_id'" in res_bad.message

    good_conn = BigQueryConnector({
        "project_id": "corp-analytics-lake",
        "dataset_id": "marts",
        "mock_mode": True
    })
    res_good = good_conn.test_connection()
    assert res_good.success is True
    assert "Connected to Google BigQuery" in res_good.message
    assert res_good.server_version == "Google BigQuery v2"


def test_bigquery_schema_table_column_discovery():
    """Test BigQuery discovering datasets, tables, and columns."""
    connector = BigQueryConnector({
        "project_id": "corp-gcp-analytics",
        "dataset_id": "marketing",
        "mock_mode": True,
        "_mock_tables": {
            "campaign_performance": [
                {"campaign_id": "CMP101", "clicks": 5400, "spend": 1250.75},
                {"campaign_id": "CMP102", "clicks": 8200, "spend": 2100.00}
            ]
        }
    })

    schemas = connector.discover_schemas()
    assert "analytics" in schemas
    assert "marketing" in schemas

    tables = connector.discover_tables("marketing")
    t_names = [t.name for t in tables]
    assert "campaign_performance" in t_names

    cols = connector.discover_columns("campaign_performance", "marketing")
    c_names = [c.name for c in cols]
    assert "campaign_id" in c_names
    assert "clicks" in c_names
    assert "spend" in c_names


def test_bigquery_read_stream_and_batch_write():
    """Test BigQuery streaming read and batch writes."""
    connector = BigQueryConnector({
        "project_id": "gcp-prod-lake",
        "dataset_id": "finance",
        "mock_mode": True
    })

    records = [
        {"txn_id": "T1", "amount": 500.0},
        {"txn_id": "T2", "amount": 850.0}
    ]

    # Append write
    cnt_append = connector.write_data_batch("transactions", records, write_mode="append")
    assert cnt_append == 2
    assert len(connector._mock_tables["transactions"]) == 2

    # Streaming read
    stream = list(connector.read_data_stream("transactions", batch_size=1))
    assert len(stream) == 2

    # Upsert write
    upsert_records = [
        {"txn_id": "T2", "amount": 900.0},  # Update
        {"txn_id": "T3", "amount": 350.0}   # Insert
    ]
    connector.write_data_batch("transactions", upsert_records, write_mode="upsert", key_columns=["txn_id"])
    assert len(connector._mock_tables["transactions"]) == 3
    amt_map = {r["txn_id"]: r["amount"] for r in connector._mock_tables["transactions"]}
    assert amt_map["T2"] == 900.0
    assert amt_map["T3"] == 350.0


# ==========================================
# 3. AWS Redshift Connector Tests
# ==========================================

def test_redshift_connector_registration():
    """Verify Redshift connector registration in factory."""
    config = {
        "host": "redshift-cluster.us-east-1.redshift.amazonaws.com",
        "port": 5439,
        "database": "dev",
        "user": "awsuser",
        "mock_mode": True
    }
    connector = get_connector("redshift", config)
    assert isinstance(connector, RedshiftConnector)
    assert connector.port == 5439
    assert connector.database == "dev"


def test_redshift_connection_test():
    """Test Redshift connection validation under mock and param check modes."""
    bad_conn = RedshiftConnector({"mock_mode": False})
    res_bad = bad_conn.test_connection()
    assert res_bad.success is False
    assert "requires 'host', 'database', and 'user'" in res_bad.message

    good_conn = RedshiftConnector({
        "cluster_identifier": "analytics-dw-cluster",
        "database": "reporting",
        "user": "master",
        "mock_mode": True
    })
    res_good = good_conn.test_connection()
    assert res_good.success is True
    assert "Connected to Amazon Redshift" in res_good.message
    assert "PostgreSQL 8.0.2" in res_good.server_version


def test_redshift_schema_table_column_discovery():
    """Test Redshift schema, table, and column metadata discovery."""
    connector = RedshiftConnector({
        "host": "dw.aws.com",
        "database": "dwh",
        "user": "etl",
        "schema": "marts",
        "mock_mode": True,
        "_mock_tables": {
            "dim_stores": [
                {"store_id": 1, "city": "Seattle", "region": "Pacific"},
                {"store_id": 2, "city": "Austin", "region": "South"}
            ]
        }
    })

    schemas = connector.discover_schemas()
    assert "public" in schemas
    assert "marts" in schemas

    tables = connector.discover_tables("marts")
    tbl_names = [t.name for t in tables]
    assert "dim_stores" in tbl_names

    cols = connector.discover_columns("dim_stores", "marts")
    c_names = [c.name for c in cols]
    assert "store_id" in c_names
    assert "city" in c_names
    assert "region" in c_names


def test_redshift_streaming_read_and_batch_write():
    """Test Redshift streaming reads and append/upsert writes."""
    connector = RedshiftConnector({
        "host": "redshift.dw.local",
        "database": "sales_db",
        "user": "analyst",
        "mock_mode": True
    })

    records = [
        {"item_id": 101, "sales": 40},
        {"item_id": 102, "sales": 60}
    ]

    # Append
    written = connector.write_data_batch("daily_sales", records, write_mode="append")
    assert written == 2

    # Streaming read
    stream = list(connector.read_data_stream("daily_sales", batch_size=1))
    assert len(stream) == 2

    # Upsert
    upsert_records = [
        {"item_id": 102, "sales": 75},
        {"item_id": 103, "sales": 20}
    ]
    connector.write_data_batch("daily_sales", upsert_records, write_mode="upsert", key_columns=["item_id"])
    assert len(connector._mock_tables["daily_sales"]) == 3
    sales_map = {r["item_id"]: r["sales"] for r in connector._mock_tables["daily_sales"]}
    assert sales_map[102] == 75
    assert sales_map[103] == 20
