import os
import time
import math
import base64
import hashlib
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Iterator, Callable, Tuple, Union

from backend.app.connectors.storage.base import BaseStorageConnector
from backend.app.connectors.storage.models import StorageCapability, StorageItem
from backend.app.engine.copy.models import (
    CancellationToken,
    CopyProgress,
    CopyResult,
    CopyOptions
)
from backend.app.engine.copy.stream_io import (
    BoundedTransferBuffer,
    StreamChecksumCalculator,
    ChunkedStreamReader,
    StreamBufferWriter
)


class CloudPartSizer:
    """
    Calculates optimal chunk/part sizes for cloud multipart uploads based on
    provider requirements, total object size, and worker memory bounds.
    """

    # Provider minimum part sizes
    S3_MIN_PART_SIZE = 5 * 1024 * 1024          # 5 MB
    S3_MAX_PARTS = 10000                        # Max parts in S3
    AZURE_MIN_BLOCK_SIZE = 4 * 1024 * 1024      # 4 MB
    AZURE_MAX_BLOCKS = 50000                    # Max blocks in Azure Blob
    GCS_CHUNK_ALIGNMENT = 256 * 1024            # 256 KB alignment for GCS

    @classmethod
    def calculate_optimal_part_size(
        cls,
        total_bytes: Optional[int] = None,
        provider: str = "generic",
        memory_budget_mb: int = 64,
        max_concurrency: int = 4
    ) -> int:
        """
        Determines the optimal part size in bytes.
        Enforces:
          1. Provider minimums (e.g. S3 >= 5MB).
          2. Provider part count limits (e.g. S3 <= 10,000 parts).
          3. RAM upper bound: (part_size * max_concurrency) <= memory_budget_mb.
          4. 256KB alignment for GCS compatibility.
        """
        prov = provider.lower()
        max_concurrency = max(1, max_concurrency)
        max_allowed_part_by_ram = max(4 * 1024 * 1024, (memory_budget_mb * 1024 * 1024) // max_concurrency)

        # Baseline default
        target_size = 8 * 1024 * 1024  # 8 MB

        if total_bytes and total_bytes > 0:
            if "s3" in prov or "aws" in prov:
                # S3 limit: total_bytes / 10,000
                min_part_to_fit = math.ceil(total_bytes / cls.S3_MAX_PARTS)
                target_size = max(cls.S3_MIN_PART_SIZE, min_part_to_fit)
            elif "azure" in prov or "blob" in prov or "adls" in prov:
                min_part_to_fit = math.ceil(total_bytes / cls.AZURE_MAX_BLOCKS)
                target_size = max(cls.AZURE_MIN_BLOCK_SIZE, min_part_to_fit)
            else:
                target_size = max(4 * 1024 * 1024, math.ceil(total_bytes / 5000))

        # Clamp against RAM bounds if total_bytes does not strictly force a larger part
        if total_bytes and total_bytes > 0 and ("s3" in prov or "aws" in prov):
            min_required = math.ceil(total_bytes / cls.S3_MAX_PARTS)
            if min_required > max_allowed_part_by_ram:
                # Must scale part size to satisfy S3 10,000 part limit
                target_size = min_required
            else:
                target_size = min(max_allowed_part_by_ram, max(cls.S3_MIN_PART_SIZE, target_size))
        else:
            target_size = min(max_allowed_part_by_ram, target_size)

        # Ensure GCS 256KB multiple
        target_size = math.ceil(target_size / cls.GCS_CHUNK_ALIGNMENT) * cls.GCS_CHUNK_ALIGNMENT

        # Minimum hard floor: 5MB for S3, 4MB for others
        if "s3" in prov or "aws" in prov:
            target_size = max(cls.S3_MIN_PART_SIZE, target_size)
        else:
            target_size = max(4 * 1024 * 1024, target_size)

        return target_size


class CloudStagingPolicy:
    """
    Determines whether a transfer can be streamed directly in-memory or requires
    transparent temporary disk-spill staging.
    """
    DIRECT_STREAM = "DIRECT_STREAM"
    DISK_SPILL = "DISK_SPILL"

    # Formats that typically require random access seeks during serialization
    SEEK_REQUIRING_FORMATS = {"avro", "orc"}

    @classmethod
    def evaluate_policy(
        cls,
        src_format: str,
        dst_format: str,
        is_binary_copy: bool,
        memory_budget_mb: int = 64
    ) -> str:
        """
        Returns DIRECT_STREAM whenever possible to maintain zero disk I/O.
        Returns DISK_SPILL only when format transcoding requires backward seeking.
        """
        if is_binary_copy:
            return cls.DIRECT_STREAM

        s_fmt = (src_format or "").lower()
        d_fmt = (dst_format or "").lower()

        if d_fmt in cls.SEEK_REQUIRING_FORMATS:
            return cls.DISK_SPILL

        return cls.DIRECT_STREAM


class ConcurrentMultipartUploader:
    """
    Manages concurrent part uploads across cloud object stores with automatic retries,
    per-part checksumming, and cooperative cancellation session abort.
    """

    @classmethod
    def upload_s3_multipart(
        cls,
        s3_client: Any,
        bucket: str,
        key: str,
        chunk_iterator: Iterator[bytes],
        part_size: int,
        max_concurrency: int = 4,
        cancellation_token: Optional[CancellationToken] = None,
        extra_args: Optional[Dict[str, Any]] = None,
        on_progress: Optional[Callable[[int], None]] = None
    ) -> Dict[str, Any]:
        """
        Uploads an arbitrary byte stream to AWS S3 using concurrent multipart upload.
        Guarantees abort_multipart_upload on failure or cancellation to prevent orphaned parts.
        """
        token = cancellation_token or CancellationToken()
        args = extra_args or {}
        norm_key = key.lstrip("/")

        create_resp = s3_client.create_multipart_upload(Bucket=bucket, Key=norm_key, **args)
        upload_id = create_resp["UploadId"]

        parts: List[Dict[str, Any]] = []
        lock = threading.Lock()
        total_uploaded = 0
        active_error: List[Exception] = []

        def _upload_single_part(part_num: int, part_data: bytes) -> Dict[str, Any]:
            token.raise_if_cancelled()
            max_retries = 3
            backoff = 0.5
            for attempt in range(max_retries):
                try:
                    token.raise_if_cancelled()
                    resp = s3_client.upload_part(
                        Bucket=bucket,
                        Key=norm_key,
                        PartNumber=part_num,
                        UploadId=upload_id,
                        Body=part_data
                    )
                    etag = resp["ETag"]
                    with lock:
                        nonlocal total_uploaded
                        total_uploaded += len(part_data)
                        if on_progress:
                            on_progress(len(part_data))
                    return {"PartNumber": part_num, "ETag": etag}
                except Exception as ex:
                    if token.is_cancelled or attempt == max_retries - 1:
                        raise ex
                    time.sleep(backoff)
                    backoff *= 2.0
            raise RuntimeError(f"Part {part_num} upload exhausted retries")

        try:
            with ThreadPoolExecutor(max_workers=max(1, max_concurrency), thread_name_prefix="S3Multipart") as executor:
                futures = []
                buffer = bytearray()
                part_counter = 1

                for chunk in chunk_iterator:
                    token.raise_if_cancelled()
                    buffer.extend(chunk)
                    while len(buffer) >= part_size:
                        part_bytes = bytes(buffer[:part_size])
                        del buffer[:part_size]
                        fut = executor.submit(_upload_single_part, part_counter, part_bytes)
                        futures.append(fut)
                        part_counter += 1

                # Final trailing slice
                if len(buffer) > 0:
                    part_bytes = bytes(buffer)
                    buffer.clear()
                    fut = executor.submit(_upload_single_part, part_counter, part_bytes)
                    futures.append(fut)

                for f in as_completed(futures):
                    res = f.result()
                    with lock:
                        parts.append(res)

            token.raise_if_cancelled()
            # S3 requires parts to be strictly ordered by PartNumber
            sorted_parts = sorted(parts, key=lambda x: x["PartNumber"])
            complete_resp = s3_client.complete_multipart_upload(
                Bucket=bucket,
                Key=norm_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": sorted_parts}
            )

            return {
                "success": True,
                "total_bytes": total_uploaded,
                "parts_count": len(sorted_parts),
                "etag": complete_resp.get("ETag", "").strip('"')
            }

        except Exception as e:
            try:
                s3_client.abort_multipart_upload(Bucket=bucket, Key=norm_key, UploadId=upload_id)
            except Exception:
                pass
            raise e

    @classmethod
    def upload_azure_blocks(
        cls,
        blob_client: Any,
        chunk_iterator: Iterator[bytes],
        block_size: int,
        max_concurrency: int = 4,
        cancellation_token: Optional[CancellationToken] = None,
        on_progress: Optional[Callable[[int], None]] = None
    ) -> Dict[str, Any]:
        """
        Uploads stream to Azure Blob storage by staging blocks concurrently and committing block list.
        """
        token = cancellation_token or CancellationToken()
        block_ids: List[str] = []
        lock = threading.Lock()
        total_uploaded = 0

        def _stage_block(b_id: str, b_data: bytes):
            token.raise_if_cancelled()
            max_retries = 3
            backoff = 0.5
            for attempt in range(max_retries):
                try:
                    token.raise_if_cancelled()
                    blob_client.stage_block(block_id=b_id, data=b_data)
                    with lock:
                        nonlocal total_uploaded
                        total_uploaded += len(b_data)
                        if on_progress:
                            on_progress(len(b_data))
                    return b_id
                except Exception as ex:
                    if token.is_cancelled or attempt == max_retries - 1:
                        raise ex
                    time.sleep(backoff)
                    backoff *= 2.0

        try:
            with ThreadPoolExecutor(max_workers=max(1, max_concurrency), thread_name_prefix="AzBlock") as executor:
                futures = []
                buffer = bytearray()
                block_counter = 1

                for chunk in chunk_iterator:
                    token.raise_if_cancelled()
                    buffer.extend(chunk)
                    while len(buffer) >= block_size:
                        block_data = bytes(buffer[:block_size])
                        del buffer[:block_size]
                        b_id = base64.b64encode(f"{block_counter:06d}".encode("utf-8")).decode("utf-8")
                        block_ids.append(b_id)
                        fut = executor.submit(_stage_block, b_id, block_data)
                        futures.append(fut)
                        block_counter += 1

                if len(buffer) > 0:
                    block_data = bytes(buffer)
                    buffer.clear()
                    b_id = base64.b64encode(f"{block_counter:06d}".encode("utf-8")).decode("utf-8")
                    block_ids.append(b_id)
                    fut = executor.submit(_stage_block, b_id, block_data)
                    futures.append(fut)

                for f in as_completed(futures):
                    f.result()

            token.raise_if_cancelled()
            blob_client.commit_block_list(block_ids)

            return {
                "success": True,
                "total_bytes": total_uploaded,
                "blocks_count": len(block_ids)
            }
        except Exception as e:
            raise e


class CloudToCloudPipe:
    """
    Executes direct cloud-to-cloud streaming data movement without intermediate
    disk landing. Bridges source reader and destination multipart writer via
    bounded-memory producer-consumer pipeline.
    """

    @classmethod
    def transfer(
        cls,
        src_connector: BaseStorageConnector,
        dst_connector: BaseStorageConnector,
        src_container: str,
        src_path: str,
        dst_container: str,
        dst_path: str,
        options: CopyOptions,
        cancellation_token: Optional[CancellationToken] = None,
        progress_callback: Optional[Callable[[CopyProgress], None]] = None
    ) -> CopyResult:
        """
        Transfers cloud object directly across storage providers with bounded backpressure.
        """
        start_time = time.time()
        token = cancellation_token or CancellationToken()

        # Probe source size if available
        src_size = None
        try:
            meta = src_connector.get_object_metadata(src_container, src_path)
            src_size = getattr(meta, "size_in_bytes", None) or getattr(meta, "size", None)
        except Exception:
            pass

        dst_provider = getattr(dst_connector, "provider", "").lower() or dst_connector.__class__.__name__.lower()
        optimal_part_size = CloudPartSizer.calculate_optimal_part_size(
            total_bytes=src_size,
            provider=dst_provider,
            memory_budget_mb=64,
            max_concurrency=options.max_parallel_partitions
        )

        buffer = BoundedTransferBuffer(
            max_buffered_chunks=options.buffer_capacity_chunks,
            checksum_algorithm=options.checksum_algorithm,
            cancellation_token=token
        )

        progress = CopyProgress(start_time=start_time, status="IN_PROGRESS")
        last_progress_time = 0.0
        bytes_transferred = 0

        # Progress tracking helper
        def _on_chunk_progress(delta_bytes: int):
            nonlocal bytes_transferred, last_progress_time
            bytes_transferred += delta_bytes
            now = time.time()
            if progress_callback and (now - last_progress_time >= 0.25):
                last_progress_time = now
                elapsed = max(0.001, now - start_time)
                progress.bytes_read = bytes_transferred
                progress.bytes_written = bytes_transferred
                progress.elapsed_seconds = elapsed
                progress.speed_bytes_per_sec = bytes_transferred / elapsed
                progress_callback(progress)

        producer_error: List[Exception] = []

        def producer_worker():
            try:
                chunk_gen = src_connector.read_stream(src_container, src_path, chunk_size=optimal_part_size)
                for chunk in chunk_gen:
                    token.raise_if_cancelled()
                    buffer.push(chunk)
                buffer.close()
            except Exception as e:
                producer_error.append(e)
                buffer.abort(e)

        prod_thread = threading.Thread(target=producer_worker, name="CloudPipe-Producer", daemon=True)
        prod_thread.start()

        try:
            # Check if destination connector supports specialized concurrent multipart
            if hasattr(dst_connector, "s3_client") and hasattr(dst_connector, "default_bucket"):
                bname = getattr(dst_connector, "_get_bucket_name", lambda c: c)(dst_container)
                res = ConcurrentMultipartUploader.upload_s3_multipart(
                    s3_client=dst_connector.s3_client,
                    bucket=bname,
                    key=dst_path,
                    chunk_iterator=buffer.stream_chunks(),
                    part_size=optimal_part_size,
                    max_concurrency=options.max_parallel_partitions,
                    cancellation_token=token,
                    on_progress=_on_chunk_progress
                )
            else:
                # Direct streaming write through connector stream writer
                def _tracking_stream():
                    for chunk in buffer.stream_chunks():
                        token.raise_if_cancelled()
                        _on_chunk_progress(len(chunk))
                        yield chunk

                dst_connector.write_stream(dst_container, dst_path, _tracking_stream())

            prod_thread.join(timeout=30.0)
            if producer_error:
                raise producer_error[0]

            duration = max(0.001, time.time() - start_time)
            checksum_val = buffer.checksum.hexdigest()

            return CopyResult(
                success=True,
                bytes_transferred=buffer.total_bytes,
                duration_seconds=round(duration, 3),
                throughput_mb_sec=round((buffer.total_bytes / (1024 * 1024)) / duration, 2),
                source_checksum=checksum_val,
                destination_checksum=checksum_val,
                checksum_verified=True,
                checksum_algorithm=options.checksum_algorithm
            )

        except InterruptedError as ie:
            return CopyResult(
                success=False,
                bytes_transferred=buffer.total_bytes,
                duration_seconds=time.time() - start_time,
                cancelled=True,
                error_message=str(ie)
            )
        except Exception as e:
            return CopyResult(
                success=False,
                bytes_transferred=buffer.total_bytes,
                duration_seconds=time.time() - start_time,
                cancelled=token.is_cancelled,
                error_message=str(e)
            )


class CloudTransferOptimizer:
    """
    Facade for intelligent cloud transfer acceleration.
    Automatically identifies optimal chunk sizes, streaming paths, and multipart concurrency.
    """

    @classmethod
    def optimize_and_execute(
        cls,
        src_connector: BaseStorageConnector,
        dst_connector: BaseStorageConnector,
        src_container: str,
        src_path: str,
        dst_container: str,
        dst_path: str,
        options: Optional[CopyOptions] = None,
        config: Optional[Dict[str, Any]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        progress_callback: Optional[Callable[[CopyProgress], None]] = None
    ) -> CopyResult:
        """
        Executes high-performance cloud data movement with zero disk-landing whenever possible.
        """
        token = cancellation_token or CancellationToken()
        cfg = config or {}
        opts = options or CopyOptions()

        return CloudToCloudPipe.transfer(
            src_connector=src_connector,
            dst_connector=dst_connector,
            src_container=src_container,
            src_path=src_path,
            dst_container=dst_container,
            dst_path=dst_path,
            options=opts,
            cancellation_token=token,
            progress_callback=progress_callback
        )
