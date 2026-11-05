from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterator, Optional, Set
import os
from backend.app.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    TableMetadata,
    ColumnMetadata
)
from backend.app.connectors.storage.models import (
    StorageItem,
    StorageCapability,
    StorageErrorCategory,
    StorageException
)


class BaseStorageConnector(BaseConnector, ABC):
    """
    Common abstract storage connector for all object storage systems
    (Azure Blob, ADLS Gen2, AWS S3, Google Cloud Storage, Local Filesystem).
    
    Provides capability-based introspection, container/bucket abstraction,
    hierarchical and prefix browsing, chunked streaming binary I/O,
    and backward-compatible integration with DataForge's tabular activities.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._connected = False

    def connect(self) -> None:
        """Establishes client connection/session. Subclasses may override."""
        self._connected = True

    def close(self) -> None:
        """Closes client connections and releases resources."""
        self._connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abstractmethod
    def get_capabilities(self) -> Set[StorageCapability]:
        """Returns the set of capabilities natively supported by this provider."""
        pass

    def has_capability(self, capability: StorageCapability) -> bool:
        """Checks if a specific capability is supported by this connector."""
        return capability in self.get_capabilities()

    # ------------------------------------------------------------------
    # Container / Bucket Discovery
    # ------------------------------------------------------------------

    @abstractmethod
    def list_containers(self) -> List[str]:
        """Lists available containers (Azure) or buckets (AWS S3, GCP GCS)."""
        pass

    def list_buckets(self) -> List[str]:
        """Alias for list_containers() for S3/GCS terminology parity."""
        return self.list_containers()

    # ------------------------------------------------------------------
    # Directory & File Browsing
    # ------------------------------------------------------------------

    @abstractmethod
    def list_directories(self, container: str, prefix: str = "") -> List[str]:
        """Lists immediate child subdirectories or virtual prefixes."""
        pass

    @abstractmethod
    def list_files(
        self,
        container: str,
        prefix: str = "",
        recursive: bool = False,
        limit: Optional[int] = None
    ) -> Iterator[StorageItem]:
        """Lists files/objects within a container, optionally filtered by prefix."""
        pass

    @abstractmethod
    def get_object_metadata(self, container: str, object_key: str) -> StorageItem:
        """Retrieves metadata (size, etag, timestamps, content-type) for a specific object."""
        pass

    # ------------------------------------------------------------------
    # Streaming & File Read / Write Operations
    # ------------------------------------------------------------------

    @abstractmethod
    def read_stream(
        self,
        container: str,
        object_key: str,
        chunk_size: int = 4 * 1024 * 1024
    ) -> Iterator[bytes]:
        """Streams object contents as raw binary byte chunks."""
        pass

    def read_file(self, container: str, object_key: str) -> bytes:
        """Reads complete file into memory as bytes. Use read_stream for large files."""
        chunks = []
        for chunk in self.read_stream(container, object_key):
            chunks.append(chunk)
        return b"".join(chunks)

    @abstractmethod
    def write_stream(
        self,
        container: str,
        object_key: str,
        stream: Iterator[bytes],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> int:
        """Writes binary stream to destination object. Returns total bytes written."""
        pass

    def write_file(
        self,
        container: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> int:
        """Writes full byte buffer to destination object."""
        def _stream():
            yield data
        return self.write_stream(container, object_key, _stream(), content_type=content_type, metadata=metadata)

    def upload_file(
        self,
        local_path: str,
        container: str,
        object_key: str,
        content_type: Optional[str] = None
    ) -> int:
        """Uploads a local file to storage using chunked streaming."""
        if not os.path.exists(local_path):
            raise StorageException(
                f"Local file does not exist: {local_path}",
                category=StorageErrorCategory.NOT_FOUND,
                provider="storage"
            )

        def _file_chunk_stream(chunk_size: int = 4 * 1024 * 1024):
            with open(local_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        ctype = content_type or "application/octet-stream"
        return self.write_stream(container, object_key, _file_chunk_stream(), content_type=ctype)

    def download_file(
        self,
        container: str,
        object_key: str,
        local_path: str
    ) -> int:
        """Downloads a remote object to local file using chunked streaming."""
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        total_bytes = 0
        with open(local_path, "wb") as f:
            for chunk in self.read_stream(container, object_key):
                f.write(chunk)
                total_bytes += len(chunk)
        return total_bytes

    # ------------------------------------------------------------------
    # Mutation & Management
    # ------------------------------------------------------------------

    @abstractmethod
    def delete_file(self, container: str, object_key: str) -> bool:
        """Deletes a single object from storage. Returns True if deleted."""
        pass

    @abstractmethod
    def delete_directory(self, container: str, prefix: str) -> int:
        """Deletes all objects matching prefix. Returns number of objects deleted."""
        pass

    @abstractmethod
    def copy_file(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        """Copies an object within the same storage provider."""
        pass

    def move_file(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        """Moves an object by copying and then deleting source."""
        success = self.copy_file(src_container, src_key, dst_container, dst_key)
        if success:
            self.delete_file(src_container, src_key)
            return True
        return False

    # ------------------------------------------------------------------
    # BaseConnector Compatibility (Bridging Tabular Activities)
    # ------------------------------------------------------------------

    def discover_schemas(self) -> List[str]:
        """Maps schemas to containers / buckets."""
        try:
            return self.list_containers()
        except Exception:
            return ["default"]

    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        """Discovers files within a container formatted as TableMetadata."""
        container = schema_name or (self.list_containers()[0] if self.list_containers() else "default")
        tables = []
        try:
            for item in self.list_files(container, recursive=True, limit=100):
                if not item.is_directory:
                    tables.append(TableMetadata(
                        name=item.path,
                        schema_name=container,
                        table_type="FILE",
                        approx_row_count=None,
                        columns=[]
                    ))
        except Exception:
            pass
        return tables

    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        """Stub for column discovery; implemented when combined with format readers."""
        return []

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Storage connectors do not support SQL execution."""
        raise StorageException(
            "SQL query execution is not supported by object storage connectors.",
            category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
            provider="storage"
        )

    def read_data_stream(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        watermark_column: Optional[str] = None,
        watermark_value: Optional[Any] = None,
        batch_size: int = 5000,
        schema_name: Optional[str] = None
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Base streaming reader for tabular activities.
        Subclasses or format readers yield structured records.
        """
        raise NotImplementedError("Storage connector requires a format reader to parse records.")

    def write_data_batch(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        write_mode: str = "append",
        key_columns: Optional[List[str]] = None,
        column_mappings: Optional[List[Dict[str, str]]] = None,
        schema_name: Optional[str] = None,
        auto_create_table: bool = True
    ) -> int:
        """
        Base batch writer for tabular activities.
        Subclasses or format writers persist structured records.
        """
        raise NotImplementedError("Storage connector requires a format writer to encode records.")
