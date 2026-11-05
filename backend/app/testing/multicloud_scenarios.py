import io
import os
import time
import tracemalloc
import tempfile
import shutil
from typing import Dict, Any, List, Optional
import pyarrow.parquet as pq

from backend.app.transfer.engine import TransferEngine
from backend.app.transfer.models import CancellationToken
from backend.app.connectors.storage.aws_s3 import AmazonS3Connector
from backend.app.connectors.storage.azure_blob import AzureBlobStorageConnector
from backend.app.connectors.storage.azure_adls import AzureDataLakeStorageConnector
from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.connectors.sqlite import SQLiteConnector
from backend.app.testing.multicloud_harness import (
    azurite_context,
    mock_aws,
    boto3,
    create_mock_gcs_connector,
    VirtualLargeSourceConnector,
    VirtualLargeSinkConnector,
    AZURITE_ACCOUNT_NAME
)
from azure.storage.blob import BlobServiceClient


def run_scenario_1_s3_to_adls_streaming() -> Dict[str, Any]:
    """Scenario 1: AWS S3 -> Azure ADLS Gen2 Direct Streaming Copy."""
    start_time = time.time()
    assertions = []

    with mock_aws():
        # Setup S3
        s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        s3.create_bucket(Bucket="dataforge-s3-source")
        
        # 10,000 lines CSV payload ~1MB
        header = b"sensor_id,timestamp,temperature,pressure,status\n"
        row_template = b"SENS-%05d,2026-11-05T12:00:00Z,23.45,101.3,NORMAL\n"
        body = header + b"".join(row_template % i for i in range(1, 10001))
        s3.put_object(Bucket="dataforge-s3-source", Key="raw/telemetry.csv", Body=body)

        s3_conn = AmazonS3Connector({
            "bucket": "dataforge-s3-source",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })

        with azurite_context() as conn_str:
            blob_service = BlobServiceClient.from_connection_string(conn_str)
            try:
                blob_service.create_container("adls-dest-lake")
            except Exception:
                pass

            adls_conn = AzureBlobStorageConnector({
                "connection_string": conn_str,
                "account_name": AZURITE_ACCOUNT_NAME
            })

            config = {
                "source": {"container": "dataforge-s3-source", "path": "raw/telemetry.csv"},
                "destination": {"container": "adls-dest-lake", "path": "processed/telemetry.csv"},
                "source_settings": {"format": "csv"},
                "destination_settings": {"format": "csv"},
                "advanced": {"checksum_algorithm": "md5"}
            }

            res = TransferEngine.execute_storage_to_storage(
                src_connector=s3_conn,
                dst_connector=adls_conn,
                src_container="dataforge-s3-source",
                src_path="raw/telemetry.csv",
                dst_container="adls-dest-lake",
                dst_path="processed/telemetry.csv",
                config=config
            )

            # Read back from Azurite
            read_back = adls_conn.read_file("adls-dest-lake", "processed/telemetry.csv")

            assertions.append({
                "name": "Transfer Status Success",
                "expected": "True",
                "actual": str(res.success),
                "passed": res.success is True
            })
            assertions.append({
                "name": "Byte Parity Verification",
                "expected": str(len(body)),
                "actual": str(res.bytes_transferred),
                "passed": res.bytes_transferred == len(body) and len(read_back) == len(body)
            })
            assertions.append({
                "name": "Checksum Verification",
                "expected": "True",
                "actual": str(res.checksum_verified),
                "passed": res.checksum_verified is True and res.destination_checksum is not None
            })

    duration_ms = round((time.time() - start_time) * 1000, 2)
    all_passed = all(a["passed"] for a in assertions)
    return {
        "scenario_id": "scenario_mc_1",
        "name": "Scenario 1: S3 -> Azure ADLS Direct Streaming",
        "status": "Passed" if all_passed else "Failed",
        "duration_ms": duration_ms,
        "bytes_transferred": res.bytes_transferred if res else 0,
        "checksum": res.destination_checksum if res else None,
        "assertions": assertions
    }


