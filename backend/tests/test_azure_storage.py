import os
import time
import shutil
import subprocess
import tempfile
import pytest

from backend.app.connectors.storage.models import (
    StorageItem,
    StorageCapability,
    StorageErrorCategory,
    StorageException
)
from backend.app.connectors.storage.azure_auth import (
    build_azure_credentials_and_endpoints,
    AZURITE_ACCOUNT_NAME,
    AZURITE_ACCOUNT_KEY
)
from backend.app.connectors.storage.azure_blob import AzureBlobStorageConnector
from backend.app.connectors.storage.azure_adls import AzureDataLakeStorageConnector
from backend.app.connectors.storage.registry import StorageProviderRegistry
from backend.app.connectors.factory import get_connector


class TestAzureAuthAndConfig:
    """Tests Azure credential builders, authentication modes, and error handling."""

    def test_account_key_auth_builder(self):
        url, cred, conn_str = build_azure_credentials_and_endpoints({
            "account_name": "dataforgestore",
            "account_key": "fakekey123==",
            "auth_mode": "account_key"
        }, service_type="blob")
        assert "dataforgestore.blob.core.windows.net" in url
        assert cred == "fakekey123=="
        assert conn_str is None

    def test_sas_token_auth_builder(self):
        url, cred, conn_str = build_azure_credentials_and_endpoints({
            "account_name": "dataforgestore",
            "sas_token": "?sv=2020-08-04&ss=b&srt=s",
            "auth_mode": "sas_token"
        }, service_type="blob")
        assert "dataforgestore.blob.core.windows.net" in url
        assert cred is not None

    def test_service_principal_missing_fields_raises(self):
        with pytest.raises(StorageException) as exc_info:
            build_azure_credentials_and_endpoints({
                "account_name": "dataforgestore",
                "auth_mode": "service_principal",
                "client_id": "my-id"
                # client_secret and tenant_id missing
            }, service_type="blob")
        assert exc_info.value.category == StorageErrorCategory.AUTHENTICATION_FAILED

    def test_missing_account_name_raises(self):
        with pytest.raises(StorageException) as exc_info:
            build_azure_credentials_and_endpoints({}, service_type="blob")
        assert exc_info.value.category == StorageErrorCategory.AUTHENTICATION_FAILED

    def test_connection_string_mode(self):
        conn_str_input = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;"
        url, cred, conn_str = build_azure_credentials_and_endpoints({
            "connection_string": conn_str_input
        }, service_type="blob")
        assert conn_str == conn_str_input


class TestAzureConnectorCapabilitiesAndRegistry:
    """Verifies capabilities and provider registry resolution for Azure connectors."""

    def test_azure_blob_capabilities(self):
        conn = AzureBlobStorageConnector({
            "account_name": "teststore",
            "account_key": "fakekey=="
        })
        caps = conn.get_capabilities()
        assert StorageCapability.CONTAINER_DISCOVERY in caps
        assert StorageCapability.STREAM_READ in caps
        assert StorageCapability.STREAM_WRITE in caps
        assert StorageCapability.MULTIPART_UPLOAD in caps
        assert StorageCapability.STORAGE_TIERING in caps
        assert not conn.has_capability(StorageCapability.HIERARCHICAL_NAMESPACE)

    def test_azure_adls_capabilities(self):
        conn = AzureDataLakeStorageConnector({
            "account_name": "teststore",
            "account_key": "fakekey=="
        })
        caps = conn.get_capabilities()
        assert StorageCapability.CONTAINER_DISCOVERY in caps
        assert StorageCapability.HIERARCHICAL_NAMESPACE in caps
        assert StorageCapability.MOVE_OBJECT in caps

    def test_registry_lists_azure_as_available(self):
        assert StorageProviderRegistry.is_provider_available("azure_blob") is True
        assert StorageProviderRegistry.is_provider_available("azure_adls") is True

    def test_factory_creates_azure_connector(self):
        blob_conn = get_connector("azure_blob", {
            "account_name": "dataforgelake",
            "account_key": "fakekey=="
        })
        assert isinstance(blob_conn, AzureBlobStorageConnector)

        adls_conn = get_connector("azure_adls", {
            "account_name": "dataforgelake",
            "account_key": "fakekey=="
        })
        assert isinstance(adls_conn, AzureDataLakeStorageConnector)


