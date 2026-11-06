import time
import threading
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
from typing import Dict, Any, List, Optional, Callable
from backend.app.engine.copy.models import (
    CancellationToken,
    CopyProgress,
    CopyResult,
    PartitionSpec,
    CheckpointToken
)
from backend.app.engine.copy.checkpoints import PartitionCheckpointLedger


class ParallelCopyCoordinator:
    """
    Coordinates multi-threaded parallel data movement across partitioned slices.
    Features:
      - Thread pool execution bounded by max_parallel_partitions.
      - Resumes from partition checkpoints (skips already completed slices).
      - Thread-safe aggregated progress tracking with live throughput estimation.
      - Cooperative cancellation propagation across all worker threads.
      - Error isolation: individual partition failure does not corrupt other slices.
    """

    def __init__(
        self,
        ledger: PartitionCheckpointLedger,
        max_parallel_partitions: int = 4,
        cancellation_token: Optional[CancellationToken] = None,
        progress_callback: Optional[Callable[[CopyProgress], None]] = None
    ):
        self.ledger = ledger
        self.max_parallel_partitions = max(1, min(32, max_parallel_partitions))
        self.cancellation_token = cancellation_token or CancellationToken()
        self.progress_callback = progress_callback

        self._lock = threading.Lock()
        self._total_bytes_transferred = 0
        self._total_records_transferred = 0
        self._active_workers = 0
        self._start_time = time.time()
        self._last_progress_emit = 0.0

    def execute(
        self,
        worker_fn: Callable[[PartitionSpec, CancellationToken, Callable[[int, int], None]], Dict[str, Any]]
    ) -> CopyResult:
        """
        Executes worker_fn concurrently for each pending partition in the ledger.
        worker_fn signature: (partition_spec, token, progress_updater) -> dict(rows, bytes, checksum, metadata)
        """
        self._start_time = time.time()
        self._total_bytes_transferred = sum(p.bytes_transferred for p in self.ledger.partitions.values() if p.status == "Succeeded")
        self._total_records_transferred = sum(p.rows_transferred for p in self.ledger.partitions.values() if p.status == "Succeeded")

        pending_partitions = self.ledger.get_pending_partitions()
        total_partitions = len(self.ledger.partitions)

        # All partitions already completed in earlier run
        if not pending_partitions:
            stats = self.ledger.get_total_stats()
            return CopyResult(
                success=True,
                bytes_transferred=stats["total_bytes"],
                records_transferred=stats["total_rows"],
                duration_seconds=0.0,
                throughput_mb_sec=0.0,
                partitions_total=total_partitions,
                partitions_succeeded=stats["succeeded_partitions"],
                partitions_failed=stats["failed_partitions"],
                partition_details=list(self.ledger.partitions.values())
            )

        partition_errors: Dict[str, str] = {}
        futures = []

        def _make_progress_updater(part_id: str):
            def updater(bytes_delta: int, records_delta: int):
                with self._lock:
                    self._total_bytes_transferred += bytes_delta
                    self._total_records_transferred += records_delta
                    now = time.time()
                    if self.progress_callback and (now - self._last_progress_emit >= 0.25):
                        self._last_progress_emit = now
                        elapsed = max(0.001, now - self._start_time)
                        progress = CopyProgress(
                            bytes_read=self._total_bytes_transferred,
                            bytes_written=self._total_bytes_transferred,
                            records_read=self._total_records_transferred,
                            records_written=self._total_records_transferred,
                            start_time=self._start_time,
                            last_update_time=now,
                            speed_bytes_per_sec=self._total_bytes_transferred / elapsed,
                            elapsed_seconds=elapsed,
                            active_partitions=self._active_workers,
                            completed_partitions=sum(1 for p in self.ledger.partitions.values() if p.status == "Succeeded"),
                            total_partitions=total_partitions,
                            status="IN_PROGRESS"
                        )
                        try:
                            self.progress_callback(progress)
                        except Exception:
                            pass
            return updater

        def _worker_wrapper(spec: PartitionSpec):
            part_id = spec.partition_id
            if self.cancellation_token.is_cancelled:
                self.ledger.mark_failed(part_id, "Cancelled before start")
                return

            with self._lock:
                self._active_workers += 1
                self.ledger.mark_in_progress(part_id)

            updater = _make_progress_updater(part_id)

            try:
                result = worker_fn(spec, self.cancellation_token, updater)
                rows = result.get("rows_transferred", 0) if isinstance(result, dict) else getattr(result, "rows_transferred", 0)
                bytes_cnt = result.get("bytes_transferred", 0) if isinstance(result, dict) else getattr(result, "bytes_transferred", 0)
                checksum = result.get("checksum") if isinstance(result, dict) else getattr(result, "checksum", None)
                meta = result.get("metadata", {}) if isinstance(result, dict) else getattr(result, "metadata", {})

                with self._lock:
                    self.ledger.mark_completed(
                        partition_id=part_id,
                        rows_transferred=rows,
                        bytes_transferred=bytes_cnt,
                        checksum=checksum,
                        metadata=meta
                    )
            except InterruptedError as ie:
                with self._lock:
                    self.ledger.mark_failed(part_id, f"Cancelled: {ie}")
                    partition_errors[part_id] = str(ie)
            except Exception as ex:
                with self._lock:
                    self.ledger.mark_failed(part_id, str(ex))
                    partition_errors[part_id] = str(ex)
            finally:
                with self._lock:
                    self._active_workers -= 1

        workers_count = min(self.max_parallel_partitions, len(pending_partitions))
        with ThreadPoolExecutor(max_workers=workers_count, thread_name_prefix="CopyCoord") as executor:
            for spec in pending_partitions:
                if self.cancellation_token.is_cancelled:
                    self.ledger.mark_failed(spec.partition_id, "Operation cancelled")
                    continue
                future = executor.submit(_worker_wrapper, spec)
                futures.append(future)

            wait(futures, return_when=ALL_COMPLETED)

        duration = max(0.001, time.time() - self._start_time)
        stats = self.ledger.get_total_stats()
        is_all_success = self.ledger.is_all_completed()
        is_cancelled = self.cancellation_token.is_cancelled

        # Final progress notification
        if self.progress_callback:
            try:
                self.progress_callback(CopyProgress(
                    bytes_read=stats["total_bytes"],
                    bytes_written=stats["total_bytes"],
                    records_read=stats["total_rows"],
                    records_written=stats["total_rows"],
                    start_time=self._start_time,
                    last_update_time=time.time(),
                    speed_bytes_per_sec=stats["total_bytes"] / duration,
                    elapsed_seconds=duration,
                    active_partitions=0,
                    completed_partitions=stats["succeeded_partitions"],
                    total_partitions=total_partitions,
                    status="COMPLETED" if is_all_success else ("CANCELLED" if is_cancelled else "FAILED")
                ))
            except Exception:
                pass

        error_summary = None
        if partition_errors:
            error_summary = "; ".join(f"[{pid}]: {err}" for pid, err in partition_errors.items())

        return CopyResult(
            success=is_all_success,
            bytes_transferred=stats["total_bytes"],
            records_transferred=stats["total_rows"],
            duration_seconds=round(duration, 3),
            throughput_mb_sec=round((stats["total_bytes"] / (1024 * 1024)) / duration, 2),
            partitions_total=total_partitions,
            partitions_succeeded=stats["succeeded_partitions"],
            partitions_failed=stats["failed_partitions"],
            partition_details=list(self.ledger.partitions.values()),
            cancelled=is_cancelled,
            error_message=error_summary
        )
