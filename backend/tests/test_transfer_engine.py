import os
import tempfile
import shutil
import io
import time
import pytest

from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.transfer.models import CancellationToken, TransferProgress
from backend.app.transfer.checksums import StreamChecksumCalculator
from backend.app.transfer.buffer import BoundedTransferBuffer
from backend.app.transfer.engine import TransferEngine
from backend.app.activities.base import ActivityExecutionContext
from backend.app.activities.copy_data import CopyDataActivity
from backend.app.models.connection import Connection
from backend.app.models.workspace import Project
from backend.app.core.database import SessionLocal
from backend.app.core.security import encrypt_secret


@pytest.fixture
def temp_storage_dirs():
    src_dir = tempfile.mkdtemp(prefix="dataforge_src_")
    dst_dir = tempfile.mkdtemp(prefix="dataforge_dst_")

    src_conn = LocalStorageConnector({"base_path": src_dir})
    dst_conn = LocalStorageConnector({"base_path": dst_dir})

    yield src_conn, dst_conn, src_dir, dst_dir

    shutil.rmtree(src_dir, ignore_errors=True)
    shutil.rmtree(dst_dir, ignore_errors=True)


class TestChecksumsAndBuffer:
    def test_checksum_calculator_md5(self):
        calc = StreamChecksumCalculator("md5")
        calc.update(b"Hello ")
        calc.update(b"World!")
        assert calc.hexdigest() == "ed076287532e86365e841e92bfc50d8c"

    def test_checksum_calculator_sha256(self):
        calc = StreamChecksumCalculator("sha256")
        calc.update(b"DataForge Enterprise")
        assert len(calc.hexdigest()) == 64

    def test_checksum_calculator_crc32c(self):
        calc = StreamChecksumCalculator("crc32c")
        calc.update(b"123456789")
        # crc32c of "123456789" = 0xe3069283 (or fallback zlib crc32 = 0xcbf43926)
        assert calc.hexdigest() in ("e3069283", "cbf43926")

    def test_bounded_transfer_buffer(self):
        buffer = BoundedTransferBuffer(max_buffered_chunks=2)
        buffer.push(b"chunk1")
        buffer.push(b"chunk2")
        buffer.close()

        chunks = list(buffer.stream_chunks())
        assert len(chunks) == 2
        assert chunks[0] == b"chunk1"
        assert chunks[1] == b"chunk2"
        assert buffer.total_bytes == 12