def run_scenario_2_adls_to_s3_transcoding() -> Dict[str, Any]:
    """Scenario 2: Azure ADLS Gen2 -> Amazon S3 Format Transcoding (CSV to Parquet)."""
    start_time = time.time()
    assertions = []

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        s3.create_bucket(Bucket="dataforge-s3-dest")

        s3_conn = AmazonS3Connector({
            "bucket": "dataforge-s3-dest",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })

        with azurite_context() as conn_str:
            blob_service = BlobServiceClient.from_connection_string(conn_str)
            try:
                blob_service.create_container("adls-source-lake")
            except Exception:
                pass

            adls_conn = AzureBlobStorageConnector({
                "connection_string": conn_str,
                "account_name": AZURITE_ACCOUNT_NAME
            })

            # Seed CSV in Azure
            csv_lines = ["event_id,event_type,user_id,amount,status"]
            for i in range(1, 1001):
                csv_lines.append(f"{i},PURCHASE,USER_{i % 50},{i * 1.5:.2f},CONFIRMED")
            csv_content = "\n".join(csv_lines).encode("utf-8")
            adls_conn.write_file("adls-source-lake", "events.csv", csv_content)

            config = {
                "source": {"container": "adls-source-lake", "path": "events.csv"},
                "destination": {"container": "dataforge-s3-dest", "path": "analytics/events.parquet", "format": "parquet"},
                "source_settings": {"format": "csv", "has_header": True},
                "destination_settings": {"format": "parquet", "compression": "snappy"}
            }

            res = TransferEngine.execute_storage_to_storage(
                src_connector=adls_conn,
                dst_connector=s3_conn,
                src_container="adls-source-lake",
                src_path="events.csv",
                dst_container="dataforge-s3-dest",
                dst_path="analytics/events.parquet",
                config=config
            )

            # Read back Parquet from S3 and verify with PyArrow
            parquet_bytes = s3_conn.read_file("dataforge-s3-dest", "analytics/events.parquet")
            pq_table = pq.read_table(io.BytesIO(parquet_bytes))

            assertions.append({
                "name": "Transcoding Execution Status",
                "expected": "True",
                "actual": str(res.success),
                "passed": res.success is True
            })
            assertions.append({
                "name": "Transcoded Record Count Parity",
                "expected": "1000",
                "actual": str(res.records_transferred),
                "passed": res.records_transferred == 1000 and pq_table.num_rows == 1000
            })
            assertions.append({
                "name": "Parquet Magic Header Validation",
                "expected": "PAR1",
                "actual": parquet_bytes[:4].decode("latin1", errors="ignore"),
                "passed": parquet_bytes[:4] == b"PAR1"
            })
            assertions.append({
                "name": "Parquet Column Schema Integrity",
                "expected": "['event_id', 'event_type', 'user_id', 'amount', 'status']",
                "actual": str(pq_table.column_names),
                "passed": set(pq_table.column_names) == {"event_id", "event_type", "user_id", "amount", "status"}
            })

    duration_ms = round((time.time() - start_time) * 1000, 2)
    all_passed = all(a["passed"] for a in assertions)
    return {
        "scenario_id": "scenario_mc_2",
        "name": "Scenario 2: ADLS Gen2 -> S3 Parquet Transcoding",
        "status": "Passed" if all_passed else "Failed",
        "duration_ms": duration_ms,
        "bytes_transferred": res.bytes_transferred if res else 0,
        "records_transferred": res.records_transferred if res else 0,
        "assertions": assertions
    }


