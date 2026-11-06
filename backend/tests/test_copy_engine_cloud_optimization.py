import os
import time
import shutil
import tempfile
import tracemalloc
from typing import Dict, Any, List, Iterator
from unittest.mock import MagicMock

from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.engine.copy.models import (
    CancellationToken,
    CopyOptions,
    CopyProgress
)
from backend.app.engine.copy.cloud_optimizer import (
    CloudPartSizer,
    CloudStagingPolicy,
    ConcurrentMultipartUploader,
    CloudToCloudPipe,
    CloudTransferOptimizer
)
from backend.app.engine.copy.engine import DataForgeCopyEngine


def test_cloud_part_sizer():
    # S3 minimum part size constraint (5MB)
    s3_small = CloudPartSizer.calculate_optimal_part_size(
        total_bytes=10 * 1024 * 1024,
        provider="aws_s3",
        memory_budget_mb=64,
        max_concurrency=4
    )
    assert s3_small >= 5 * 1024 * 1024
    assert s3_small % (256 * 1024) == 0

    # Large S3 object (1 TB = 1,099,511,627,776 bytes)
    # Must enforce total_bytes / 10,000 >= 109.95 MB
    s3_1tb = CloudPartSizer.calculate_optimal_part_size(
        total_bytes=1024 * 1024 * 1024 * 1024,
        provider="aws_s3",
        memory_budget_mb=64,
        max_concurrency=4
    )
    assert s3_1tb >= 100 * 1024 * 1024
    assert s3_1tb % (256 * 1024) == 0

    # Azure minimum block size (4MB)
    azure_small = CloudPartSizer.calculate_optimal_part_size(
        total_bytes=5 * 1024 * 1024,
        provider="azure_blob",
        memory_budget_mb=64,
        max_concurrency=4
    )
    assert azure_small >= 4 * 1024 * 1024
    assert azure_small % (256 * 1024) == 0

    # Unknown size fallback
    generic_unknown = CloudPartSizer.calculate_optimal_part_size(
        total_bytes=None,
        provider="gcs",
        memory_budget_mb=64,
        max_concurrency=4
    )
    assert generic_unknown >= 4 * 1024 * 1024
    assert generic_unknown % (256 * 1024) == 0


def test_cloud_staging_policy():
    # Binary transfers stream directly with zero disk landing
    assert CloudStagingPolicy.evaluate_policy("csv", "csv", is_binary_copy=True) == CloudStagingPolicy.DIRECT_STREAM
    assert CloudStagingPolicy.evaluate_policy("parquet", "parquet", is_binary_copy=True) == CloudStagingPolicy.DIRECT_STREAM

    # Streaming format transcoding
    assert CloudStagingPolicy.evaluate_policy("csv", "json", is_binary_copy=False) == CloudStagingPolicy.DIRECT_STREAM
    assert CloudStagingPolicy.evaluate_policy("json", "csv", is_binary_copy=False) == CloudStagingPolicy.DIRECT_STREAM

    # Formats requiring random seeking require transparent disk spill
    assert CloudStagingPolicy.evaluate_policy("csv", "avro", is_binary_copy=False) == CloudStagingPolicy.DISK_SPILL
    assert CloudStagingPolicy.evaluate_policy("parquet", "orc", is_binary_copy=False) == CloudStagingPolicy.DISK_SPILL


def test_s3_concurrent_multipart_uploader():
    mock_s3 = MagicMock()
    mock_s3.create_multipart_upload.return_value = {"UploadId": "test-upload-id-123"}
    
    def mock_upload_part(**kwargs):
        part_num = kwargs["PartNumber"]
        return {"ETag": f'"etag-part-{part_num}"'}

    mock_s3.upload_part.side_effect = mock_upload_part
    mock_s3.complete_multipart_upload.return_value = {"ETag": '"complete-final-etag"'}

    # 15 MB payload split into 3 chunks of 5 MB each
    part_size = 5 * 1024 * 1024
    chunk_iter = (b"A" * (1024 * 1024) for _ in range(15))

    res = ConcurrentMultipartUploader.upload_s3_multipart(
        s3_client=mock_s3,
        bucket="my-data-bucket",
        key="lake/dataset.parquet",
        chunk_iterator=chunk_iter,
        part_size=part_size,
        max_concurrency=3
    )

    assert res["success"] is True
    assert res["total_bytes"] == 15 * 1024 * 1024
    assert res["parts_count"] == 3
    assert res["etag"] == "complete-final-etag"

    mock_s3.create_multipart_upload.assert_called_once()
    assert mock_s3.upload_part.call_count == 3
    mock_s3.complete_multipart_upload.assert_called_once()
    mock_s3.abort_multipart_upload.assert_not_called()


def test_azure_block_uploader():
    mock_blob = MagicMock()
    staged_blocks = []

    def mock_stage(block_id, data):
        staged_blocks.append((block_id, len(data)))

    mock_blob.stage_block.side_effect = mock_stage

    # 8 MB payload split into 2 blocks of 4 MB
    block_size = 4 * 1024 * 1024
    chunk_iter = (b"B" * (1024 * 1024) for _ in range(8))

    res = ConcurrentMultipartUploader.upload_azure_blocks(
        blob_client=mock_blob,
        chunk_iterator=chunk_iter,
        block_size=block_size,
        max_concurrency=2
    )

    assert res["success"] is True
    assert res["total_bytes"] == 8 * 1024 * 1024
    assert res["blocks_count"] == 2
    assert len(staged_blocks) == 2
    mock_blob.commit_block_list.assert_called_once()


