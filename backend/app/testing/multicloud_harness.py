import os
import io
import time
import socket
import shutil
import tempfile
import subprocess
from contextlib import contextmanager
from typing import Iterator, Dict, Any, Optional
from datetime import datetime, timezone

import boto3
try:
    from moto import mock_aws
except ImportError:
    mock_aws = None

from backend.app.connectors.storage.models import StorageItem, StorageCapability
from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.connectors.storage.aws_s3 import AmazonS3Connector
from backend.app.connectors.storage.azure_blob import AzureBlobStorageConnector
from backend.app.connectors.storage.azure_adls import AzureDataLakeStorageConnector
from backend.app.connectors.storage.gcp_storage import GoogleCloudStorageConnector
from backend.app.connectors.sqlite import SQLiteConnector


AZURITE_PORT = 10150
AZURITE_ACCOUNT_NAME = "devstoreaccount1"
AZURITE_ACCOUNT_KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="


def is_port_listening(host: str, port: int, timeout: float = 0.3) -> bool:
    """Checks whether a TCP socket port is actively listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except Exception:
        return False


@contextmanager
def azurite_context(port: int = AZURITE_PORT) -> Iterator[str]:
    """
    Context manager ensuring Azurite emulator is running on the specified port.
    If Azurite is already running, reuses the existing instance.
    Otherwise, starts Azurite in a background subprocess and cleans up on exit.
    Yields connection string.
    """
    conn_str = (
        f"DefaultEndpointsProtocol=http;AccountName={AZURITE_ACCOUNT_NAME};"
        f"AccountKey={AZURITE_ACCOUNT_KEY};BlobEndpoint=http://127.0.0.1:{port}/{AZURITE_ACCOUNT_NAME};"
    )

    if is_port_listening("127.0.0.1", port):
        yield conn_str
        return

    tmp_dir = tempfile.mkdtemp(prefix="azurite_harness_")
    node_path = os.path.expanduser("~/.local/node/bin")
    env = os.environ.copy()
    env["PATH"] = f"{node_path}:{env.get('PATH', '')}"

    proc = subprocess.Popen(
        [
            "azurite",
            "--silent",
            "--blobPort", str(port),
            "--queuePort", str(port + 1),
            "--tablePort", str(port + 2),
            "--loose",
            "--skipApiVersionCheck",
            "-l", tmp_dir
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait up to 5 seconds for port to open
    started = False
    for _ in range(50):
        if is_port_listening("127.0.0.1", port):
            started = True
            break
        time.sleep(0.1)

    if not started:
        proc.kill()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Azurite failed to start on port {port} within 5 seconds.")

    try:
        yield conn_str
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        shutil.rmtree(tmp_dir, ignore_errors=True)


class FakeGcsBlob:
    """In-memory GCS Blob simulator conforming to google.cloud.storage.Blob."""
    def __init__(self, name: str, bucket: Any, content: bytes = b"", content_type: str = "application/octet-stream"):
        self.name = name
        self.bucket = bucket
        self.content = content
        self.content_type = content_type
        self.storage_class = "STANDARD"
        self.size = len(content)
        self.updated = datetime.now(timezone.utc)
        self.etag = f"etag_{name}_{len(content)}"
        self.metadata = {}

    def open(self, mode: str = "rb", content_type: Optional[str] = None, chunk_size: Optional[int] = None):
        if "w" in mode:
            blob_ref = self
            class _Writer(io.BytesIO):
                def close(s):
                    blob_ref.content = s.getvalue()
                    blob_ref.size = len(blob_ref.content)
                    blob_ref.updated = datetime.now(timezone.utc)
                    blob_ref.etag = f"etag_{blob_ref.name}_{blob_ref.size}"
                    if content_type:
                        blob_ref.content_type = content_type
                    super().close()
            return _Writer()
        else:
            return io.BytesIO(self.content)

    def delete(self):
        if self.name in self.bucket._blobs:
            del self.bucket._blobs[self.name]


class FakeGcsBucket:
    """In-memory GCS Bucket simulator conforming to google.cloud.storage.Bucket."""
    def __init__(self, name: str, exists: bool = True):
        self.name = name
        self._exists = exists
        self._blobs = {}

    def exists(self) -> bool:
        return self._exists

    def blob(self, name: str, chunk_size: Optional[int] = None) -> FakeGcsBlob:
        if name not in self._blobs:
            self._blobs[name] = FakeGcsBlob(name, self)
        return self._blobs[name]

    def get_blob(self, name: str) -> Optional[FakeGcsBlob]:
        return self._blobs.get(name)

    def list_blobs(self, prefix: str = "", delimiter: Optional[str] = None):
        res = []
        for name, b in self._blobs.items():
            if not prefix or name.startswith(prefix):
                res.append(b)
        return res

    def delete_blobs(self, blobs):
        for b in blobs:
            if b.name in self._blobs:
                del self._blobs[b.name]

    def copy_blob(self, src_blob, dst_bucket, dst_name):
        new_b = dst_bucket.blob(dst_name)
        new_b.content = src_blob.content
        new_b.size = len(new_b.content)
        new_b.content_type = src_blob.content_type
        new_b.metadata = dict(src_blob.metadata)
        new_b.updated = datetime.now(timezone.utc)
        dst_bucket._blobs[dst_name] = new_b
        return new_b


class FakeGcsClient:
    """In-memory GCS Client simulator conforming to google.cloud.storage.Client."""
    def __init__(self, project: str = "test-dataforge-project"):
        self.project = project
        self._buckets = {}

    def bucket(self, name: str) -> FakeGcsBucket:
        if name not in self._buckets:
            self._buckets[name] = FakeGcsBucket(name)
        return self._buckets[name]

    def get_bucket(self, name: str) -> FakeGcsBucket:
        if name not in self._buckets:
            self._buckets[name] = FakeGcsBucket(name)
        return self._buckets[name]

    def list_buckets(self):
        return list(self._buckets.values())

    def close(self):
        pass


def create_mock_gcs_connector(bucket_name: str = "dataforge-gcs-lake") -> GoogleCloudStorageConnector:
    """Creates a configured GCS connector with in-memory client attached."""
    client = FakeGcsClient()
    client.bucket(bucket_name)
    conn = GoogleCloudStorageConnector({"bucket": bucket_name, "project_id": "test-dataforge-project"})
    conn._client = client
    conn._connected = True
    return conn


class VirtualLargeSourceConnector(LocalStorageConnector):
    """Generates synthetic multi-chunk binary stream for testing 1GB+ transfers with bounded RAM."""
    def __init__(self, total_bytes: int = 1024 * 1024 * 1024, chunk_size: int = 8 * 1024 * 1024):
        super().__init__({"base_path": "/tmp"})
        self.total_bytes = total_bytes
        self.chunk_size = chunk_size
        self._sample_chunk = b"X" * chunk_size

    def read_stream(self, container: str, object_key: str, chunk_size: int = 8 * 1024 * 1024) -> Iterator[bytes]:
        bytes_yielded = 0
        while bytes_yielded < self.total_bytes:
            remaining = self.total_bytes - bytes_yielded
            size = min(self.chunk_size, remaining)
            yield self._sample_chunk[:size]
            bytes_yielded += size


class VirtualLargeSinkConnector(LocalStorageConnector):
    """Consumes synthetic binary stream, validating byte count and discarding data without RAM usage."""
    def __init__(self):
        super().__init__({"base_path": "/tmp"})
        self.bytes_received = 0

    def write_stream(
        self,
        container: str,
        object_key: str,
        stream: Iterator[bytes],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> int:
        self.bytes_received = 0
        for chunk in stream:
            self.bytes_received += len(chunk)
        return self.bytes_received