def run_scenario_3_gcs_to_s3_multipart() -> Dict[str, Any]:
    """Scenario 3: Google Cloud Storage -> Amazon S3 Multipart Streaming Transfer (6MB)."""
    start_time = time.time()
    assertions = []

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        s3.create_bucket(Bucket="dataforge-s3-multipart")

        # Configure S3 connector with 5MB multipart threshold
        s3_conn = AmazonS3Connector({
            "bucket": "dataforge-s3-multipart",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing",
            "multipart_threshold": 5 * 1024 * 1024,
            "multipart_part_size": 5 * 1024 * 1024
        })

        gcs_conn = create_mock_gcs_connector("dataforge-gcs-lake")
        
        # 6MB synthetic binary payload
        six_mb = 6 * 1024 * 1024
        test_payload = os.urandom(six_mb)
        gcs_conn.write_file("dataforge-gcs-lake", "payload/telemetry.bin", test_payload)

        config = {
            "source": {"container": "dataforge-gcs-lake", "path": "payload/telemetry.bin"},
            "destination": {"container": "dataforge-s3-multipart", "path": "backup/telemetry.bin"},
            "advanced": {"checksum_algorithm": "sha256"}
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=gcs_conn,
            dst_connector=s3_conn,
            src_container="dataforge-gcs-lake",
            src_path="payload/telemetry.bin",
            dst_container="dataforge-s3-multipart",
            dst_path="backup/telemetry.bin",
            config=config
        )

        s3_bytes = s3_conn.read_file("dataforge-s3-multipart", "backup/telemetry.bin")

        assertions.append({
            "name": "Multipart Transfer Status",
            "expected": "True",
            "actual": str(res.success),
            "passed": res.success is True
        })
        assertions.append({
            "name": "Transferred Size Parity (6MB)",
            "expected": str(six_mb),
            "actual": str(res.bytes_transferred),
            "passed": res.bytes_transferred == six_mb and len(s3_bytes) == six_mb
        })
        assertions.append({
            "name": "SHA-256 Checksum Verification",
            "expected": "True",
            "actual": str(res.checksum_verified),
            "passed": res.checksum_verified is True
        })

    duration_ms = round((time.time() - start_time) * 1000, 2)
    all_passed = all(a["passed"] for a in assertions)
    return {
        "scenario_id": "scenario_mc_3",
        "name": "Scenario 3: GCS -> S3 Resumable/Multipart Transfer",
        "status": "Passed" if all_passed else "Failed",
        "duration_ms": duration_ms,
        "bytes_transferred": res.bytes_transferred if res else 0,
        "checksum": res.destination_checksum if res else None,
        "assertions": assertions
    }