class TestTransferEngineDirectAndTranscoding:
    def test_direct_binary_copy(self, temp_storage_dirs):
        src_conn, dst_conn, src_dir, dst_dir = temp_storage_dirs

        # Prepare source file
        payload = b"id,name,value\n1,Apples,50\n2,Bananas,100\n"
        src_conn.write_file("raw-bucket", "inventory.csv", payload)

        config = {
            "source": {"container": "raw-bucket", "path": "inventory.csv"},
            "destination": {"container": "backup-bucket", "path": "inventory.csv"},
            "source_settings": {"format": "csv"},
            "destination_settings": {"format": "csv"},
            "performance": {"chunk_size_mb": 1},
            "advanced": {"checksum_algorithm": "md5"}
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=src_conn,
            dst_connector=dst_conn,
            src_container="raw-bucket",
            src_path="inventory.csv",
            dst_container="backup-bucket",
            dst_path="inventory.csv",
            config=config
        )

        assert res.success is True
        assert res.bytes_transferred == len(payload)
        assert res.checksum_verified is True
        assert res.source_checksum == res.destination_checksum

        # Verify destination file exists and matches
        copied_data = dst_conn.read_file("backup-bucket", "inventory.csv")
        assert copied_data == payload

    def test_transcoding_csv_to_parquet(self, temp_storage_dirs):
        src_conn, dst_conn, src_dir, dst_dir = temp_storage_dirs

        # Prepare source CSV
        csv_data = b"id,name,score\n1,Alice,95.5\n2,Bob,88.0\n"
        src_conn.write_file("raw", "scores.csv", csv_data)

        config = {
            "source": {"container": "raw", "path": "scores.csv"},
            "destination": {"container": "lake", "path": "scores.parquet", "format": "parquet"},
            "source_settings": {"format": "csv", "has_header": True},
            "destination_settings": {"format": "parquet", "compression": "snappy"},
            "column_mappings": []
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=src_conn,
            dst_connector=dst_conn,
            src_container="raw",
            src_path="scores.csv",
            dst_container="lake",
            dst_path="scores.parquet",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 2
        assert res.bytes_transferred > 0

        # Read back parquet and verify
        import pyarrow.parquet as pq
        parquet_bytes = dst_conn.read_file("lake", "scores.parquet")
        table = pq.read_table(io.BytesIO(parquet_bytes))
        assert table.num_rows == 2
        assert "score" in table.column_names

    def test_transcoding_with_column_mappings(self, temp_storage_dirs):
        src_conn, dst_conn, src_dir, dst_dir = temp_storage_dirs

        # Prepare source JSON Lines
        jsonl_data = b'{"emp_id": 101, "full_name": "Carol", "dept": "HR"}\n{"emp_id": 102, "full_name": "Dave", "dept": "IT"}\n'
        src_conn.write_file("inbound", "employees.jsonl", jsonl_data)

        config = {
            "source": {"container": "inbound", "path": "employees.jsonl"},
            "destination": {"container": "outbound", "path": "staff.jsonl", "format": "jsonl"},
            "source_settings": {"format": "jsonl"},
            "destination_settings": {"format": "jsonl"},
            "column_mappings": [
                {"source_column": "emp_id", "destination_column": "employee_id"},
                {"source_column": "full_name", "destination_column": "name"},
                {"source_column": "dept", "exclude": True}
            ]
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=src_conn,
            dst_connector=dst_conn,
            src_container="inbound",
            src_path="employees.jsonl",
            dst_container="outbound",
            dst_path="staff.jsonl",
            config=config
        )

        assert res.success is True
        assert res.records_transferred == 2

        out_data = dst_conn.read_file("outbound", "staff.jsonl").decode("utf-8")
        assert "employee_id" in out_data
        assert "dept" not in out_data

    def test_cancellation_token_stops_transfer(self, temp_storage_dirs):
        src_conn, dst_conn, src_dir, dst_dir = temp_storage_dirs

        # Prepare source file
        payload = b"line\n" * 1000
        src_conn.write_file("source", "long.txt", payload)

        token = CancellationToken()
        token.cancel("User aborted pipeline")

        config = {
            "source": {"container": "source", "path": "long.txt"},
            "destination": {"container": "target", "path": "long.txt"},
            "source_settings": {"format": "text"},
            "destination_settings": {"format": "text"},
            "performance": {"chunk_size_mb": 1}
        }

        res = TransferEngine.execute_storage_to_storage(
            src_connector=src_conn,
            dst_connector=dst_conn,
            src_container="source",
            src_path="long.txt",
            dst_container="target",
            dst_path="long.txt",
            config=config,
            cancellation_token=token
        )

        assert res.success is False
        assert res.cancelled is True


class TestCopyDataActivityIntegration:
    def test_copy_data_activity_storage_transfer(self, temp_storage_dirs):
        src_conn, dst_conn, src_dir, dst_dir = temp_storage_dirs
        db = SessionLocal()

        try:
            proj = db.query(Project).first()
            if not proj:
                proj = Project(name="Transfer Test Project")
                db.add(proj)
                db.commit()
                db.refresh(proj)

            # Create source & dest connection records
            src_db_conn = Connection(
                project_id=proj.id,
                name="Src Local Storage",
                connector_type="local_storage",
                config_encrypted=encrypt_secret({"base_path": src_dir})
            )
            dst_db_conn = Connection(
                project_id=proj.id,
                name="Dst Local Storage",
                connector_type="local_storage",
                config_encrypted=encrypt_secret({"base_path": dst_dir})
            )
            db.add_all([src_db_conn, dst_db_conn])
            db.commit()

            # Seed source data
            src_conn.write_file("data-lake", "metrics.csv", b"timestamp,cpu,ram\n100,50,70\n101,55,72\n")

            activity_config = {
                "source": {
                    "connection_id": src_db_conn.id,
                    "container": "data-lake",
                    "path": "metrics.csv"
                },
                "destination": {
                    "connection_id": dst_db_conn.id,
                    "container": "archive-lake",
                    "path": "metrics.csv"
                },
                "source_settings": {"format": "csv"},
                "destination_settings": {"format": "csv"},
                "advanced": {"checksum_algorithm": "sha256"}
            }

            context = ActivityExecutionContext(
                pipeline_run_id="run_test_transfer_123",
                activity_id="act_transfer_copy_1",
                activity_name="test_storage_copy",
                activity_type="CopyData",
                config=activity_config,
                pipeline_parameters={},
                pipeline_variables={}
            )

            activity = CopyDataActivity(context, db)
            exec_result = activity.execute()

            assert exec_result.status == "Succeeded"
            assert exec_result.bytes_processed > 0
            assert "checksum" in exec_result.metrics

            copied = dst_conn.read_file("archive-lake", "metrics.csv")
            assert b"cpu,ram" in copied

            # Cleanup db records
            db.delete(src_db_conn)
            db.delete(dst_db_conn)
            db.commit()
        finally:
            db.close()
