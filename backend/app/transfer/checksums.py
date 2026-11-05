import hashlib
from typing import Optional

try:
    import crc32c
    HAS_CRC32C = True
except ImportError:
    import zlib
    HAS_CRC32C = False


class StreamChecksumCalculator:
    """
    Computes streaming hashes (MD5, SHA-256, CRC32C) on-the-fly
    without buffering the entire stream in memory.
    """

    def __init__(self, algorithm: Optional[str] = "md5"):
        self.algorithm = (algorithm or "none").lower()
        self._md5 = hashlib.md5() if self.algorithm == "md5" else None
        self._sha256 = hashlib.sha256() if self.algorithm == "sha256" else None
        self._crc32c_val = 0 if self.algorithm == "crc32c" else None

    def update(self, chunk: bytes) -> None:
        if not chunk or self.algorithm in ("none", ""):
            return

        if self._md5:
            self._md5.update(chunk)
        elif self._sha256:
            self._sha256.update(chunk)
        elif self._crc32c_val is not None:
            if HAS_CRC32C:
                self._crc32c_val = crc32c.crc32c(chunk, self._crc32c_val)
            else:
                self._crc32c_val = zlib.crc32(chunk, self._crc32c_val) & 0xFFFFFFFF

    def hexdigest(self) -> Optional[str]:
        if self.algorithm in ("none", ""):
            return None
        if self._md5:
            return self._md5.hexdigest()
        if self._sha256:
            return self._sha256.hexdigest()
        if self._crc32c_val is not None:
            return f"{self._crc32c_val:08x}"
        return None