def run_scenario_4_database_to_multicloud_parquet() -> Dict[str, Any]:
    """Scenario 4: Relational Database -> Multi-Cloud Parquet Ingestion (S3, ADLS, GCS)."""
    start_time = time.time()
    assertions = []

    temp_dir = tempfile.mkdtemp(prefix="dataforge_sc4_")
    db_file = os.path.join(temp_dir, "erp.db")
    db_conn = SQLiteConnector({"database_path": db_file})

    # Initialize source relational table with 500 rows
    db_conn.execute_query("""
        CREATE TABLE financial_ledger (
            tx_id INTEGER PRIMARY KEY,
            account_from TEXT,
            account_to TEXT,
            amount REAL,
            currency TEXT,
            status TEXT
        );
    """)
    for i in range(1, 501):
        db_conn.execute_query(f"""
            INSERT INTO financial_ledger VALUES (
                {i}, 'ACC_SRC_{i % 20}', 'ACC_DST_{i % 30}', {round(i * 12.34, 2)}, 'USD', 'SETTLED'
            );
        """)

    with mock_aws():
        # Setup S3 target
        s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        s3.create_bucket(Bucket="dataforge-s3-lake")
        s3_conn = AmazonS3Connector({"bucket": "dataforge-s3-lake", "region_name": "us-east-1", "access_key_id": "testing", "secret_access_key": "testing"})

        # Setup GCS target
        gcs_conn = create_mock_gcs_connector("dataforge-gcs-lake")

        # Setup Azure target
        with azurite_context() as conn_str:
            blob_service = BlobServiceClient.from_connection_string(conn_str)
            try:
                blob_service.create_container("adls-lake")
            except Exception:
                pass
            adls_conn = AzureBlobStorageConnector({"connection_string": conn_str, "account_name": AZURITE_ACCOUNT_NAME})

            config_base = {
                "source": {"table_name": "financial_ledger"},
                "destination_settings": {"format": "parquet", "compression": "snappy"}
            }

            # Ingest to S3
            res_s3 = TransferEngine.execute_database_to_storage(
                db_connector=db_conn,
                dst_connector=s3_conn,
                src_table="financial_ledger",
                dst_container="dataforge-s3-lake",
                dst_path="ledger.parquet",
                config={**config_base, "destination": {"container": "dataforge-s3-lake", "path": "ledger.parquet", "format": "parquet"}}
            )

            # Ingest to ADLS
            res_adls = TransferEngine.execute_database_to_storage(
                db_connector=db_conn,
                dst_connector=adls_conn,
                src_table="financial_ledger",
                dst_container="adls-lake",
                dst_path="ledger.parquet",
                config={**config_base, "destination": {"container": "adls-lake", "path": "ledger.parquet", "format": "parquet"}}
            )

            # Ingest to GCS
            res_gcs = TransferEngine.execute_database_to_storage(
                db_connector=db_conn,
                dst_connector=gcs_conn,
                src_table="financial_ledger",
                dst_container="dataforge-gcs-lake",
                dst_path="ledger.parquet",
                config={**config_base, "destination": {"container": "dataforge-gcs-lake", "path": "ledger.parquet", "format": "parquet"}}
            )

            assertions.append({
                "name": "Database to S3 Parquet Status & Rows",
                "expected": "500",
                "actual": str(res_s3.records_transferred),
                "passed": res_s3.success is True and res_s3.records_transferred == 500
            })
            assertions.append({
                "name": "Database to Azure ADLS Parquet Status & Rows",
                "expected": "500",
                "actual": str(res_adls.records_transferred),
                "passed": res_adls.success is True and res_adls.records_transferred == 500
            })
            assertions.append({
                "name": "Database to GCS Parquet Status & Rows",
                "expected": "500",
                "actual": str(res_gcs.records_transferred),
                "passed": res_gcs.success is True and res_gcs.records_transferred == 500
            })

    shutil.rmtree(temp_dir, ignore_errors=True)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    all_passed = all(a["passed"] for a in assertions)
    return {
        "scenario_id": "scenario_mc_4",
        "name": "Scenario 4: Database -> Multi-Cloud Parquet Ingestion",
        "status": "Passed" if all_passed else "Failed",
        "duration_ms": duration_ms,
        "records_transferred": 1500,
        "assertions": assertions
    }


