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
from backend.app.connectors.storage.azure_auth import build_azure_credentials_and_endpoints

try:
    from azure.storage.blob import (
        BlobServiceClient,
        BlobClient,
        ContainerClient,
        ContentSettings
    )
    from azure.core.exceptions import (
        HttpResponseError,
        ResourceNotFoundError,
        ClientAuthenticationError,
        ServiceRequestError
    )
    HAS_AZURE_BLOB = True
except ImportError:
    HAS_AZURE_BLOB = False


class AzureBlobStorageConnector(BaseStorageConnector):
    """
    Microsoft Azure Blob Storage Connector.
    Supports Service Principal, Managed Identity, Account Key, and SAS Token authentication.
    Provides container discovery, virtual prefix browsing, streaming chunked reads/writes,
    and metadata inspection.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not HAS_AZURE_BLOB:
            raise StorageException(
                "azure-storage-blob is not installed. Install with: pip install azure-storage-blob",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider="azure_blob"
            )
        self.default_container = config.get("container_name") or config.get("container")
        self._service_client: Optional[BlobServiceClient] = None

    def get_capabilities(self) -> Set[StorageCapability]:
        return {
            StorageCapability.CONTAINER_DISCOVERY,
            StorageCapability.DIRECTORY_OPERATIONS,
            StorageCapability.STREAM_READ,
            StorageCapability.STREAM_WRITE,
            StorageCapability.MULTIPART_UPLOAD,
            StorageCapability.STORAGE_TIERING,
            StorageCapability.PRESIGNED_URLS,
            StorageCapability.DELETE_OBJECT,
            StorageCapability.COPY_OBJECT,
        }

    @property
    def service_client(self) -> BlobServiceClient:
        if self._service_client is None:
            self.connect()
        return self._service_client

    def connect(self) -> None:
        service_url, cred, conn_str = build_azure_credentials_and_endpoints(self.config, service_type="blob")
        try:
            if conn_str:
                self._service_client = BlobServiceClient.from_connection_string(conn_str)
            elif cred is None:
                self._service_client = BlobServiceClient(account_url=service_url)
            else:
                self._service_client = BlobServiceClient(account_url=service_url, credential=cred)
            self._connected = True
        except Exception as e:
            self._classify_and_raise(e, "connect")

    def close(self) -> None:
        if self._service_client:
            self._service_client.close()
            self._service_client = None
        self._connected = False

    def _classify_and_raise(self, err: Exception, operation: str) -> None:
        if isinstance(err, StorageException):
            raise err
        msg = str(err)
        cat = StorageErrorCategory.UNKNOWN
        status = getattr(err, "status_code", None)

        if isinstance(err, ClientAuthenticationError) or status in (401, 403):
            cat = StorageErrorCategory.AUTHENTICATION_FAILED
        elif isinstance(err, ResourceNotFoundError) or status == 404:
            cat = StorageErrorCategory.NOT_FOUND
        elif isinstance(err, ServiceRequestError) or "timeout" in msg.lower():
            cat = StorageErrorCategory.NETWORK_TIMEOUT

        raise StorageException(
            f"Azure Blob error during {operation}: {msg}",
            category=cat,
            provider="azure_blob",
            status_code=status,
            original_exception=err
        )

    # ------------------------------------------------------------------
    # Connection Testing
    # ------------------------------------------------------------------

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            client = self.service_client
            # Verify connectivity by reading service properties or listing first container
            try:
                props = client.get_service_properties()
                version = props.get("default_service_version", "2020-10-02")
            except Exception:
                # If permissions restrict service properties, try listing container
                next(iter(client.list_containers(results_per_page=1)), None)
                version = "Azure Blob Storage API"

            latency = round((time.time() - start) * 1000, 2)
            return ConnectionTestResult(
                success=True,
                message="Successfully connected to Azure Blob Storage.",
                latency_ms=latency,
                server_version=str(version)
            )
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            # Redact credentials from error
            clean_err = StorageException._sanitize_message(str(e))
            return ConnectionTestResult(
                success=False,
                message=f"Azure Blob connection failed: {clean_err}",
                latency_ms=latency
            )

    # ------------------------------------------------------------------
    # Container & Resource Browsing
    # ------------------------------------------------------------------

    def list_containers(self) -> List[str]:
        try:
            return [c["name"] for c in self.service_client.list_containers()]
        except Exception as e:
            self._classify_and_raise(e, "list_containers")

    def _get_container_name(self, container: Optional[str]) -> str:
        cname = container or self.default_container
        if not cname:
            raise StorageException(
                "No container specified and no default container configured.",
                category=StorageErrorCategory.INVALID_PATH,
                provider="azure_blob"
            )
        return cname

    def list_directories(self, container: str, prefix: str = "") -> List[str]:
        cname = self._get_container_name(container)
        norm_prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        try:
            container_client = self.service_client.get_container_client(cname)
            dirs = []
            for item in container_client.walk_blobs(name_starts_with=norm_prefix, delimiter="/"):
                if getattr(item, "is_prefix", False) or not hasattr(item, "size"):
                    dirs.append(item.name.rstrip("/"))
            return sorted(dirs)
        except Exception as e:
            self._classify_and_raise(e, "list_directories")

    def list_files(
        self,
        container: str,
        prefix: str = "",
        recursive: bool = False,
        limit: Optional[int] = None
    ) -> Iterator[StorageItem]:
        cname = self._get_container_name(container)
        norm_prefix = prefix.strip("/")
        if norm_prefix:
            norm_prefix += "/" if not norm_prefix.endswith("/") else ""

        try:
            container_client = self.service_client.get_container_client(cname)
            count = 0

            if recursive:
                for blob in container_client.list_blobs(name_starts_with=norm_prefix):
                    yield StorageItem(
                        name=blob.name.split("/")[-1],
                        path=blob.name,
                        is_directory=False,
                        size_in_bytes=blob.size,
                        last_modified=blob.last_modified,
                        content_type=blob.content_settings.content_type if blob.content_settings else None,
                        etag=blob.etag.strip('"') if blob.etag else None,
                        storage_tier=getattr(blob, "blob_tier", None)
                    )
                    count += 1
                    if limit and count >= limit:
                        return
            else:
                for item in container_client.walk_blobs(name_starts_with=norm_prefix, delimiter="/"):
                    if getattr(item, "is_prefix", False) or not hasattr(item, "size"):
                        yield StorageItem(
                            name=item.name.rstrip("/").split("/")[-1],
                            path=item.name.rstrip("/"),
                            is_directory=True,
                            size_in_bytes=0,
                            content_type="inode/directory"
                        )
                    else:
                        yield StorageItem(
                            name=item.name.split("/")[-1],
                            path=item.name,
                            is_directory=False,
                            size_in_bytes=item.size,
                            last_modified=item.last_modified,
                            content_type=item.content_settings.content_type if item.content_settings else None,
                            etag=item.etag.strip('"') if item.etag else None,
                            storage_tier=getattr(item, "blob_tier", None)
                        )
                    count += 1
                    if limit and count >= limit:
                        return
        except Exception as e:
            self._classify_and_raise(e, "list_files")

    def get_object_metadata(self, container: str, object_key: str) -> StorageItem:
        cname = self._get_container_name(container)
        norm_key = object_key.lstrip("/")
        try:
            blob_client = self.service_client.get_blob_client(container=cname, blob=norm_key)
            props = blob_client.get_blob_properties()
            return StorageItem(
                name=norm_key.split("/")[-1],
                path=norm_key,
                is_directory=False,
                size_in_bytes=props.size,
                last_modified=props.last_modified,
                content_type=props.content_settings.content_type if props.content_settings else None,
                etag=props.etag.strip('"') if props.etag else None,
                metadata=props.metadata or {},
                storage_tier=getattr(props, "blob_tier", None)
            )
        except Exception as e:
            self._classify_and_raise(e, "get_object_metadata")

    # ------------------------------------------------------------------
    # Streaming Read & Write
    # ------------------------------------------------------------------

    def read_stream(
        self,
        container: str,
        object_key: str,
        chunk_size: int = 4 * 1024 * 1024
    ) -> Iterator[bytes]:
        cname = self._get_container_name(container)
        norm_key = object_key.lstrip("/")
        try:
            blob_client = self.service_client.get_blob_client(container=cname, blob=norm_key)
            download_stream = blob_client.download_blob(max_concurrency=2)
            for chunk in download_stream.chunks():
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
        cname = self._get_container_name(container)
        norm_key = object_key.lstrip("/")
        try:
            blob_client = self.service_client.get_blob_client(container=cname, blob=norm_key)
            settings = ContentSettings(content_type=content_type)
            
            # Azure Blob upload_blob accepts an iterable / generator of bytes or file-like object
            class _StreamWrapper:
                def __init__(self, it):
                    self.it = it
                    self.buf = b""
                    self.total = 0

                def read(self, size=-1):
                    while not self.buf:
                        try:
                            self.buf = next(self.it)
                        except StopIteration:
                            return b""
                    if size == -1 or len(self.buf) <= size:
                        chunk, self.buf = self.buf, b""
                    else:
                        chunk, self.buf = self.buf[:size], self.buf[size:]
                    self.total += len(chunk)
                    return chunk

            wrapper = _StreamWrapper(stream)
            blob_client.upload_blob(
                wrapper,
                overwrite=True,
                content_settings=settings,
                metadata=metadata,
                max_concurrency=2
            )
            return wrapper.total
        except Exception as e:
            self._classify_and_raise(e, "write_stream")

    # ------------------------------------------------------------------
    # Mutation: Delete, Copy
    # ------------------------------------------------------------------

    def delete_file(self, container: str, object_key: str) -> bool:
        cname = self._get_container_name(container)
        norm_key = object_key.lstrip("/")
        try:
            blob_client = self.service_client.get_blob_client(container=cname, blob=norm_key)
            blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            self._classify_and_raise(e, "delete_file")

    def delete_directory(self, container: str, prefix: str) -> int:
        cname = self._get_container_name(container)
        norm_prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        try:
            container_client = self.service_client.get_container_client(cname)
            blobs_to_delete = [b.name for b in container_client.list_blobs(name_starts_with=norm_prefix)]
            for blob_name in blobs_to_delete:
                container_client.delete_blob(blob_name)
            return len(blobs_to_delete)
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
            src_cname = self._get_container_name(src_container)
            dst_cname = self._get_container_name(dst_container)
            src_blob = self.service_client.get_blob_client(container=src_cname, blob=src_key.lstrip("/"))
            dst_blob = self.service_client.get_blob_client(container=dst_cname, blob=dst_key.lstrip("/"))
            
            # Start copy
            copy_props = dst_blob.start_copy_from_url(src_blob.url)
            # For emulator/fast copies, status is usually 'success' immediately
            return True
        except Exception as e:
            self._classify_and_raise(e, "copy_file")


# Register concrete connector into provider registry
StorageProviderRegistry._providers["azure_blob"]["connector_class"] = AzureBlobStorageConnector
