import time
import threading
from typing import Dict, Any, Optional, List, Callable
from pydantic import BaseModel, Field


class CancellationToken:
    """Thread-safe cooperative cancellation token for long-running multi-cloud transfers."""

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
            raise InterruptedError(f"Transfer cancelled: {self._reason}")


class TransferProgress(BaseModel):
    """Real-time observability metrics emitted during active transfer."""
    bytes_read: int = 0
    bytes_written: int = 0
    records_read: int = 0
    records_written: int = 0
    start_time: float = Field(default_factory=time.time)
    last_update_time: float = Field(default_factory=time.time)
    speed_bytes_per_sec: float = 0.0
    elapsed_seconds: float = 0.0
    status: str = "IN_PROGRESS"


class TransferResult(BaseModel):
    """Final outcome summary of completed or terminated transfer."""
    success: bool
    bytes_transferred: int = 0
    records_transferred: int = 0
    duration_seconds: float = 0.0
    source_checksum: Optional[str] = None
    destination_checksum: Optional[str] = None
    checksum_verified: bool = False
    checksum_algorithm: Optional[str] = None
    error_message: Optional[str] = None
    cancelled: bool = False