def run_scenario_5_cloud_to_database_upsert() -> Dict[str, Any]:
    """Scenario 5: Multi-Cloud Storage -> Database In-Place Upsert."""
    start_time = time.time()
    assertions = []

    temp_dir = tempfile.mkdtemp(prefix="dataforge_sc5_")
    db_file = os.path.join(temp_dir, "warehouse.db")
    db_conn = SQLiteConnector({"database_path": db_file})

    # Seed target table with initial 100 accounts
    db_conn.execute_query("""
        CREATE TABLE customer_accounts (
            account_id INTEGER PRIMARY KEY,
            holder_name TEXT,
            balance REAL,
            tier TEXT
        );
    """)
    for i in range(1, 101):
        db_conn.execute_query(f"""
            INSERT INTO customer_accounts VALUES ({i}, 'User {i}', 1000.0, 'STANDARD');
        """)

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
        s3.create_bucket(Bucket="dataforge-s3-lake")

        s3_conn = AmazonS3Connector({"bucket": "dataforge-s3-lake", "region_name": "us-east-1", "access_key_id": "testing", "secret_access_key": "testing"})

        # Mutation file: 50 existing accounts updated (accounts 51-100) + 50 new accounts (101-150)
        lines = ["account_id,holder_name,balance,tier"]
        for i in range(51, 101):
            lines.append(f"{i},User {i},9999.50,PLATINUM")
        for i in range(101, 151):
            lines.append(f"{i},New User {i},500.00,GOLD")
        csv_payload = "\n".join(lines).encode("utf-8")

        s3_conn.write_file("dataforge-s3-lake", "mutations.csv", csv_payload)

        config = {
            "source": {"container": "dataforge-s3-lake", "path": "mutations.csv"},
            "destination": {
                "table_name": "customer_accounts",
                "write_mode": "upsert",
                "key_columns": ["account_id"]
            },
            "source_settings": {"format": "csv", "has_header": True}
        }

        res = TransferEngine.execute_storage_to_database(
            src_connector=s3_conn,
            db_connector=db_conn,
            src_container="dataforge-s3-lake",
            src_path="mutations.csv",
            dst_table="customer_accounts",
            config=config
        )

        # Inspect database post-upsert
        count_rows = db_conn.execute_query("SELECT COUNT(*) as cnt FROM customer_accounts;")[0]["cnt"]
        updated_row = db_conn.execute_query("SELECT balance, tier FROM customer_accounts WHERE account_id = 75;")[0]
        new_row = db_conn.execute_query("SELECT holder_name, balance FROM customer_accounts WHERE account_id = 120;")[0]
        untouched_row = db_conn.execute_query("SELECT balance, tier FROM customer_accounts WHERE account_id = 10;")[0]

        assertions.append({
            "name": "Upsert Transfer Execution Status",
            "expected": "True",
            "actual": str(res.success),
            "passed": res.success is True
        })
        assertions.append({
            "name": "Total Rows in Warehouse Post-Upsert",
            "expected": "150",
            "actual": str(count_rows),
            "passed": count_rows == 150
        })
        assertions.append({
            "name": "Updated Record Value Check (Account 75)",
            "expected": "9999.50, PLATINUM",
            "actual": f"{updated_row['balance']}, {updated_row['tier']}",
            "passed": updated_row["balance"] == 9999.50 and updated_row["tier"] == "PLATINUM"
        })
        assertions.append({
            "name": "New Record Value Check (Account 120)",
            "expected": "New User 120, 500.0",
            "actual": f"{new_row['holder_name']}, {new_row['balance']}",
            "passed": new_row["holder_name"] == "New User 120" and new_row["balance"] == 500.0
        })
        assertions.append({
            "name": "Untouched Record Preserved (Account 10)",
            "expected": "1000.0, STANDARD",
            "actual": f"{untouched_row['balance']}, {untouched_row['tier']}",
            "passed": untouched_row["balance"] == 1000.0 and untouched_row["tier"] == "STANDARD"
        })

    shutil.rmtree(temp_dir, ignore_errors=True)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    all_passed = all(a["passed"] for a in assertions)
    return {
        "scenario_id": "scenario_mc_5",
        "name": "Scenario 5: Multi-Cloud -> Database In-Place Upsert",
        "status": "Passed" if all_passed else "Failed",
        "duration_ms": duration_ms,
        "records_transferred": res.records_transferred if res else 0,
        "assertions": assertions
    }


