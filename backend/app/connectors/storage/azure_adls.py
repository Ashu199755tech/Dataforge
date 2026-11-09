from __future__ import annotations
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
    from azure.storage.filedatalake import (
        DataLakeServiceClient,
        FileSystemClient,
        DataLakeDirectoryClient,
        DataLakeFileClient,
        ContentSettings
    )
    from azure.core.exceptions import (
        HttpResponseError,
        ResourceNotFoundError,
        ClientAuthenticationError,
        ServiceRequestError
    )
    HAS_AZURE_ADLS = True
except ImportError:
    HAS_AZURE_ADLS = False
    DataLakeServiceClient = Any
    FileSystemClient = Any
    DataLakeDirectoryClient = Any
    DataLakeFileClient = Any
    ContentSettings = Any
    HttpResponseError = Exception
    ResourceNotFoundError = Exception
    ClientAuthenticationError = Exception
    ServiceRequestError = Exception


class AzureDataLakeStorageConnector(BaseStorageConnector):
    """
    Microsoft Azure Data Lake Storage Gen2 (ADLS Gen2) Connector.
    Supports POSIX hierarchical namespaces, atomic directory renames/moves,
    Service Principal, Managed Identity, and Account Key authentication.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not HAS_AZURE_ADLS:
            raise StorageException(
                "azure-storage-file-datalake is not installed. Install with: pip install azure-storage-file-datalake",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider="azure_adls"
            )
        self.default_filesystem = config.get("filesystem") or config.get("container_name") or config.get("container")
        self._service_client: Optional[DataLakeServiceClient] = None

    def get_capabilities(self) -> Set[StorageCapability]:
        return {
            StorageCapability.CONTAINER_DISCOVERY,
            StorageCapability.HIERARCHICAL_NAMESPACE,
            StorageCapability.DIRECTORY_OPERATIONS,
            StorageCapability.STREAM_READ,
            StorageCapability.STREAM_WRITE,
            StorageCapability.MULTIPART_UPLOAD,
            StorageCapability.DELETE_OBJECT,
            StorageCapability.COPY_OBJECT,
            StorageCapability.MOVE_OBJECT,
        }

    @property
    def service_client(self) -> DataLakeServiceClient:
        if self._service_client is None:
            self.connect()
        return self._service_client

    def connect(self) -> None:
        service_url, cred, conn_str = build_azure_credentials_and_endpoints(self.config, service_type="dfs")
        try:
            if conn_str:
                self._service_client = DataLakeServiceClient.from_connection_string(conn_str)
            elif cred is None:
                self._service_client = DataLakeServiceClient(account_url=service_url)
            else:
                self._service_client = DataLakeServiceClient(account_url=service_url, credential=cred)
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
            f"Azure ADLS Gen2 error during {operation}: {msg}",
            category=cat,
            provider="azure_adls",
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
            try:
                props = client.get_service_properties()
                version = props.get("default_service_version", "2020-10-02")
            except Exception:
                next(iter(client.list_file_systems(results_per_page=1)), None)
                version = "ADLS Gen2 DFS Engine"

            latency = round((time.time() - start) * 1000, 2)
            return ConnectionTestResult(
                success=True,
                message="Successfully connected to Azure Data Lake Storage Gen2.",
                latency_ms=latency,
                server_version=str(version)
            )
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            clean_err = StorageException._sanitize_message(str(e))
            return ConnectionTestResult(
                success=False,
                message=f"Azure ADLS Gen2 connection failed: {clean_err}",
                latency_ms=latency
            )

    # ------------------------------------------------------------------
    # Filesystem & Hierarchical Directory Browsing
    # ------------------------------------------------------------------

    def list_containers(self) -> List[str]:
        """Lists filesystems (ADLS Gen2 filesystems correspond to containers)."""
        try:
            return [fs["name"] for fs in self.service_client.list_file_systems()]
        except Exception as e:
            self._classify_and_raise(e, "list_containers")

    def _get_fs_name(self, container: Optional[str]) -> str:
        fs = container or self.default_filesystem
        if not fs:
            raise StorageException(
                "No ADLS Gen2 filesystem specified and no default configured.",
                category=StorageErrorCategory.INVALID_PATH,
                provider="azure_adls"
            )
        return fs

    def list_directories(self, container: str, prefix: str = "") -> List[str]:
        fs_name = self._get_fs_name(container)
        norm_prefix = prefix.strip("/")
        try:
            fs_client = self.service_client.get_file_system_client(fs_name)
            dirs = []
            paths = fs_client.get_paths(path=norm_prefix if norm_prefix else None, recursive=False)
            for p in paths:
                if p.is_directory:
                    dirs.append(p.name)
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
        fs_name = self._get_fs_name(container)
        norm_prefix = prefix.strip("/")
        try:
            fs_client = self.service_client.get_file_system_client(fs_name)
            paths = fs_client.get_paths(path=norm_prefix if norm_prefix else None, recursive=recursive)
            count = 0
            for p in paths:
                yield StorageItem(
                    name=p.name.split("/")[-1],
                    path=p.name,
                    is_directory=p.is_directory,
                    size_in_bytes=0 if p.is_directory else (p.content_length or 0),
                    last_modified=p.last_modified,
                    content_type="inode/directory" if p.is_directory else "application/octet-stream",
                    etag=p.etag.strip('"') if getattr(p, "etag", None) else None
                )
                count += 1
                if limit and count >= limit:
                    return
        except Exception as e:
            self._classify_and_raise(e, "list_files")

    def get_object_metadata(self, container: str, object_key: str) -> StorageItem:
        fs_name = self._get_fs_name(container)
        norm_key = object_key.lstrip("/")
        try:
            file_client = self.service_client.get_file_client(file_system=fs_name, file_path=norm_key)
            props = file_client.get_file_properties()
            is_dir = getattr(props, "is_directory", False)
            return StorageItem(
                name=norm_key.split("/")[-1],
                path=norm_key,
                is_directory=is_dir,
                size_in_bytes=0 if is_dir else props.size,
                last_modified=props.last_modified,
                content_type=props.content_settings.content_type if props.content_settings else None,
                etag=props.etag.strip('"') if props.etag else None,
                metadata=props.metadata or {}
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
        fs_name = self._get_fs_name(container)
        norm_key = object_key.lstrip("/")
        try:
            file_client = self.service_client.get_file_client(file_system=fs_name, file_path=norm_key)
            download = file_client.download_file()
            for chunk in download.chunks():
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
        fs_name = self._get_fs_name(container)
        norm_key = object_key.lstrip("/")
        try:
            file_client = self.service_client.get_file_client(file_system=fs_name, file_path=norm_key)
            settings = ContentSettings(content_type=content_type)

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
            file_client.upload_data(
                wrapper,
                overwrite=True,
                content_settings=settings,
                metadata=metadata
            )
            return wrapper.total
        except Exception as e:
            self._classify_and_raise(e, "write_stream")

    # ------------------------------------------------------------------
    # Mutation: Delete, Atomic Rename / Move, Copy
    # ------------------------------------------------------------------

    def delete_file(self, container: str, object_key: str) -> bool:
        fs_name = self._get_fs_name(container)
        norm_key = object_key.lstrip("/")
        try:
            file_client = self.service_client.get_file_client(file_system=fs_name, file_path=norm_key)
            file_client.delete_file()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            self._classify_and_raise(e, "delete_file")

    def delete_directory(self, container: str, prefix: str) -> int:
        fs_name = self._get_fs_name(container)
        norm_prefix = prefix.strip("/")
        try:
            dir_client = self.service_client.get_directory_client(file_system=fs_name, directory_path=norm_prefix)
            dir_client.delete_directory()
            return 1
        except Exception as e:
            self._classify_and_raise(e, "delete_directory")

    def move_file(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        """Atomic ADLS Gen2 POSIX file rename/move."""
        src_fs = self._get_fs_name(src_container)
        dst_fs = self._get_fs_name(dst_container)
        src_norm = src_key.lstrip("/")
        dst_norm = dst_key.lstrip("/")
        try:
            src_file = self.service_client.get_file_client(file_system=src_fs, file_path=src_norm)
            # rename_file performs atomic POSIX metadata move
            new_path = f"{dst_fs}/{dst_norm}" if src_fs != dst_fs else dst_norm
            src_file.rename_file(new_name=new_path)
            return True
        except Exception as e:
            self._classify_and_raise(e, "move_file")

    def copy_file(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        """Copies file by streaming through buffer."""
        try:
            stream = self.read_stream(src_container, src_key)
            self.write_stream(dst_container, dst_key, stream)
            return True
        except Exception as e:
            self._classify_and_raise(e, "copy_file")


# Register concrete connector into provider registry
StorageProviderRegistry._providers["azure_adls"]["connector_class"] = AzureDataLakeStorageConnector
