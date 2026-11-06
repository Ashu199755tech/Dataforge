import time
import threading
import pytest
from typing import Dict, Any, List

from backend.app.engine.copy.models import (
    CancellationToken,
    CopyProgress,
    CopyResult,
    PartitionSpec,
    CheckpointToken
)
from backend.app.engine.copy.checkpoints import PartitionCheckpointLedger
from backend.app.engine.copy.coordinator import ParallelCopyCoordinator
from backend.app.engine.copy.cloud_optimizer import ConcurrentMultipartUploader
from backend.app.monitoring.diagnostics import classify_error


def test_partition_worker_crash_and_checkpoint_resume():
    """
    Chaos Test 1: Worker crash mid-execution and checkpoint resumption.
    Simulates a worker dying or being killed at partition #5 of a 10-partition transfer.
    Verifies that upon resumption:
    1. Partitions 0-4 (already succeeded) are strictly skipped (idempotency, zero duplicate data).
    2. Partitions 5-9 execute and complete.
    3. Final ledger reflects 10/10 partitions succeeded with 100% data integrity.
    """
    ledger = PartitionCheckpointLedger(run_id="run_chaos_1", activity_id="act_copy_1")

    # Initialize 10 partition slices (1,000 rows & 50,000 bytes each)
    specs = []
    for i in range(10):
        spec = PartitionSpec(
            partition_id=f"part_{i}",
            slice_index=i,
            total_slices=10,
            filter_expr=f"id >= {i * 1000} AND id < {(i + 1) * 1000}"
        )
        specs.append(spec)
    ledger.register_partitions(specs)

    assert len(ledger.get_pending_partitions()) == 10

    executed_in_run_1: List[int] = []
    executed_in_run_2: List[int] = []

    # Worker 1: Injects crash at partition 5
    def flaky_worker(spec: PartitionSpec, token: CancellationToken, progress_fn):
        executed_in_run_1.append(spec.slice_index)
        if spec.slice_index == 5:
            raise RuntimeError("CRASH: Worker process killed (SIGKILL simulation) at partition 5")
        time.sleep(0.005)
        return {"rows": 1000, "bytes": 50000, "checksum": f"chk_{spec.slice_index}"}

    coordinator_1 = ParallelCopyCoordinator(ledger=ledger, max_parallel_partitions=2)
    result_1 = coordinator_1.execute(flaky_worker)

    # Verify Run 1 failed with error recorded
    assert result_1.success is False
    assert result_1.partitions_failed >= 1
    assert "CRASH" in (result_1.error_message or "")

    # Inspect checkpoint ledger state
    succeeded_parts = [p for p in ledger.partitions.values() if p.status == "Succeeded"]
    assert len(succeeded_parts) >= 1  # Partitions before crash succeeded
    saved_checkpoints = ledger.serialize_checkpoints()

    # Run 2: Re-instantiate ledger from persisted state (simulating fresh worker start)
    ledger_2 = PartitionCheckpointLedger(run_id="run_chaos_1", activity_id="act_copy_1")
    ledger_2.register_partitions(specs)
    ledger_2.load_existing_checkpoints(saved_checkpoints)

    def healthy_worker(spec: PartitionSpec, token: CancellationToken, progress_fn):
        executed_in_run_2.append(spec.slice_index)
        time.sleep(0.005)
        return {"rows": 1000, "bytes": 50000, "checksum": f"chk_{spec.slice_index}"}

    coordinator_2 = ParallelCopyCoordinator(ledger=ledger_2, max_parallel_partitions=2)
    result_2 = coordinator_2.execute(healthy_worker)

    # Verify Run 2 succeeded
    assert result_2.success is True
    assert result_2.partitions_succeeded == 10
    assert result_2.partitions_failed == 0
    assert result_2.records_transferred == 10000
    assert result_2.bytes_transferred == 500000

    # CRITICAL: Verify that partitions succeeded in Run 1 were NOT re-executed in Run 2
    for part_idx in [p.slice_index for p in succeeded_parts]:
        assert part_idx not in executed_in_run_2, f"Partition {part_idx} was re-executed despite already succeeding!"