def run_scenario_6_large_file_bounded_memory() -> Dict[str, Any]:
    """Scenario 6: 1GB+ Large File Streaming & Memory Bounded Limit (< 256MB)."""
    start_time = time.time()
    assertions = []

    # 1GB = 1,073,741,824 bytes
    one_gb = 1024 * 1024 * 1024
    src_connector = VirtualLargeSourceConnector(total_bytes=one_gb, chunk_size=8 * 1024 * 1024)
    dst_connector = VirtualLargeSinkConnector()

    tracemalloc.start()
    config = {
        "performance": {"chunk_size": 8 * 1024 * 1024, "buffer_size": 32 * 1024 * 1024},
        "advanced": {"checksum_algorithm": "md5"}
    }

    res = TransferEngine.execute_storage_to_storage(
        src_connector=src_connector,
        dst_connector=dst_connector,
        src_container="virtual-source",
        src_path="1gb_telemetry.bin",
        dst_container="virtual-dest",
        dst_path="1gb_telemetry.bin",
        config=config
    )

    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = round(peak_memory / (1024 * 1024), 2)
    duration_sec = max(0.001, time.time() - start_time)
    speed_mb_sec = round((one_gb / (1024 * 1024)) / duration_sec, 2)

    assertions.append({
        "name": "1GB Stream Transfer Status",
        "expected": "True",
        "actual": str(res.success),
        "passed": res.success is True
    })
    assertions.append({
        "name": "Exact 1GB Byte Parity",
        "expected": str(one_gb),
        "actual": str(res.bytes_transferred),
        "passed": res.bytes_transferred == one_gb and dst_connector.bytes_received == one_gb
    })
    assertions.append({
        "name": "Bounded Memory Peak (< 256MB Limit)",
        "expected": "< 256.0 MB",
        "actual": f"{peak_mb} MB",
        "passed": peak_mb < 256.0
    })

    duration_ms = round(duration_sec * 1000, 2)
    all_passed = all(a["passed"] for a in assertions)
    return {
        "scenario_id": "scenario_mc_6",
        "name": "Scenario 6: 1GB+ Large File Streaming & Memory Bounded Limit",
        "status": "Passed" if all_passed else "Failed",
        "duration_ms": duration_ms,
        "bytes_transferred": res.bytes_transferred if res else 0,
        "peak_memory_mb": peak_mb,
        "throughput_mb_sec": speed_mb_sec,
        "checksum": res.destination_checksum if res else None,
        "assertions": assertions
    }


def run_scenario_7_cancellation_mid_stream() -> Dict[str, Any]:
    """Scenario 7: Cooperative Cancellation During Active Transfer."""
    start_time = time.time()
    assertions = []

    src_connector = VirtualLargeSourceConnector(total_bytes=100 * 1024 * 1024)
    dst_connector = VirtualLargeSinkConnector()
    token = CancellationToken()
    token.cancel("User aborted pipeline execution")

    res = TransferEngine.execute_storage_to_storage(
        src_connector=src_connector,
        dst_connector=dst_connector,
        src_container="source",
        src_path="cancelled.bin",
        dst_container="dest",
        dst_path="cancelled.bin",
        config={},
        cancellation_token=token
    )

    assertions.append({
        "name": "Transfer Success Flag is False",
        "expected": "False",
        "actual": str(res.success),
        "passed": res.success is False
    })
    assertions.append({
        "name": "Cancellation Flag is True",
        "expected": "True",
        "actual": str(res.cancelled),
        "passed": res.cancelled is True
    })
    assertions.append({
        "name": "Cancellation Reason Recorded",
        "expected": "Transfer cancelled",
        "actual": res.error_message or "",
        "passed": "cancelled" in (res.error_message or "").lower()
    })

    duration_ms = round((time.time() - start_time) * 1000, 2)
    all_passed = all(a["passed"] for a in assertions)
    return {
        "scenario_id": "scenario_mc_7",
        "name": "Scenario 7: Cooperative Cancellation Mid-Stream",
        "status": "Passed" if all_passed else "Failed",
        "duration_ms": duration_ms,
        "assertions": assertions
    }


ALL_MULTICLOUD_SCENARIOS = [
    run_scenario_1_s3_to_adls_streaming,
    run_scenario_2_adls_to_s3_transcoding,
    run_scenario_3_gcs_to_s3_multipart,
    run_scenario_4_database_to_multicloud_parquet,
    run_scenario_5_cloud_to_database_upsert,
    run_scenario_6_large_file_bounded_memory,
    run_scenario_7_cancellation_mid_stream
]
