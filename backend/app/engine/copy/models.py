import time
import threading
from typing import Dict, Any, Optional, List, Callable, Union
from pydantic import BaseModel, Field


class CancellationToken:
    """Thread-safe cooperative cancellation token for Copy Engine operations."""

    def __init__(self):
        self._is_cancelled = threading.Event()
        self._reason = ""

    def cancel(self, reason: str = "User cancelled execution"):
        self._reason = reason
        self._is_cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled.is_set()

    @property
    def reason(self) -> str:
        return self._reason

    def raise_if_cancelled(self):
        if self._is_cancelled.is_set():
            raise InterruptedError(f"Copy operation cancelled: {self._reason}")


class PartitionSpec(BaseModel):
    """Defines a slice of data for partitioned parallel execution."""
    partition_id: str
    slice_index: int = 0
    total_slices: int = 1
    partition_column: Optional[str] = None
    range_min: Optional[Union[int, float, str]] = None
    range_max: Optional[Union[int, float, str]] = None
    filter_expr: Optional[str] = None
    file_items: Optional[List[str]] = None
    status: str = "Pending"  # Pending, InProgress, Succeeded, Failed
    rows_transferred: int = 0
    bytes_transferred: int = 0
    error_message: Optional[str] = None


class CheckpointToken(BaseModel):
    """State persistence record for a completed partition."""
    partition_id: str
    completed_at: float = Field(default_factory=time.time)
    rows_transferred: int = 0
    bytes_transferred: int = 0
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CopyProgress(BaseModel):
    """Real-time progress telemetry emitted during copy operations."""
    bytes_read: int = 0
    bytes_written: int = 0
    records_read: int = 0
    records_written: int = 0
    start_time: float = Field(default_factory=time.time)
    last_update_time: float = Field(default_factory=time.time)
    speed_bytes_per_sec: float = 0.0
    elapsed_seconds: float = 0.0
    active_partitions: int = 1
    completed_partitions: int = 0
    total_partitions: int = 1
    status: str = "IN_PROGRESS"


class CopyOptions(BaseModel):
    """Configurable execution parameters for DataForge Copy Engine."""
    chunk_size_mb: int = Field(default=8, ge=1, le=64)
    buffer_capacity_chunks: int = Field(default=4, ge=1, le=16)
    batch_size: int = Field(default=5000, ge=1)
    checksum_algorithm: str = "md5"  # md5, sha256, none
    max_parallel_partitions: int = Field(default=4, ge=1, le=32)
    column_mappings: List[Dict[str, Any]] = Field(default_factory=list)
    write_mode: str = "append"  # append, overwrite, upsert
    key_columns: List[str] = Field(default_factory=list)
    auto_create_table: bool = True
    pre_copy_script: Optional[str] = None
    post_copy_script: Optional[str] = None
    schema_name: Optional[str] = None
    watermark_column: Optional[str] = None
    watermark_value: Optional[Any] = None


class CopyResult(BaseModel):
    """Comprehensive execution summary returned by Copy Engine."""
    success: bool
    bytes_transferred: int = 0
    records_transferred: int = 0
    duration_seconds: float = 0.0
    throughput_mb_sec: float = 0.0
    source_checksum: Optional[str] = None
    destination_checksum: Optional[str] = None
    checksum_verified: bool = False
    checksum_algorithm: Optional[str] = None
    partitions_total: int = 1
    partitions_succeeded: int = 1
    partitions_failed: int = 0
    partition_details: List[PartitionSpec] = Field(default_factory=list)
    output_variables: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    cancelled: bool = False
