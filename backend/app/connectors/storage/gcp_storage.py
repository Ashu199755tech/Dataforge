import time
from typing import List, Dict, Any, Iterator, Optional, Set
from datetime import datetime

from backend.app.connectors.base import ConnectionTestResult
from backend.app.connectors.storage.base import BaseStorageConnector
from backend.app.connectors.storage.models import (
    StorageItem,
    StorageCapability,
    StorageErrorCategory,
    StorageException
)
from backend.app.connectors.storage.registry import StorageProviderRegistry
from backend.app.connectors.storage.gcp_auth import create_gcp_storage_client

try:
    from google.cloud import storage
    from google.api_core.exceptions import (
        GoogleAPICallError,
        NotFound,
        Forbidden,
        Unauthorized,
        BadRequest,
        TooManyRequests
    )
    HAS_GCP_STORAGE = True
except ImportError:
    HAS_GCP_STORAGE = False


class GoogleCloudStorageConnector(BaseStorageConnector):
    """
    Google Cloud Platform (GCP) Cloud Storage Connector.
    Supports Service Account JSON, Application Default Credentials (ADC),
    and Workload Identity Federation.
    Implements bucket discovery, prefix browsing, chunked streaming,
    resumable session uploads, and metadata inspection.
    """

    # GCS resumable upload chunk size must be a multiple of 256 KB (262,144 bytes)
    RESUMABLE_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunk size

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not HAS_GCP_STORAGE:
            raise StorageException(
                "google-cloud-storage is not installed. Install with: pip install google-cloud-storage google-auth",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider="gcp_storage"
            )
        self.default_bucket = config.get("bucket") or config.get("bucket_name")
        self.project_id = config.get("project_id")
        self._client = None

    def get_capabilities(self) -> Set[StorageCapability]:
        return {
            StorageCapability.BUCKET_DISCOVERY,
            StorageCapability.DIRECTORY_OPERATIONS,
            StorageCapability.STREAM_READ,
            StorageCapability.STREAM_WRITE,
            StorageCapability.RESUMABLE_UPLOAD,
            StorageCapability.STORAGE_TIERING,
            StorageCapability.PRESIGNED_URLS,
            StorageCapability.DELETE_OBJECT,
            StorageCapability.COPY_OBJECT,
        }

    @property
    def client(self):
        if self._client is None:
            self.connect()
        return self._client

    def connect(self) -> None:
        self._client = create_gcp_storage_client(self.config)
        self._connected = True

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._connected = False

    def _classify_and_raise(self, err: Exception, operation: str) -> None:
        if isinstance(err, StorageException):
            raise err
        msg = str(err)
        cat = StorageErrorCategory.UNKNOWN
        status = getattr(err, "code", None)

        if isinstance(err, (Unauthorized, Forbidden)) or status in (401, 403):
            cat = StorageErrorCategory.AUTHENTICATION_FAILED
        elif isinstance(err, NotFound) or status == 404:
            cat = StorageErrorCategory.NOT_FOUND
        elif isinstance(err, TooManyRequests) or status == 429:
            cat = StorageErrorCategory.RATE_LIMITED
        elif isinstance(err, BadRequest) or status == 400:
            cat = StorageErrorCategory.INVALID_PATH
        elif "timeout" in msg.lower():
            cat = StorageErrorCategory.NETWORK_TIMEOUT

        raise StorageException(
            f"GCP Storage error during {operation}: {msg}",
            category=cat,
            provider="gcp_storage",
            status_code=status,
            original_exception=err
        )

    # ------------------------------------------------------------------
    # Connection Testing
    # ------------------------------------------------------------------

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            client = self.client
            if self.default_bucket:
                bucket = client.bucket(self.default_bucket)
                exists = bucket.exists()
                if not exists:
                    return ConnectionTestResult(
                        success=False,
                        message=f"GCS bucket '{self.default_bucket}' does not exist or access denied."
                    )
                ver_msg = f"GCS bucket '{self.default_bucket}' accessible"
            else:
                # Ping by discovering first bucket
                next(iter(client.list_buckets(max_results=1)), None)
                ver_msg = "Google Cloud Storage API accessible"

            latency = round((time.time() - start) * 1000, 2)
            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to GCP Storage: {ver_msg}",
                latency_ms=latency,
                server_version="Google Cloud Storage Engine"
            )
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            clean_err = StorageException._sanitize_message(str(e))
            return ConnectionTestResult(
                success=False,
                message=f"GCP Storage connection failed: {clean_err}",
                latency_ms=latency
            )

    # ------------------------------------------------------------------
    # Bucket & Prefix Browsing
    # ------------------------------------------------------------------

    def list_containers(self) -> List[str]:
        try:
            return [b.name for b in self.client.list_buckets()]
        except Exception as e:
            self._classify_and_raise(e, "list_containers")

    def _get_bucket_name(self, container: Optional[str]) -> str:
        bname = container or self.default_bucket
        if not bname:
            raise StorageException(
                "No GCS bucket specified and no default configured.",
                category=StorageErrorCategory.INVALID_PATH,
                provider="gcp_storage"
            )
        return bname

    def list_directories(self, container: str, prefix: str = "") -> List[str]:
        bname = self._get_bucket_name(container)
        norm_prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        try:
            bucket = self.client.bucket(bname)
            iterator = self.client.list_blobs(bucket, prefix=norm_prefix, delimiter="/")
            # Consume iterator to populate prefixes
            list(iterator)
            return sorted([p.rstrip("/") for p in iterator.prefixes])
        except Exception as e:
            self._classify_and_raise(e, "list_directories")

    def list_files(
        self,
        container: str,
        prefix: str = "",
        recursive: bool = False,
        limit: Optional[int] = None
    ) -> Iterator[StorageItem]:
        bname = self._get_bucket_name(container)
        norm_prefix = prefix.strip("/")
        if norm_prefix:
            norm_prefix += "/" if not norm_prefix.endswith("/") else ""

        try:
            bucket = self.client.bucket(bname)
            count = 0

            if recursive:
                for blob in self.client.list_blobs(bucket, prefix=norm_prefix):
                    if blob.name.endswith("/") and blob.size == 0:
                        continue
                    yield StorageItem(
                        name=blob.name.split("/")[-1],
                        path=blob.name,
                        is_directory=False,
                        size_in_bytes=blob.size or 0,
                        last_modified=blob.updated,
                        content_type=blob.content_type,
                        etag=blob.etag.strip('"') if blob.etag else None,
                        storage_tier=blob.storage_class or "STANDARD"
                    )
                    count += 1
                    if limit and count >= limit:
                        return
            else:
                iterator = self.client.list_blobs(bucket, prefix=norm_prefix, delimiter="/")
                for blob in iterator:
                    if blob.name.endswith("/") and blob.size == 0:
                        continue
                    yield StorageItem(
                        name=blob.name.split("/")[-1],
                        path=blob.name,
                        is_directory=False,
                        size_in_bytes=blob.size or 0,
                        last_modified=blob.updated,
                        content_type=blob.content_type,
                        etag=blob.etag.strip('"') if blob.etag else None,
                        storage_tier=blob.storage_class or "STANDARD"
                    )
                    count += 1
                    if limit and count >= limit:
                        return

                for p in iterator.prefixes:
                    yield StorageItem(
                        name=p.rstrip("/").split("/")[-1],
                        path=p.rstrip("/"),
                        is_directory=True,
                        size_in_bytes=0,
                        content_type="inode/directory"
                    )
                    count += 1
                    if limit and count >= limit:
                        return
        except Exception as e:
            self._classify_and_raise(e, "list_files")

    def get_object_metadata(self, container: str, object_key: str) -> StorageItem:
        bname = self._get_bucket_name(container)
        norm_key = object_key.lstrip("/")
        try:
            bucket = self.client.bucket(bname)
            blob = bucket.get_blob(norm_key)
            if blob is None:
                raise StorageException(
                    f"GCS object '{bname}/{norm_key}' not found.",
                    category=StorageErrorCategory.NOT_FOUND,
                    provider="gcp_storage",
                    status_code=404
                )
            return StorageItem(
                name=norm_key.split("/")[-1],
                path=norm_key,
                is_directory=False,
                size_in_bytes=blob.size or 0,
                last_modified=blob.updated,
                content_type=blob.content_type or "application/octet-stream",
                etag=blob.etag.strip('"') if blob.etag else None,
                metadata=blob.metadata or {},
                storage_tier=blob.storage_class or "STANDARD"
            )
        except Exception as e:
            self._classify_and_raise(e, "get_object_metadata")

    # ------------------------------------------------------------------
    # Streaming Read & Resumable Write
    # ------------------------------------------------------------------

    def read_stream(
        self,
        container: str,
        object_key: str,
        chunk_size: int = 4 * 1024 * 1024
    ) -> Iterator[bytes]:
        bname = self._get_bucket_name(container)
        norm_key = object_key.lstrip("/")
        try:
            bucket = self.client.bucket(bname)
            blob = bucket.get_blob(norm_key)
            if blob is None:
                raise StorageException(
                    f"GCS object '{bname}/{norm_key}' not found.",
                    category=StorageErrorCategory.NOT_FOUND,
                    provider="gcp_storage",
                    status_code=404
                )

            with blob.open("rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            self._classify_and_raise(e, "read_stream")

    def write_stream(
        self,
        container: str,
        object_key: str,
        stream: Iterator[bytes],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> int:
        bname = self._get_bucket_name(container)
        norm_key = object_key.lstrip("/")
        try:
            bucket = self.client.bucket(bname)
            blob = bucket.blob(norm_key, chunk_size=self.RESUMABLE_CHUNK_SIZE)
            if metadata:
                blob.metadata = metadata

            total_bytes = 0
            with blob.open("wb", content_type=content_type) as f:
                for chunk in stream:
                    f.write(chunk)
                    total_bytes += len(chunk)

            return total_bytes
        except Exception as e:
            self._classify_and_raise(e, "write_stream")

    # ------------------------------------------------------------------
    # Mutation: Delete, Copy
    # ------------------------------------------------------------------

    def delete_file(self, container: str, object_key: str) -> bool:
        bname = self._get_bucket_name(container)
        norm_key = object_key.lstrip("/")
        try:
            bucket = self.client.bucket(bname)
            blob = bucket.get_blob(norm_key)
            if blob:
                blob.delete()
                return True
            return False
        except Exception as e:
            self._classify_and_raise(e, "delete_file")

    def delete_directory(self, container: str, prefix: str) -> int:
        bname = self._get_bucket_name(container)
        norm_prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        try:
            bucket = self.client.bucket(bname)
            blobs = list(self.client.list_blobs(bucket, prefix=norm_prefix))
            if blobs:
                bucket.delete_blobs(blobs)
            return len(blobs)
        except Exception as e:
            self._classify_and_raise(e, "delete_directory")

    def copy_file(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        try:
            src_bname = self._get_bucket_name(src_container)
            dst_bname = self._get_bucket_name(dst_container)
            src_bucket = self.client.bucket(src_bname)
            src_blob = src_bucket.get_blob(src_key.lstrip("/"))
            if not src_blob:
                raise StorageException(
                    f"Source object '{src_bname}/{src_key}' not found.",
                    category=StorageErrorCategory.NOT_FOUND,
                    provider="gcp_storage",
                    status_code=404
                )
            dst_bucket = self.client.bucket(dst_bname)
            src_bucket.copy_blob(src_blob, dst_bucket, dst_key.lstrip("/"))
            return True
        except Exception as e:
            self._classify_and_raise(e, "copy_file")


# Register concrete connector into provider registry
StorageProviderRegistry._providers["gcp_storage"]["connector_class"] = GoogleCloudStorageConnector
