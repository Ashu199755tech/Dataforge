import os
import shutil
import tempfile
import pytest
from datetime import datetime, timezone

from backend.app.connectors.storage.models import (
    StorageItem,
    StorageMetadata,
    StorageCapability,
    StorageErrorCategory,
    StorageException
)
from backend.app.connectors.storage.base import BaseStorageConnector
from backend.app.connectors.storage.registry import StorageProviderRegistry
from backend.app.connectors.storage.local import LocalStorageConnector
from backend.app.schemas.storage import (
    LocalStorageConfig,
    AzureBlobStorageConfig,
    AzureADLSGen2Config,
    AWSS3Config,
    GCSConfig,
    sanitize_storage_config
)
from backend.app.connectors.factory import get_connector


class TestStorageModelsAndSecurity:
    """Tests Pydantic storage models, capability enums, and credential sanitization."""

    def test_storage_item_model(self):
        item = StorageItem(
            name="dataset.parquet",
            path="lake/raw/dataset.parquet",
            is_directory=False,
            size_in_bytes=2048,
            last_modified=datetime.now(timezone.utc),
            content_type="application/octet-stream",
            etag="d41d8cd98f00b204e9800998ecf8427e",
            metadata={"source": "erp_sync"},
            storage_tier="Hot"
        )
        assert item.name == "dataset.parquet"
        assert item.path == "lake/raw/dataset.parquet"
        assert not item.is_directory
        assert item.size_in_bytes == 2048
        assert item.etag == "d41d8cd98f00b204e9800998ecf8427e"
        assert item.metadata["source"] == "erp_sync"

    def test_storage_exception_sanitizes_credentials(self):
        sensitive_msg = "Failed auth with key=SECRET_KEY_123456 and token=BEARER_TOKEN_ABC and AKIAIOSFODNN7EXAMPLE"
        exc = StorageException(
            message=sensitive_msg,
            category=StorageErrorCategory.AUTHENTICATION_FAILED,
            provider="aws_s3",
            status_code=403
        )
        exc_str = str(exc)
        assert "SECRET_KEY_123456" not in exc_str
        assert "BEARER_TOKEN_ABC" not in exc_str
        assert "AKIAIOSFODNN7EXAMPLE" not in exc_str
        assert "***REDACTED***" in exc_str
        assert exc.category == StorageErrorCategory.AUTHENTICATION_FAILED
        assert exc.status_code == 403

    def test_sanitize_storage_config(self):
        raw_config = {
            "account_name": "corpstorage",
            "account_key": "super_secret_account_key_azure",
            "sas_token": "sp=r&st=2026-01-01&sig=sensitive_sig",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "nested": {
                "client_secret": "my_client_secret_xyz",
                "normal_field": "visible_value"
            }
        }
        sanitized = sanitize_storage_config(raw_config)
        assert sanitized["account_name"] == "corpstorage"
        assert sanitized["account_key"] == "***REDACTED***"
        assert sanitized["sas_token"] == "***REDACTED***"
        assert sanitized["secret_access_key"] == "***REDACTED***"
        assert sanitized["nested"]["client_secret"] == "***REDACTED***"
        assert sanitized["nested"]["normal_field"] == "visible_value"


class TestStorageProviderRegistry:
    """Tests dynamic provider registration, availability discovery, and factory resolution."""

    def test_list_providers(self):
        providers = StorageProviderRegistry.list_providers()
        ptypes = [p.provider_type for p in providers]
        assert "local_storage" in ptypes
        assert "azure_blob" in ptypes
        assert "azure_adls" in ptypes
        assert "aws_s3" in ptypes
        assert "gcp_storage" in ptypes

        # local_storage must always be available
        local_info = next(p for p in providers if p.provider_type == "local_storage")
        assert local_info.is_available is True
        assert local_info.missing_reason is None

    def test_missing_provider_diagnostic(self):
        # Even if boto3 is not present, registry provides clear diagnostic without crashing
        is_avail = StorageProviderRegistry.is_provider_available("aws_s3")
        reason = StorageProviderRegistry.get_missing_dependency_message("aws_s3")
        if not is_avail:
            assert reason is not None
            assert "boto3" in reason
            with pytest.raises(StorageException) as exc_info:
                StorageProviderRegistry.create_connector("aws_s3", {"bucket": "test"})
            assert exc_info.value.category == StorageErrorCategory.OPERATION_NOT_SUPPORTED
            assert "pip install" in str(exc_info.value)

    def test_get_connector_storage_factory(self, tmp_path):
        conn = get_connector("local_storage", {"base_path": str(tmp_path)})
        assert isinstance(conn, LocalStorageConnector)
        assert conn.test_connection().success is True


