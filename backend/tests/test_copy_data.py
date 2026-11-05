import os
import tempfile
from backend.app.connectors.sqlite import SQLiteConnector


def test_sqlite_connector_copy_stream():
    # Create two temporary databases: source and target
    with tempfile.NamedTemporaryFile(suffix=".db") as src_file, tempfile.NamedTemporaryFile(suffix=".db") as dst_file:
        src_conn = SQLiteConnector({"database_path": src_file.name})
        dst_conn = SQLiteConnector({"database_path": dst_file.name})

        # Setup source data
        src_conn.execute_query("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                name TEXT,
                country TEXT,
                updated_at TEXT
            );
        """)
        src_conn.execute_query("""
            INSERT INTO customers VALUES 
            (1, 'Alice Smith', 'USA', '2026-01-01 10:00:00'),
            (2, 'Bob Jones', 'UK', '2026-01-02 11:00:00'),
            (3, 'Charlie Brown', 'Canada', '2026-01-03 12:00:00');
        """)

        # Discover columns
        cols = src_conn.discover_columns("customers")
        assert len(cols) == 4
        col_names = [c.name for c in cols]
        assert "customer_id" in col_names

        # Stream copy all records to destination
        stream = src_conn.read_data_stream("customers", batch_size=2)
        total_copied = 0
        for chunk in stream:
            written = dst_conn.write_data_batch(
                table_name="target_customers",
                records=chunk,
                write_mode="append",
                key_columns=["customer_id"],
                auto_create_table=True
            )
            total_copied += written

        assert total_copied == 3

        # Verify destination records
        res = dst_conn.execute_query("SELECT COUNT(*) as cnt FROM target_customers;")
        assert res[0]["cnt"] == 3

        # Test incremental watermark loading
        src_conn.execute_query("""
            INSERT INTO customers VALUES 
            (4, 'Diana Prince', 'Themyscira', '2026-01-05 15:00:00');
        """)

        # Watermark filter: updated_at > '2026-01-03 12:00:00'
        incremental_stream = src_conn.read_data_stream(
            "customers",
            watermark_column="updated_at",
            watermark_value="2026-01-03 12:00:00"
        )
        inc_records = []
        for chunk in incremental_stream:
            inc_records.extend(chunk)

        assert len(inc_records) == 1
        assert inc_records[0]["customer_id"] == 4
        assert inc_records[0]["name"] == "Diana Prince"

        # Upsert incremental record into destination
        dst_conn.write_data_batch(
            table_name="target_customers",
            records=inc_records,
            write_mode="upsert",
            key_columns=["customer_id"]
        )

        res2 = dst_conn.execute_query("SELECT COUNT(*) as cnt FROM target_customers;")
        assert res2[0]["cnt"] == 4