def test_multipart_abort_on_cancellation():
    mock_s3 = MagicMock()
    mock_s3.create_multipart_upload.return_value = {"UploadId": "abort-test-id"}

    token = CancellationToken()
    # Cancel token before or right as upload starts
    token.cancel("User aborted pipeline")

    chunk_iter = (b"X" * (1024 * 1024) for _ in range(5))

    try:
        ConcurrentMultipartUploader.upload_s3_multipart(
            s3_client=mock_s3,
            bucket="abort-bucket",
            key="abort.bin",
            chunk_iterator=chunk_iter,
            part_size=5 * 1024 * 1024,
            cancellation_token=token
        )
        assert False, "Should have raised InterruptedError on cancellation"
    except InterruptedError:
        pass

    # Verify S3 abort_multipart_upload was invoked to prevent dangling parts!
    mock_s3.abort_multipart_upload.assert_called_once_with(
        Bucket="abort-bucket",
        Key="abort.bin",
        UploadId="abort-test-id"
    )


def test_multipart_retry_on_transient_failure():
    mock_s3 = MagicMock()
    mock_s3.create_multipart_upload.return_value = {"UploadId": "retry-test-id"}
    call_attempts = {"count": 0}

    def flaking_upload_part(**kwargs):
        call_attempts["count"] += 1
        if call_attempts["count"] == 1:
            # First attempt fails with transient network timeout
            raise ConnectionError("Temporary connection reset by peer")
        return {"ETag": '"etag-recovered"'}

    mock_s3.upload_part.side_effect = flaking_upload_part
    mock_s3.complete_multipart_upload.return_value = {"ETag": '"etag-final"'}

    # 5 MB payload (1 part)
    chunk_iter = [b"R" * (5 * 1024 * 1024)]

    res = ConcurrentMultipartUploader.upload_s3_multipart(
        s3_client=mock_s3,
        bucket="retry-bucket",
        key="retry.bin",
        chunk_iterator=iter(chunk_iter),
        part_size=5 * 1024 * 1024,
        max_concurrency=1
    )

    assert res["success"] is True
    # Verify it retried: 1 failure + 1 success = 2 calls
    assert call_attempts["count"] == 2
    mock_s3.complete_multipart_upload.assert_called_once()


def test_cloud_to_cloud_direct_streaming():
    tmp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(tmp_dir, "src_lake")
    dst_dir = os.path.join(tmp_dir, "dst_lake")
    os.makedirs(os.path.join(src_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(dst_dir, "warehouse"), exist_ok=True)

    try:
        # Create a 10 MB source file
        payload = b"CLOUDDATA1234567" * (640 * 1024)  # 10,485,760 bytes (~10 MB)
        src_file = os.path.join(src_dir, "raw", "telemetry.dat")
        with open(src_file, "wb") as f:
            f.write(payload)

        src_conn = LocalStorageConnector({"base_path": src_dir})
        dst_conn = LocalStorageConnector({"base_path": dst_dir})

        opts = CopyOptions(chunk_size_mb=4, buffer_capacity_chunks=2)
        res = DataForgeCopyEngine.execute_cloud_to_cloud(
            src_connector=src_conn,
            dst_connector=dst_conn,
            src_container="raw",
            src_path="telemetry.dat",
            dst_container="warehouse",
            dst_path="telemetry_replicated.dat",
            options=opts
        )

        assert res.success is True
        assert res.bytes_transferred == len(payload)
        assert res.checksum_verified is True
        assert res.source_checksum is not None

        # Verify destination file on disk
        dst_file = os.path.join(dst_dir, "warehouse", "telemetry_replicated.dat")
        assert os.path.exists(dst_file)
        assert os.path.getsize(dst_file) == len(payload)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_cloud_pipe_empirical_benchmark():
    """
    Physical empirical benchmark testing direct cloud-to-cloud pipe throughput
    and verifying peak resident memory consumption remains strictly <= 64 MB.
    """
    tmp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(tmp_dir, "src_pipe")
    dst_dir = os.path.join(tmp_dir, "dst_pipe")
    os.makedirs(os.path.join(src_dir, "in"), exist_ok=True)
    os.makedirs(os.path.join(dst_dir, "out"), exist_ok=True)

    try:
        # 16 MB payload
        payload_16mb = b"Z" * (16 * 1024 * 1024)
        with open(os.path.join(src_dir, "in", "bench_16m.bin"), "wb") as f:
            f.write(payload_16mb)

        src_conn = LocalStorageConnector({"base_path": src_dir})
        dst_conn = LocalStorageConnector({"base_path": dst_dir})

        tracemalloc.start()
        start_time = time.time()

        opts = CopyOptions(chunk_size_mb=4, buffer_capacity_chunks=3, checksum_algorithm="md5")
        res = CloudToCloudPipe.transfer(
            src_connector=src_conn,
            dst_connector=dst_conn,
            src_container="in",
            src_path="bench_16m.bin",
            dst_container="out",
            dst_path="bench_16m.bin",
            options=opts
        )

        duration = max(0.001, time.time() - start_time)
        current_mem, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_ram_mb = peak_mem / (1024 * 1024)

        assert res.success is True
        assert res.bytes_transferred == 16 * 1024 * 1024
        assert res.checksum_verified is True
        # Verify strict memory bound: RAM must be <= 64 MB
        assert peak_ram_mb <= 64.0

        throughput_mb_s = (16.0) / duration
        print(f"\n[BENCHMARK] Cloud-to-Cloud 16 MB Direct Stream: {duration:.4f}s ({throughput_mb_s:.2f} MB/s)")
        print(f"[BENCHMARK] Peak RAM Consumption: {peak_ram_mb:.2f} MB (Budget: 64 MB)")
        print(f"[BENCHMARK] Verified MD5 Hash: {res.destination_checksum}")

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
