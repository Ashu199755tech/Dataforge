import os
import time
import shutil
import tempfile
import sqlite3
from datetime import datetime
from backend.app.connectors.sqlite import SQLiteConnector
from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.engine.copy.models import (
    CancellationToken,
    CopyOptions,
    PartitionSpec
)
from backend.app.engine.copy.checkpoints import PartitionCheckpointLedger
from backend.app.engine.copy.partitioner import (
    RangePartitioner,
    TemporalPartitioner,
    ListPartitioner,
    StorageFilePartitioner
)
from backend.app.engine.copy.coordinator import ParallelCopyCoordinator
from backend.app.engine.copy.engine import DataForgeCopyEngine


def test_numeric_range_partitioner():
    # Test standard integer range [1, 100] split into 4 slices
    specs = RangePartitioner.create_numeric_partitions("user_id", min_val=1, max_val=100, num_partitions=4)
    assert len(specs) == 4
    assert specs[0].partition_id == "part-00000"
    assert specs[0].range_min == 1
    assert specs[0].range_max == 25
    assert specs[0].filter_expr == '"user_id" >= 1 AND "user_id" < 25'

    assert specs[1].range_min == 25
    assert specs[1].range_max == 50
    assert specs[1].filter_expr == '"user_id" >= 25 AND "user_id" < 50'

    assert specs[3].range_min == 75
    assert specs[3].range_max == 100
    assert specs[3].filter_expr == '"user_id" >= 75 AND "user_id" <= 100'

    # Test single point range
    single_point = RangePartitioner.create_numeric_partitions("id", 10, 10, num_partitions=4)
    assert len(single_point) == 1
    assert single_point[0].filter_expr == '"id" >= 10 AND "id" <= 10'

    # Test floating point range [0.0, 10.0] with 2 slices
    float_specs = RangePartitioner.create_numeric_partitions("amount", 0.0, 10.0, num_partitions=2)
    assert len(float_specs) == 2
    assert float_specs[0].range_min == 0.0
    assert float_specs[0].range_max == 5.0
    assert '"amount" >= 0.000000 AND "amount" < 5.000000' in float_specs[0].filter_expr
    assert '"amount" >= 5.000000 AND "amount" <= 10.000000' in float_specs[1].filter_expr


def test_temporal_partitioner():
    # Test daily partition windows over 4 days
    specs = TemporalPartitioner.create_temporal_partitions(
        column="created_at",
        start_time="2026-01-01 00:00:00",
        end_time="2026-01-05 00:00:00",
        num_partitions=4
    )
    assert len(specs) == 4
    assert specs[0].range_min == "2026-01-01 00:00:00"
    assert specs[0].range_max == "2026-01-02 00:00:00"
    assert '"created_at" >= \'2026-01-01 00:00:00\' AND "created_at" < \'2026-01-02 00:00:00\'' == specs[0].filter_expr

    assert specs[3].range_min == "2026-01-04 00:00:00"
    assert specs[3].range_max == "2026-01-05 00:00:00"
    assert '"created_at" >= \'2026-01-04 00:00:00\' AND "created_at" <= \'2026-01-05 00:00:00\'' == specs[3].filter_expr


def test_list_partitioner():
    regions = ["US-EAST", "US-WEST", "EU-WEST", "AP-SOUTH", "SA-EAST"]
    specs = ListPartitioner.create_discrete_partitions(column="region", values=regions, num_partitions=2)
    assert len(specs) == 2
    # Check that all regions are accounted for in filter expressions
    combined_expr = f"{specs[0].filter_expr} AND {specs[1].filter_expr}"
    for r in regions:
        assert r in combined_expr


def test_storage_file_partitioner_bin_packing():
    # 5 files of varying sizes
    files = [
        ("file_a.parquet", 100 * 1024 * 1024),  # 100 MB
        ("file_b.parquet", 80 * 1024 * 1024),   # 80 MB
        ("file_c.parquet", 60 * 1024 * 1024),   # 60 MB
        ("file_d.parquet", 40 * 1024 * 1024),   # 40 MB
        ("file_e.parquet", 20 * 1024 * 1024),   # 20 MB
    ]
    # Total = 300 MB. 2 partitions -> target ~150 MB each
    specs = StorageFilePartitioner.create_file_partitions(files, num_partitions=2)
    assert len(specs) == 2

    # Partition 0: 100 + 40 + 20 = 160 MB (or 100 + 60 = 160 MB)
    # Partition 1: 80 + 60 = 140 MB
    items_p0 = specs[0].file_items or []
    items_p1 = specs[1].file_items or []

    assert len(items_p0) + len(items_p1) == 5
    assert set(items_p0 + items_p1) == {f[0] for f in files}