class TestLocalStorageConnector:
    """Tests end-to-end functionality of LocalStorageConnector conforming to BaseStorageConnector."""

    @pytest.fixture
    def storage(self, tmp_path):
        base_dir = str(tmp_path / "test_storage_root")
        conn = LocalStorageConnector({"base_path": base_dir, "create_if_missing": True})
        yield conn
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir, ignore_errors=True)

    def test_capabilities(self, storage):
        caps = storage.get_capabilities()
        assert StorageCapability.CONTAINER_DISCOVERY in caps
        assert StorageCapability.HIERARCHICAL_NAMESPACE in caps
        assert StorageCapability.STREAM_READ in caps
        assert StorageCapability.STREAM_WRITE in caps
        assert StorageCapability.DELETE_OBJECT in caps
        assert storage.has_capability(StorageCapability.STREAM_READ)
        assert not storage.has_capability(StorageCapability.RESUMABLE_UPLOAD)

    def test_connection_test(self, storage):
        res = storage.test_connection()
        assert res.success is True
        assert "POSIX Storage Engine" in res.server_version

    def test_read_write_file(self, storage):
        data = b"Hello Enterprise Multi-Cloud World!"
        written = storage.write_file("container1", "greetings/hello.txt", data, content_type="text/plain")
        assert written == len(data)

        read_data = storage.read_file("container1", "greetings/hello.txt")
        assert read_data == data

    def test_streaming_read_and_write(self, storage):
        chunk1 = b"Part1_" * 1024
        chunk2 = b"Part2_" * 1024
        total_len = len(chunk1) + len(chunk2)

        def _stream():
            yield chunk1
            yield chunk2

        written = storage.write_stream("container1", "streams/stream.bin", _stream())
        assert written == total_len

        read_chunks = list(storage.read_stream("container1", "streams/stream.bin", chunk_size=512))
        reassembled = b"".join(read_chunks)
        assert reassembled == chunk1 + chunk2

    def test_upload_and_download_file(self, storage, tmp_path):
        # Create a local source file
        local_src = str(tmp_path / "source.txt")
        content = b"Local file to upload into multi-cloud storage."
        with open(local_src, "wb") as f:
            f.write(content)

        uploaded = storage.upload_file(local_src, "container2", "uploads/source.txt")
        assert uploaded == len(content)

        # Download back to local destination
        local_dst = str(tmp_path / "downloaded.txt")
        downloaded = storage.download_file("container2", "uploads/source.txt", local_dst)
        assert downloaded == len(content)
        with open(local_dst, "rb") as f:
            assert f.read() == content

    def test_metadata_and_etag(self, storage):
        data = b"MD5 verification payload"
        storage.write_file("default", "meta_test.txt", data)

        meta = storage.get_object_metadata("default", "meta_test.txt")
        assert meta.name == "meta_test.txt"
        assert meta.size_in_bytes == len(data)
        assert meta.etag is not None
        assert len(meta.etag) == 32  # 32 char MD5 hex

    def test_listing_and_filtering(self, storage):
        storage.write_file("finance", "2026/01/report.csv", b"col1,col2\n1,2")
        storage.write_file("finance", "2026/02/report.csv", b"col1,col2\n3,4")
        storage.write_file("finance", "2026/summary.txt", b"Annual Summary")

        # List containers
        containers = storage.list_containers()
        assert "finance" in containers

        # List directories under 2026
        dirs = storage.list_directories("finance", prefix="2026")
        assert any("01" in d for d in dirs)
        assert any("02" in d for d in dirs)

        # Recursive file list
        files = list(storage.list_files("finance", prefix="2026", recursive=True))
        paths = [f.path for f in files]
        assert "2026/01/report.csv" in paths
        assert "2026/02/report.csv" in paths
        assert "2026/summary.txt" in paths

    def test_copy_move_delete(self, storage):
        data = b"Data to be copied and moved"
        storage.write_file("c1", "file.txt", data)

        # Copy
        storage.copy_file("c1", "file.txt", "c2", "file_copy.txt")
        assert storage.read_file("c2", "file_copy.txt") == data
        assert storage.read_file("c1", "file.txt") == data

        # Move
        storage.move_file("c2", "file_copy.txt", "c2", "file_moved.txt")
        assert storage.read_file("c2", "file_moved.txt") == data
        with pytest.raises(StorageException) as exc_info:
            storage.read_file("c2", "file_copy.txt")
        assert exc_info.value.category == StorageErrorCategory.NOT_FOUND

        # Delete file
        deleted = storage.delete_file("c2", "file_moved.txt")
        assert deleted is True

        # Delete directory
        storage.write_file("c3", "batch/f1.txt", b"1")
        storage.write_file("c3", "batch/f2.txt", b"2")
        del_count = storage.delete_directory("c3", "batch")
        assert del_count == 2

    def test_path_traversal_prevention(self, storage):
        with pytest.raises(StorageException) as exc_info:
            storage.read_file("default", "../../../../etc/passwd")
        assert exc_info.value.category == StorageErrorCategory.INVALID_PATH

    def test_context_manager(self, tmp_path):
        base_dir = str(tmp_path / "ctx_storage")
        with LocalStorageConnector({"base_path": base_dir}) as conn:
            assert conn._connected is True
            conn.write_file("default", "test.txt", b"hello")
        assert conn._connected is False

    def test_base_connector_discovery_compatibility(self, storage):
        storage.write_file("lake", "raw/sales.csv", b"id,val\n1,100")
        schemas = storage.discover_schemas()
        assert "lake" in schemas
        tables = storage.discover_tables("lake")
        assert any("sales.csv" in t.name for t in tables)
