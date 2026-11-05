import queue
import threading
from typing import Iterator, Optional
from backend.app.transfer.models import CancellationToken
from backend.app.transfer.checksums import StreamChecksumCalculator


class BoundedTransferBuffer:
    """
    Thread-safe bounded buffer with strict backpressure control.
    Prevents fast cloud sources from exhausting worker RAM when
    destination writer is slower or rate-limited.
    """

    def __init__(
        self,
        max_buffered_chunks: int = 4,
        checksum_algorithm: Optional[str] = "md5",
        cancellation_token: Optional[CancellationToken] = None
    ):
        self._queue: queue.Queue = queue.Queue(maxsize=max_buffered_chunks + 1)
        self._closed = False
        self._error: Optional[Exception] = None
        self._cancellation_token = cancellation_token
        self.checksum = StreamChecksumCalculator(checksum_algorithm)
        self.total_bytes = 0

    def push(self, chunk: bytes, timeout: float = 30.0) -> None:
        """Pushes a chunk into the bounded buffer, blocking if full (backpressure)."""
        if self._cancellation_token:
            self._cancellation_token.raise_if_cancelled()

        if self._error:
            raise self._error

        self.checksum.update(chunk)
        self.total_bytes += len(chunk)

        while True:
            if self._cancellation_token:
                self._cancellation_token.raise_if_cancelled()
            try:
                self._queue.put(chunk, timeout=1.0)
                break
            except queue.Full:
                continue

    def close(self) -> None:
        """Signals that no more chunks will be pushed."""
        self._closed = True
        try:
            self._queue.put(None, timeout=2.0)
        except queue.Full:
            pass

    def abort(self, exc: Exception) -> None:
        """Signals an abort error to the consumer."""
        self._error = exc
        self._queue.put(None)

    def stream_chunks(self) -> Iterator[bytes]:
        """Generator consumed by the destination writer."""
        while True:
            if self._cancellation_token:
                self._cancellation_token.raise_if_cancelled()

            if self._error:
                raise self._error

            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                if self._closed:
                    break
                continue

            if item is None:
                if self._error:
                    raise self._error
                break

            yield item
            self._queue.task_done()