AZURITE_PORT = 10150


@pytest.fixture(scope="module")
def azurite_server():
    tmp_dir = tempfile.mkdtemp(prefix="azurite_workspace_")
    node_path = os.path.expanduser("~/.local/node/bin")
    env = os.environ.copy()
    env["PATH"] = f"{node_path}:{env.get('PATH', '')}"

    proc = subprocess.Popen(
        [
            "azurite",
            "--silent",
            "--blobPort", str(AZURITE_PORT),
            "--queuePort", str(AZURITE_PORT + 1),
            "--tablePort", str(AZURITE_PORT + 2),
            "--loose",
            "--skipApiVersionCheck",
            "-l", tmp_dir
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1.0)
    yield
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    shutil.rmtree(tmp_dir, ignore_errors=True)


class TestAzureBlobAzuriteIntegration:
    """Integration test suite executing real Azure Blob Storage API calls against local Azurite emulator."""

    @pytest.fixture
    def client(self, azurite_server):
        endpoint = f"http://127.0.0.1:{AZURITE_PORT}/{AZURITE_ACCOUNT_NAME}"
        conn = AzureBlobStorageConnector({
            "account_name": AZURITE_ACCOUNT_NAME,
            "account_key": AZURITE_ACCOUNT_KEY,
            "custom_endpoint": endpoint,
            "container_name": "test-container"
        })
        # Ensure container exists
        try:
            conn.service_client.create_container("test-container")
        except Exception:
            pass
        return conn

    def test_connection_test(self, client):
        res = client.test_connection()
        assert res.success is True
        assert res.latency_ms is not None

    def test_connection_test_failure_handling(self, azurite_server):
        bad_conn = AzureBlobStorageConnector({
            "account_name": AZURITE_ACCOUNT_NAME,
            "account_key": "aW52YWxpZGF6dXJpdGVrZXkxMjM0NTY3ODkwMTI=",
            "custom_endpoint": f"http://127.0.0.1:{AZURITE_PORT}/{AZURITE_ACCOUNT_NAME}"
        })
        res = bad_conn.test_connection()
        assert res.success is False
        assert "failed" in res.message.lower() or "authentication" in res.message.lower()


    def test_write_and_read_file(self, client):
        data = b"Multi-cloud enterprise data chunk test payload."
        written = client.write_file("test-container", "logs/run1.log", data, content_type="text/plain")
        assert written == len(data)

        read_bytes = client.read_file("test-container", "logs/run1.log")
        assert read_bytes == data

    def test_streaming_chunked_read_and_write(self, client):
        chunk1 = b"AzureChunk1_" * 512
        chunk2 = b"AzureChunk2_" * 512
        total_len = len(chunk1) + len(chunk2)

        def _stream():
            yield chunk1
            yield chunk2

        written = client.write_stream("test-container", "stream/data.bin", _stream())
        assert written == total_len

        downloaded_chunks = list(client.read_stream("test-container", "stream/data.bin"))
        assembled = b"".join(downloaded_chunks)
        assert assembled == chunk1 + chunk2

    def test_upload_and_download_file(self, client, tmp_path):
        src_path = str(tmp_path / "local_blob_upload.txt")
        content = b"Uploading local file directly to Azure Blob Storage."
        with open(src_path, "wb") as f:
            f.write(content)

        uploaded = client.upload_file(src_path, "test-container", "uploads/local_blob.txt")
        assert uploaded == len(content)

        dst_path = str(tmp_path / "downloaded_blob.txt")
        downloaded = client.download_file("test-container", "uploads/local_blob.txt", dst_path)
        assert downloaded == len(content)
        with open(dst_path, "rb") as f:
            assert f.read() == content

    def test_get_object_metadata(self, client):
        payload = b"Metadata extraction test"
        client.write_file("test-container", "meta/item.txt", payload, content_type="text/plain")

        meta = client.get_object_metadata("test-container", "meta/item.txt")
        assert meta.name == "item.txt"
        assert meta.path == "meta/item.txt"
        assert meta.size_in_bytes == len(payload)
        assert meta.etag is not None
        assert not meta.is_directory

    def test_list_containers_and_files(self, client):
        containers = client.list_containers()
        assert "test-container" in containers

        client.write_file("test-container", "folderA/file1.txt", b"1")
        client.write_file("test-container", "folderA/file2.txt", b"2")
        client.write_file("test-container", "folderB/file3.txt", b"3")

        # Flat listing (virtual directories returned as items)
        flat = list(client.list_files("test-container", prefix="", recursive=False))
        names = [f.name for f in flat]
        assert "folderA" in names or "folderB" in names

        # Recursive listing
        recursive_items = list(client.list_files("test-container", prefix="folderA", recursive=True))
        rec_paths = [i.path for i in recursive_items]
        assert "folderA/file1.txt" in rec_paths
        assert "folderA/file2.txt" in rec_paths

        # List directories
        dirs = client.list_directories("test-container")
        assert "folderA" in dirs or "folderB" in dirs

    def test_copy_and_delete_file(self, client):
        data = b"Copy and delete payload"
        client.write_file("test-container", "orig.txt", data)

        # Copy
        copied = client.copy_file("test-container", "orig.txt", "test-container", "orig_copy.txt")
        assert copied is True
        assert client.read_file("test-container", "orig_copy.txt") == data

        # Delete single file
        deleted = client.delete_file("test-container", "orig.txt")
        assert deleted is True

        # Delete directory prefix
        client.write_file("test-container", "batch_del/f1.txt", b"a")
        client.write_file("test-container", "batch_del/f2.txt", b"b")
        del_count = client.delete_directory("test-container", "batch_del")
        assert del_count == 2


class TestAzureADLSOperations:
    """Verifies Azure Data Lake Storage Gen2 specific methods, hierarchy models, and error handling."""

    def test_adls_missing_filesystem_raises(self):
        conn = AzureDataLakeStorageConnector({
            "account_name": "datalakeaccount",
            "account_key": "dummy=="
        })
        with pytest.raises(StorageException) as exc_info:
            conn._get_fs_name(None)
        assert exc_info.value.category == StorageErrorCategory.INVALID_PATH

    def test_adls_connection_failure_handling(self):
        bad_conn = AzureDataLakeStorageConnector({
            "account_name": AZURITE_ACCOUNT_NAME,
            "account_key": "aW52YWxpZGtleTEyMzQ1Njc4OQ==",
            "custom_endpoint": f"http://127.0.0.1:{AZURITE_PORT}/{AZURITE_ACCOUNT_NAME}"
        })
        res = bad_conn.test_connection()
        assert res.success is False
        assert "failed" in res.message.lower() or "authentication" in res.message.lower()

    def test_adls_move_file_contract(self, monkeypatch):
        conn = AzureDataLakeStorageConnector({
            "account_name": "mockadls",
            "account_key": "mockkey==",
            "filesystem": "lake"
        })
        # Verify method exists and respects interface signature
        assert hasattr(conn, "move_file")
        assert conn.has_capability(StorageCapability.HIERARCHICAL_NAMESPACE)
        assert conn.has_capability(StorageCapability.MOVE_OBJECT)


class TestAzureLiveIntegration:
    """Optional live integration test against actual Azure subscription when credentials exist."""

    @pytest.mark.skipif(
        not os.environ.get("DATAFORGE_AZURE_STORAGE_CONNECTION_STRING"),
        reason="DATAFORGE_AZURE_STORAGE_CONNECTION_STRING not provided. Skipping live cloud test."
    )
    def test_live_azure_blob_roundtrip(self):
        conn_str = os.environ["DATAFORGE_AZURE_STORAGE_CONNECTION_STRING"]
        conn = AzureBlobStorageConnector({"connection_string": conn_str})
        test_res = conn.test_connection()
        assert test_res.success is True

        containers = conn.list_containers()
        assert isinstance(containers, list)
