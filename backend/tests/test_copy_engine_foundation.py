import time
import io
import queue
import threading
import pyarrow as pa
import pytest
from typing import Iterator, Dict, Any, List

from backend.app.engine.copy.models import (
    CancellationToken,
    CopyOptions,
    CopyResult,
    PartitionSpec,
    CheckpointToken
)
from backend.app.engine.copy.stream_io import (
    BoundedTransferBuffer,
    ChunkedStreamReader,
    StreamBufferWriter,
    StreamChecksumCalculator
)
from backend.app.engine.copy.record_batch import (
    ArrowRecordBatchTransformer,
    dict_records_to_record_batch,
    record_batch_to_dict_records
)
from backend.app.engine.copy.checkpoints import PartitionCheckpointLedger
from backend.app.engine.copy.engine import DataForgeCopyEngine
from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.connectors.sqlite import SQLiteConnector


def test_stream_checksum_calculator():
    calc_md5 = StreamChecksumCalculator("md5")
    calc_md5.update(b"hello ")
    calc_md5.update(b"world")
    # md5("hello world") = 5eb63bbbe01eeed093cb22bb8f5acdc3
    assert calc_md5.hexdigest() == "5eb63bbbe01eeed093cb22bb8f5acdc3"

    calc_sha = StreamChecksumCalculator("sha256")
    calc_sha.update(b"dataforge")
    assert len(calc_sha.hexdigest()) == 64


def test_bounded_transfer_buffer_backpressure():
    token = CancellationToken()
    buf = BoundedTransferBuffer(max_buffered_chunks=2, checksum_algorithm="md5", cancellation_token=token)

    # Push 2 chunks (should succeed immediately)
    buf.push(b"chunk1")
    buf.push(b"chunk2")

    consumer_read = []
    
    def consumer():
        time.sleep(0.05)
        for chunk in buf.stream_chunks():
            consumer_read.append(chunk)

    t = threading.Thread(target=consumer)
    t.start()

    # Third push will succeed once consumer starts popping
    buf.push(b"chunk3")
    buf.close()
    t.join(timeout=2.0)

    assert consumer_read == [b"chunk1", b"chunk2", b"chunk3"]
    assert buf.total_bytes == len(b"chunk1") + len(b"chunk2") + len(b"chunk3")


def test_chunked_stream_reader():
    chunks = [b"abcdef", b"ghijkl", b"mnopqr", b"stuvwxyz"]
    def chunk_iter():
        for c in chunks:
            yield c

    reader = ChunkedStreamReader(chunk_iter())
    assert reader.readable() is True
    assert reader.seekable() is False

    # Read in small buffers
    out = bytearray(4)
    n1 = reader.readinto(out)
    assert n1 == 4
    assert bytes(out[:n1]) == b"abcd"

    # Read remaining
    rest = reader.read()
    assert rest == b"efghijklmnopqrstuvwxyz"


def test_stream_buffer_writer():
    token = CancellationToken()
    buf = BoundedTransferBuffer(max_buffered_chunks=4, cancellation_token=token)
    writer = StreamBufferWriter(buf, flush_threshold=10)

    # Writing less than threshold should buffer internally
    writer.write(b"12345")
    assert buf._queue.qsize() == 0

    # Crossing threshold should flush chunk to buffer
    writer.write(b"678901")
    assert buf._queue.qsize() == 1

    writer.close()
    chunks = list(buf.stream_chunks())
    assert b"".join(chunks) == b"12345678901"


def test_arrow_record_batch_transformer():
    data = [
        {"id": 1, "name": "Alice", "score": 95.5, "secret": "x123"},
        {"id": 2, "name": "Bob", "score": 88.0, "secret": "y456"}
    ]
    batch = dict_records_to_record_batch(data)
    assert batch is not None
    assert batch.num_rows == 2

    # Map name -> full_name, cast id -> int64, exclude secret
    mappings = [
        {"source_column": "id", "destination_column": "user_id", "target_type": "int64"},
        {"source_column": "name", "destination_column": "full_name"},
        {"source_column": "score", "destination_column": "points"},
        {"source_column": "secret", "exclude": True}
    ]
    transformer = ArrowRecordBatchTransformer(mappings)
    transformed_batch = transformer.transform_batch(batch)

    assert transformed_batch.schema.names == ["user_id", "full_name", "points"]
    assert transformed_batch.schema.field("user_id").type == pa.int64()

    records = record_batch_to_dict_records(transformed_batch)
    assert records[0] == {"user_id": 1, "full_name": "Alice", "points": 95.5}
    assert records[1] == {"user_id": 2, "full_name": "Bob", "points": 88.0}


