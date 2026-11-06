import io
import queue
import hashlib
import threading
from typing import Iterator, Optional, Dict, Any
from backend.app.engine.copy.models import CancellationToken


class StreamChecksumCalculator:
    """Computes streaming cryptographic digests (MD5, SHA-256) on the fly."""

    def __init__(self, algorithm: str = "md5"):
        self.algorithm = (algorithm or "md5").lower()
        if self.algorithm == "sha256":
            self._hasher = hashlib.sha256()
        elif self.algorithm == "md5":
            self._hasher = hashlib.md5()
        elif self.algorithm in ("none", "disabled"):
            self._hasher = None
        else:
            self._hasher = hashlib.md5()

    def update(self, chunk: bytes) -> None:
        if self._hasher and chunk:
            self._hasher.update(chunk)

    def hexdigest(self) -> Optional[str]:
        return self._hasher.hexdigest() if self._hasher else None


class ChunkedStreamReader(io.RawIOBase):
    """
    Adapts an Iterator[bytes] generator or chunked stream into a standard
    read-only binary stream (io.RawIOBase) without loading the full payload into memory.
    """

    def __init__(self, chunk_iterator: Iterator[bytes], cancellation_token: Optional[CancellationToken] = None):
        super().__init__()
        self._chunks = chunk_iterator
        self._current_chunk = b""
        self._pos = 0
        self._total_read = 0
        self._exhausted = False
        self._cancellation_token = cancellation_token

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def writable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._total_read

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 1 and offset == 0:
            return self._total_read
        return self._total_read

    def readinto(self, b) -> int:
        if self._cancellation_token:
            self._cancellation_token.raise_if_cancelled()

        if self._exhausted:
            return 0

        # Refill current chunk if empty
        while not self._current_chunk or self._pos >= len(self._current_chunk):
            try:
                self._current_chunk = next(self._chunks)
                self._pos = 0
                if not self._current_chunk:
                    continue
            except StopIteration:
                self._exhausted = True
                return 0

        available = len(self._current_chunk) - self._pos
        to_copy = min(len(b), available)
        b[:to_copy] = self._current_chunk[self._pos:self._pos + to_copy]
        self._pos += to_copy
        self._total_read += to_copy
        return to_copy

    def read(self, size: int = -1) -> bytes:
        if self._cancellation_token:
            self._cancellation_token.raise_if_cancelled()

        if size == -1:
            # Note: caller asking for full read will consume stream, but readinto is preferred
            chunks = []
            while True:
                buf = bytearray(64 * 1024)
                n = self.readinto(buf)
                if n == 0:
                    break
                chunks.append(bytes(buf[:n]))
            return b"".join(chunks)

        buf = bytearray(size)
        n = self.readinto(buf)
        return bytes(buf[:n])


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


class StreamBufferWriter(io.RawIOBase):
    """
    File-like writable stream (io.RawIOBase) that pushes chunks directly
    into a BoundedTransferBuffer as bytes are written, maintaining bounded memory.
    """

    def __init__(self, buffer: BoundedTransferBuffer, flush_threshold: int = 4 * 1024 * 1024):
        super().__init__()
        self._buffer = buffer
        self._threshold = max(1, flush_threshold)
        self._current_chunk = bytearray()
        self._total_written = 0

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def tell(self) -> int:
        return self._total_written

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 1 and offset == 0:
            return self._total_written
        return self._total_written

    def write(self, b: bytes) -> int:
        if not b:
            return 0
        self._current_chunk.extend(b)
        self._total_written += len(b)
        if len(self._current_chunk) >= self._threshold:
            self.flush()
        return len(b)

    def flush(self) -> None:
        if self._current_chunk:
            self._buffer.push(bytes(self._current_chunk))
            self._current_chunk.clear()

    def close(self) -> None:
        self.flush()
        self._buffer.close()
        super().close()