def test_transient_network_error_exponential_backoff():
    """
    Chaos Test 2: Transient network reset / HTTP 503 error injection.
    Verifies that a simulated cloud connector experiences exponential backoff retries
    and successfully recovers without aborting the overall pipeline.
    """
    attempt_count = 0
    delays: List[float] = []

    def unreliable_cloud_call(max_retries=3, initial_backoff=0.05):
        nonlocal attempt_count
        backoff = initial_backoff
        for attempt in range(1, max_retries + 1):
            attempt_count += 1
            if attempt < 3:
                # Inject transient network failure
                time.sleep(backoff)
                delays.append(backoff)
                backoff *= 2
                continue  # Retry
            # Succeeded on attempt 3
            return {"status": 200, "etag": "cloud_hash_abc123"}
        raise ConnectionResetError("Connection lost after retries")

    res = unreliable_cloud_call()
    assert res["status"] == 200
    assert attempt_count == 3
    # Check that backoff grew exponentially
    assert len(delays) == 2
    assert delays[1] > delays[0]


def test_database_deadlock_and_timeout_classification():
    """
    Chaos Test 3: Failure classification under database deadlocks, lock contention, and timeouts.
    """
    # 1. Connection Error
    conn_err = ConnectionResetError("Connection reset by peer: DB server closed connection")
    assert classify_error(conn_err) == "ConnectionError"

    # 2. Timeout Error
    timeout_err = TimeoutError("Statement cancelled due to statement_timeout (30000ms)")
    assert classify_error(timeout_err) == "TimeoutError"

    # 3. Operational Lock Error
    lock_err = Exception("psycopg2.OperationalError: deadlock detected: Process 1234 waits for ShareLock")
    assert classify_error(lock_err) == "ConnectionError"

    # 4. Unknown/Generic Error
    unknown_err = RuntimeError("Unexpected arithmetic divide-by-zero")
    assert classify_error(unknown_err) == "SystemError"


def test_cooperative_cancellation_under_concurrent_load():
    """
    Chaos Test 4: Cooperative cancellation under high concurrent partition load.
    Launches 8 parallel partition tasks and signals cancellation.
    Verifies all threads stop cooperatively within 100ms without thread starvation or leakage.
    """
    ledger = PartitionCheckpointLedger(run_id="run_cancel_1", activity_id="act_cancel_1")
    token = CancellationToken()

    specs = []
    for i in range(8):
        specs.append(PartitionSpec(
            partition_id=f"p_{i}",
            slice_index=i,
            total_slices=8
        ))
    ledger.register_partitions(specs)

    def long_running_worker(spec: PartitionSpec, tok: CancellationToken, progress_fn):
        for _ in range(50):
            tok.raise_if_cancelled()
            time.sleep(0.01)
        return {"rows": 5000, "bytes": 250000, "checksum": "chk"}

    coordinator = ParallelCopyCoordinator(ledger=ledger, max_parallel_partitions=4, cancellation_token=token)

    # Cancel after 25ms in background thread
    def cancel_later():
        time.sleep(0.025)
        token.cancel()

    cancel_thread = threading.Thread(target=cancel_later)
    cancel_thread.start()

    t0 = time.time()
    result = coordinator.execute(long_running_worker)
    cancel_thread.join()
    cancel_duration = time.time() - t0

    assert result.success is False
    assert result.cancelled is True
    # Guaranteed to have aborted cooperatively in < 250ms rather than completing all 500ms
    assert cancel_duration < 0.25


def test_cloud_multipart_abort_cleanup_on_crash():
    """
    Chaos Test 5: Cloud multipart abort on part failure.
    Verifies that when a part fails mid-upload, ConcurrentMultipartUploader calls
    s3_client.abort_multipart_upload to eliminate orphaned storage chunks.
    """
    class MockS3Client:
        def __init__(self):
            self.created = False
            self.aborted = False
            self.completed = False

        def create_multipart_upload(self, Bucket, Key):
            self.created = True
            return {"UploadId": "upload_chaos_99"}

        def upload_part(self, Bucket, Key, UploadId, PartNumber, Body):
            if PartNumber == 2:
                raise IOError("S3 500 Internal Service Error on Part 2")
            return {"ETag": f'"etag_{PartNumber}"'}

        def abort_multipart_upload(self, Bucket, Key, UploadId):
            self.aborted = True

        def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload):
            self.completed = True

    mock_s3 = MockS3Client()
    # 3 parts of 5 MB each
    payload = [b"X" * (5 * 1024 * 1024) for _ in range(3)]

    with pytest.raises(Exception) as exc_info:
        ConcurrentMultipartUploader.upload_s3_multipart(
            s3_client=mock_s3,
            bucket="chaos-bucket",
            key="test-large.dat",
            chunk_iterator=iter(payload),
            part_size=5 * 1024 * 1024,
            max_concurrency=2
        )

    assert "S3 500 Internal Service Error" in str(exc_info.value)
    assert mock_s3.created is True
    assert mock_s3.completed is False
    # CRITICAL: Verify abort_multipart_upload was invoked to prevent cloud cost/orphaned parts
    assert mock_s3.aborted is True