def test_partition_checkpoint_ledger():
    ledger = PartitionCheckpointLedger(run_id="run_101", activity_id="act_copy_1")
    specs = [
        PartitionSpec(partition_id="part_0", slice_index=0, total_slices=3),
        PartitionSpec(partition_id="part_1", slice_index=1, total_slices=3),
        PartitionSpec(partition_id="part_2", slice_index=2, total_slices=3),
    ]
    ledger.register_partitions(specs)

    # Initially all 3 are pending
    assert len(ledger.get_pending_partitions()) == 3
    assert ledger.is_all_completed() is False

    # Mark partition 0 completed
    ledger.mark_completed("part_0", rows_transferred=5000, bytes_transferred=250000, checksum="abc1")
    assert len(ledger.get_pending_partitions()) == 2

    # Simulate checkpoint serialization and resume in a new ledger
    serialized = ledger.serialize_checkpoints()
    assert "part_0" in serialized

    new_ledger = PartitionCheckpointLedger(run_id="run_101", activity_id="act_copy_1")
    new_ledger.register_partitions(specs)
    new_ledger.load_existing_checkpoints(serialized)

    # New ledger knows part_0 is already done and resumes part_1 and part_2
    assert len(new_ledger.get_pending_partitions()) == 2
    assert new_ledger.partitions["part_0"].status == "Succeeded"


def test_copy_engine_storage_to_storage_binary(tmp_path):
    root_src = tmp_path / "src"
    root_dst = tmp_path / "dst"
    root_src.mkdir()
    root_dst.mkdir()

    src_conn = LocalStorageConnector({"base_path": str(root_src)})
    dst_conn = LocalStorageConnector({"base_path": str(root_dst)})

    # Create test source file with binary content
    test_data = b"DataForge Copy Engine Streaming Test Payload " * 1000
    src_file = root_src / "data.bin"
    src_file.write_bytes(test_data)

    res = DataForgeCopyEngine.execute_storage_to_storage(
        src_connector=src_conn,
        dst_connector=dst_conn,
        src_container="",
        src_path="data.bin",
        dst_container="",
        dst_path="data_copy.bin",
        options=CopyOptions(chunk_size_mb=1, checksum_algorithm="md5")
    )

    assert res.success is True
    assert res.bytes_transferred == len(test_data)
    assert res.checksum_verified is True
    assert res.destination_checksum == res.source_checksum

    # Verify destination file on disk
    dst_file = root_dst / "data_copy.bin"
    assert dst_file.exists()
    assert dst_file.read_bytes() == test_data


def test_copy_engine_storage_to_storage_transcoding(tmp_path):
    root_src = tmp_path / "src"
    root_dst = tmp_path / "dst"
    root_src.mkdir()
    root_dst.mkdir()

    src_conn = LocalStorageConnector({"base_path": str(root_src)})
    dst_conn = LocalStorageConnector({"base_path": str(root_dst)})

    # Create CSV source file
    csv_content = "id,name,amount\n1,Alice,100\n2,Bob,250\n3,Charlie,350\n"
    (root_src / "customers.csv").write_text(csv_content)

    res = DataForgeCopyEngine.execute_storage_to_storage(
        src_connector=src_conn,
        dst_connector=dst_conn,
        src_container="",
        src_path="customers.csv",
        dst_container="",
        dst_path="customers.json",
        config={
            "source": {"format": "csv"},
            "destination": {"format": "json"},
            "column_mappings": [
                {"source_column": "id", "destination_column": "customer_id"},
                {"source_column": "name", "destination_column": "customer_name"},
                {"source_column": "amount", "destination_column": "total_spend"}
            ]
        }
    )

    assert res.success is True
    assert res.records_transferred == 3
    dst_file = root_dst / "customers.json"
    assert dst_file.exists()


