import os
import shutil
import time
import hashlib
import mimetypes
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


class LocalStorageConnector(BaseStorageConnector):
    """
    Object Storage Connector for Local Filesystem, NFS, and mounted SMB volumes.
    Treats the base directory as a storage root, top-level directories as containers,
    and relative paths as object keys.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_path = os.path.abspath(config.get("base_path", "./data_storage"))
        self.create_if_missing = config.get("create_if_missing", True)
        if self.create_if_missing:
            os.makedirs(self.base_path, exist_ok=True)

    def get_capabilities(self) -> Set[StorageCapability]:
        return {
            StorageCapability.CONTAINER_DISCOVERY,
            StorageCapability.HIERARCHICAL_NAMESPACE,
            StorageCapability.DIRECTORY_OPERATIONS,
            StorageCapability.STREAM_READ,
            StorageCapability.STREAM_WRITE,
            StorageCapability.DELETE_OBJECT,
            StorageCapability.COPY_OBJECT,
            StorageCapability.MOVE_OBJECT,
        }

    def _resolve_container_path(self, container: str) -> str:
        """Resolves local absolute directory for a given container."""
        # Sanitize against directory traversal attacks
        clean_container = os.path.basename(os.path.normpath(container)) if container else "default"
        if clean_container in ("", ".", "..", "default"):
            return self.base_path
        return os.path.join(self.base_path, clean_container)

    def _resolve_object_path(self, container: str, object_key: str) -> str:
        """Resolves full local filesystem path for a container and object key."""
        container_path = self._resolve_container_path(container)
        norm_key = os.path.normpath(object_key).lstrip("/\\")
        # Prevent escaping container root
        full_path = os.path.abspath(os.path.join(container_path, norm_key))
        if not full_path.startswith(os.path.abspath(self.base_path)):
            raise StorageException(
                f"Path traversal detected: '{object_key}'",
                category=StorageErrorCategory.INVALID_PATH,
                provider="local_storage"
            )
        return full_path

    # ------------------------------------------------------------------
    # Connection Testing
    # ------------------------------------------------------------------

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            if not os.path.exists(self.base_path):
                if self.create_if_missing:
                    os.makedirs(self.base_path, exist_ok=True)
                else:
                    return ConnectionTestResult(
                        success=False,
                        message=f"Base storage path does not exist: {self.base_path}"
                    )

            if not os.access(self.base_path, os.R_OK | os.W_OK):
                return ConnectionTestResult(
                    success=False,
                    message=f"Permission denied: cannot read/write base path {self.base_path}"
                )

            latency = round((time.time() - start) * 1000, 2)
            return ConnectionTestResult(
                success=True,
                message=f"Local storage volume accessible at '{self.base_path}'",
                latency_ms=latency,
                server_version="POSIX Storage Engine"
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Storage test failed: {str(e)}"
            )

    # ------------------------------------------------------------------
    # Containers & Directories
    # ------------------------------------------------------------------

    def list_containers(self) -> List[str]:
        if not os.path.exists(self.base_path):
            return ["default"]
        containers = ["default"]
        for entry in os.scandir(self.base_path):
            if entry.is_dir() and not entry.name.startswith("."):
                containers.append(entry.name)
        return sorted(list(set(containers)))

    def list_directories(self, container: str, prefix: str = "") -> List[str]:
        container_path = self._resolve_container_path(container)
        target_dir = os.path.join(container_path, prefix.strip("/")) if prefix else container_path
        if not os.path.exists(target_dir):
            return []
        dirs = []
        for entry in os.scandir(target_dir):
            if entry.is_dir() and not entry.name.startswith("."):
                rel = os.path.relpath(entry.path, container_path)
                dirs.append(rel.replace("\\", "/"))
        return sorted(dirs)

    def list_files(
        self,
        container: str,
        prefix: str = "",
        recursive: bool = False,
        limit: Optional[int] = None
    ) -> Iterator[StorageItem]:
        container_path = self._resolve_container_path(container)
        target_dir = os.path.join(container_path, prefix.strip("/")) if prefix else container_path
        
        if not os.path.exists(target_dir):
            return

        count = 0
        if recursive:
            for root, dirs, files in os.walk(target_dir):
                for f in sorted(files):
                    if f.startswith("."):
                        continue
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, container_path).replace("\\", "/")
                    stat = os.stat(full_p)
                    mime, _ = mimetypes.guess_type(full_p)
                    yield StorageItem(
                        name=f,
                        path=rel_p,
                        is_directory=False,
                        size_in_bytes=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                        content_type=mime or "application/octet-stream"
                    )
                    count += 1
                    if limit and count >= limit:
                        return
        else:
            for entry in sorted(os.scandir(target_dir), key=lambda e: e.name):
                if entry.name.startswith("."):
                    continue
                rel_p = os.path.relpath(entry.path, container_path).replace("\\", "/")
                stat = entry.stat()
                if entry.is_dir():
                    yield StorageItem(
                        name=entry.name,
                        path=rel_p,
                        is_directory=True,
                        size_in_bytes=0,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                        content_type="inode/directory"
                    )
                else:
                    mime, _ = mimetypes.guess_type(entry.path)
                    yield StorageItem(
                        name=entry.name,
                        path=rel_p,
                        is_directory=False,
                        size_in_bytes=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                        content_type=mime or "application/octet-stream"
                    )
                count += 1
                if limit and count >= limit:
                    return

    def get_object_metadata(self, container: str, object_key: str) -> StorageItem:
        full_path = self._resolve_object_path(container, object_key)
        if not os.path.exists(full_path):
            raise StorageException(
                f"Object not found: {container}/{object_key}",
                category=StorageErrorCategory.NOT_FOUND,
                provider="local_storage",
                status_code=404
            )
        stat = os.stat(full_path)
        is_dir = os.path.isdir(full_path)
        mime, _ = mimetypes.guess_type(full_path)

        # Compute quick MD5 etag for small/medium files
        etag = None
        if not is_dir and stat.st_size < 50 * 1024 * 1024:
            hasher = hashlib.md5()
            with open(full_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            etag = hasher.hexdigest()

        return StorageItem(
            name=os.path.basename(full_path),
            path=object_key.strip("/"),
            is_directory=is_dir,
            size_in_bytes=0 if is_dir else stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            content_type="inode/directory" if is_dir else (mime or "application/octet-stream"),
            etag=etag,
            storage_tier="Local"
        )

    # ------------------------------------------------------------------
    # Streaming Read & Write
    # ------------------------------------------------------------------

    def read_stream(
        self,
        container: str,
        object_key: str,
        chunk_size: int = 4 * 1024 * 1024
    ) -> Iterator[bytes]:
        full_path = self._resolve_object_path(container, object_key)
        if not os.path.exists(full_path):
            raise StorageException(
                f"File not found: {container}/{object_key}",
                category=StorageErrorCategory.NOT_FOUND,
                provider="local_storage",
                status_code=404
            )
        try:
            with open(full_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            raise StorageException(
                f"Error streaming file: {str(e)}",
                category=StorageErrorCategory.UNKNOWN,
                provider="local_storage",
                original_exception=e
            )

    def write_stream(
        self,
        container: str,
        object_key: str,
        stream: Iterator[bytes],
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> int:
        full_path = self._resolve_object_path(container, object_key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write to temporary file first for atomic safety
        tmp_path = f"{full_path}.tmp_{int(time.time() * 1000)}"
        total_bytes = 0
        try:
            with open(tmp_path, "wb") as f:
                for chunk in stream:
                    f.write(chunk)
                    total_bytes += len(chunk)
            os.replace(tmp_path, full_path)
            return total_bytes
        except Exception as e:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise StorageException(
                f"Failed writing stream to '{object_key}': {str(e)}",
                category=StorageErrorCategory.UNKNOWN,
                provider="local_storage",
                original_exception=e
            )

    # ------------------------------------------------------------------
    # Mutation: Delete, Copy, Move
    # ------------------------------------------------------------------

    def delete_file(self, container: str, object_key: str) -> bool:
        full_path = self._resolve_object_path(container, object_key)
        if not os.path.exists(full_path):
            return False
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        return True

    def delete_directory(self, container: str, prefix: str) -> int:
        container_path = self._resolve_container_path(container)
        target_dir = os.path.join(container_path, prefix.strip("/"))
        if not os.path.exists(target_dir):
            return 0
        count = 0
        for root, dirs, files in os.walk(target_dir):
            count += len(files)
        shutil.rmtree(target_dir)
        return count

    def copy_file(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        src_path = self._resolve_object_path(src_container, src_key)
        dst_path = self._resolve_object_path(dst_container, dst_key)
        if not os.path.exists(src_path):
            raise StorageException(
                f"Source object not found: {src_container}/{src_key}",
                category=StorageErrorCategory.NOT_FOUND,
                provider="local_storage"
            )
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copy2(src_path, dst_path)
        return True

    def move_file(
        self,
        src_container: str,
        src_key: str,
        dst_container: str,
        dst_key: str
    ) -> bool:
        src_path = self._resolve_object_path(src_container, src_key)
        dst_path = self._resolve_object_path(dst_container, dst_key)
        if not os.path.exists(src_path):
            raise StorageException(
                f"Source object not found: {src_container}/{src_key}",
                category=StorageErrorCategory.NOT_FOUND,
                provider="local_storage"
            )
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.move(src_path, dst_path)
        return True


# Bind concrete class in the registry
StorageProviderRegistry._providers["local_storage"]["connector_class"] = LocalStorageConnector