def test_auto_probe_and_partition_sqlite():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_probe.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id TEXT, amount REAL);")
        records = [(i, f"cust_{i}", float(i * 10)) for i in range(1, 501)]
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?);", records)
        conn.commit()
        conn.close()

        connector = SQLiteConnector({"database_path": db_path})
        specs = RangePartitioner.auto_probe_and_partition(
            connector=connector,
            table_name="orders",
            column="order_id",
            num_partitions=4
        )
        assert len(specs) == 4
        assert specs[0].range_min == 1
        assert specs[-1].range_max == 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_parallel_database_to_storage_copy():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_db_copy.db")
    storage_dir = os.path.join(tmp_dir, "storage")
    os.makedirs(storage_dir, exist_ok=True)

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE products (sku_id INTEGER PRIMARY KEY, name TEXT, price REAL);")
        records = [(i, f"Product {i}", round(10.5 + i, 2)) for i in range(1, 401)]
        conn.executemany("INSERT INTO products VALUES (?, ?, ?);", records)
        conn.commit()
        conn.close()

        db_conn = SQLiteConnector({"database_path": db_path})
        storage_conn = LocalStorageConnector({"base_path": storage_dir})

        opts = CopyOptions(max_parallel_partitions=4, batch_size=50)
        res = DataForgeCopyEngine.execute_partitioned_database_to_storage(
            db_connector=db_conn,
            dst_connector=storage_conn,
            src_table="products",
            dst_container="exports",
            dst_path="products_export.csv",
            partition_column="sku_id",
            num_partitions=4,
            options=opts
        )

        assert res.success is True
        assert res.records_transferred == 400
        assert res.partitions_total == 4
        assert res.partitions_succeeded == 4
        assert res.partitions_failed == 0

        # Verify output partition files exist
        export_folder = os.path.join(storage_dir, "exports")
        files = os.listdir(export_folder)
        part_files = [f for f in files if f.startswith("products_export_part_")]
        assert len(part_files) == 4

        # Read back all rows and confirm total 400
        total_rows_written = 0
        for pf in part_files:
            with open(os.path.join(export_folder, pf), "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                # Deduct 1 for header
                total_rows_written += (len(lines) - 1)
        assert total_rows_written == 400
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_parallel_storage_to_storage_copy():
    tmp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(tmp_dir, "src_store")
    dst_dir = os.path.join(tmp_dir, "dst_store")
    os.makedirs(os.path.join(src_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(dst_dir, "backup"), exist_ok=True)

    try:
        # Create 6 small files
        for i in range(6):
            file_path = os.path.join(src_dir, "raw", f"batch_{i}.txt")
            with open(file_path, "wb") as f:
                f.write(f"Sample data content for batch {i}\n".encode("utf-8") * 100)

        src_conn = LocalStorageConnector({"base_path": src_dir})
        dst_conn = LocalStorageConnector({"base_path": dst_dir})

        opts = CopyOptions(max_parallel_partitions=3)
        res = DataForgeCopyEngine.execute_partitioned_storage_to_storage(
            src_connector=src_conn,
            dst_connector=dst_conn,
            src_container="raw",
            src_path="",
            dst_container="backup",
            dst_path="",
            num_partitions=3,
            options=opts
        )

        assert res.success is True
        assert res.partitions_total == 3
        assert res.partitions_succeeded == 3
        assert res.partitions_failed == 0

        # Check destination files
        backup_files = os.listdir(os.path.join(dst_dir, "backup"))
        assert len(backup_files) == 6
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_checkpoint_ledger_partial_resumption():
    ledger = PartitionCheckpointLedger(run_id="run_resume_test", activity_id="act_01")
    specs = [
        PartitionSpec(partition_id="part-00000", slice_index=0, total_slices=3),
        PartitionSpec(partition_id="part-00001", slice_index=1, total_slices=3),
        PartitionSpec(partition_id="part-00002", slice_index=2, total_slices=3),
    ]
    ledger.register_partitions(specs)

    # Pre-populate checkpoint for part-00000 and part-00001 as previously succeeded
    ledger.load_existing_checkpoints({
        "part-00000": {"completed_at": time.time(), "rows_transferred": 100, "bytes_transferred": 1024},
        "part-00001": {"completed_at": time.time(), "rows_transferred": 200, "bytes_transferred": 2048}
    })

    # Only part-00002 should be pending
    pending = ledger.get_pending_partitions()
    assert len(pending) == 1
    assert pending[0].partition_id == "part-00002"

    executed_parts = []

    def mock_worker(spec: PartitionSpec, token: CancellationToken, updater):
        executed_parts.append(spec.partition_id)
        updater(512, 50)
        return {"rows_transferred": 50, "bytes_transferred": 512}

    coordinator = ParallelCopyCoordinator(ledger=ledger, max_parallel_partitions=2)
    res = coordinator.execute(mock_worker)

    assert res.success is True
    # Verify ONLY part-00002 was executed!
    assert executed_parts == ["part-00002"]
    # Total rows = 100 (part 0) + 200 (part 1) + 50 (part 2) = 350
    assert res.records_transferred == 350
    # Total bytes = 1024 + 2048 + 512 = 3584
    assert res.bytes_transferred == 3584
    assert res.partitions_succeeded == 3


def test_coordinator_cancellation():
    ledger = PartitionCheckpointLedger(run_id="run_cancel", activity_id="act_cancel")
    specs = [
        PartitionSpec(partition_id=f"part-{i:05d}", slice_index=i, total_slices=4)
        for i in range(4)
    ]
    ledger.register_partitions(specs)

    token = CancellationToken()
    token.cancel("User initiated abort")

    def mock_worker(spec: PartitionSpec, t: CancellationToken, updater):
        t.raise_if_cancelled()
        return {"rows_transferred": 10, "bytes_transferred": 100}

    coordinator = ParallelCopyCoordinator(ledger=ledger, max_parallel_partitions=2, cancellation_token=token)
    res = coordinator.execute(mock_worker)

    assert res.success is False
    assert res.cancelled is True
    assert res.partitions_failed == 4


def test_parallel_speedup_benchmark():
    """
    Physical empirical benchmark testing concurrency speedup.
    Compares 1 partition worker vs 4 partition workers on multi-file transfer.
    """
    tmp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(tmp_dir, "src")
    dst_dir_serial = os.path.join(tmp_dir, "dst_serial")
    dst_dir_parallel = os.path.join(tmp_dir, "dst_parallel")
    os.makedirs(os.path.join(src_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(dst_dir_serial, "out"), exist_ok=True)
    os.makedirs(os.path.join(dst_dir_parallel, "out"), exist_ok=True)

    try:
        # Create 8 files of 1 MB each = 8 MB total payload
        file_payload = b"X" * (1024 * 1024)
        for i in range(8):
            with open(os.path.join(src_dir, "data", f"chunk_{i}.bin"), "wb") as f:
                f.write(file_payload)

        src_conn = LocalStorageConnector({"base_path": src_dir})
        dst_conn_serial = LocalStorageConnector({"base_path": dst_dir_serial})
        dst_conn_parallel = LocalStorageConnector({"base_path": dst_dir_parallel})

        # Serial run (1 worker)
        opts_serial = CopyOptions(max_parallel_partitions=1, chunk_size_mb=1)
        start_serial = time.time()
        res_serial = DataForgeCopyEngine.execute_partitioned_storage_to_storage(
            src_connector=src_conn,
            dst_connector=dst_conn_serial,
            src_container="data",
            src_path="",
            dst_container="out",
            dst_path="",
            num_partitions=1,
            options=opts_serial
        )
        duration_serial = max(0.001, time.time() - start_serial)

        # Parallel run (4 workers)
        opts_parallel = CopyOptions(max_parallel_partitions=4, chunk_size_mb=1)
        start_parallel = time.time()
        res_parallel = DataForgeCopyEngine.execute_partitioned_storage_to_storage(
            src_connector=src_conn,
            dst_connector=dst_conn_parallel,
            src_container="data",
            src_path="",
            dst_container="out",
            dst_path="",
            num_partitions=4,
            options=opts_parallel
        )
        duration_parallel = max(0.001, time.time() - start_parallel)

        assert res_serial.success is True
        assert res_parallel.success is True
        assert res_serial.bytes_transferred == 8 * 1024 * 1024
        assert res_parallel.bytes_transferred == 8 * 1024 * 1024

        print(f"\n[BENCHMARK] Serial 1 worker: {duration_serial:.4f}s ({res_serial.throughput_mb_sec} MB/s)")
        print(f"[BENCHMARK] Parallel 4 workers: {duration_parallel:.4f}s ({res_parallel.throughput_mb_sec} MB/s)")
        print(f"[BENCHMARK] Speedup factor: {duration_serial / duration_parallel:.2f}x")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