def test_copy_engine_cancellation(tmp_path):
    root_src = tmp_path / "src"
    root_dst = tmp_path / "dst"
    root_src.mkdir()
    root_dst.mkdir()

    src_conn = LocalStorageConnector({"base_path": str(root_src)})
    dst_conn = LocalStorageConnector({"base_path": str(root_dst)})

    (root_src / "large.bin").write_bytes(b"X" * (1024 * 1024))
    token = CancellationToken()
    token.cancel(reason="Aborted by test runner")

    res = DataForgeCopyEngine.execute_storage_to_storage(
        src_connector=src_conn,
        dst_connector=dst_conn,
        src_container="",
        src_path="large.bin",
        dst_container="",
        dst_path="large_cancelled.bin",
        cancellation_token=token
    )

    assert res.success is False
    assert res.cancelled is True
    assert "Aborted by test runner" in res.error_message


def test_copy_engine_database_streaming(tmp_path):
    db_file = tmp_path / "source.db"
    conn = SQLiteConnector({"database_path": str(db_file)})

    # Setup table with sample data
    conn.execute_query("CREATE TABLE sales (id INTEGER PRIMARY KEY, item TEXT, revenue REAL);")
    for i in range(1, 101):
        conn.execute_query(f"INSERT INTO sales VALUES ({i}, 'item_{i}', {i * 10.5});")

    root_dst = tmp_path / "dst"
    root_dst.mkdir()
    dst_conn = LocalStorageConnector({"base_path": str(root_dst)})

    # DB -> Storage
    res_db_to_storage = DataForgeCopyEngine.execute_database_to_storage(
        db_connector=conn,
        dst_connector=dst_conn,
        src_table="sales",
        dst_container="",
        dst_path="sales_export.json",
        config={
            "source": {"batch_size": 20},
            "destination": {"format": "json"}
        }
    )
    assert res_db_to_storage.success is True
    assert res_db_to_storage.records_transferred == 100

    # Storage -> DB (into new table sales_imported)
    res_storage_to_db = DataForgeCopyEngine.execute_storage_to_database(
        src_connector=dst_conn,
        db_connector=conn,
        src_container="",
        src_path="sales_export.json",
        dst_table="sales_imported",
        config={
            "source_settings": {"format": "json"},
            "destination": {"batch_size": 25, "auto_create_table": True}
        }
    )
    assert res_storage_to_db.success is True
    assert res_storage_to_db.records_transferred == 100

    rows = conn.execute_query("SELECT COUNT(*) as cnt FROM sales_imported;")
    assert rows[0]["cnt"] == 100


def test_copy_engine_bounded_memory_streaming(tmp_path):
    import tracemalloc

    root_src = tmp_path / "src"
    root_dst = tmp_path / "dst"
    root_src.mkdir()
    root_dst.mkdir()

    src_conn = LocalStorageConnector({"base_path": str(root_src)})
    dst_conn = LocalStorageConnector({"base_path": str(root_dst)})

    # Generate a 20 MB binary payload in chunks
    chunk = b"A" * (1024 * 1024)  # 1 MB chunk
    src_file = root_src / "medium_file.bin"
    with open(src_file, "wb") as f:
        for _ in range(20):
            f.write(chunk)

    tracemalloc.start()
    res = DataForgeCopyEngine.execute_storage_to_storage(
        src_connector=src_conn,
        dst_connector=dst_conn,
        src_container="",
        src_path="medium_file.bin",
        dst_container="",
        dst_path="medium_copy.bin",
        options=CopyOptions(chunk_size_mb=2, buffer_capacity_chunks=2)
    )
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert res.success is True
    assert res.bytes_transferred == 20 * 1024 * 1024
    peak_mb = peak / (1024 * 1024)
    # Peak memory allocated by python during streaming must be well under 64 MB (typically < 10 MB)
    assert peak_mb < 64.0, f"Peak memory exceeded bounded limit: {peak_mb} MB"

