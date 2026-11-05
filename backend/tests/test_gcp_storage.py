import os
import io
import json
import time
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from backend.app.connectors.storage.models import (
    StorageItem,
    StorageCapability,
    StorageErrorCategory,
    StorageException
)
from backend.app.connectors.storage.gcp_auth import create_gcp_storage_client
from backend.app.connectors.storage.gcp_storage import GoogleCloudStorageConnector
from backend.app.connectors.storage.registry import StorageProviderRegistry
from backend.app.connectors.factory import get_connector


class TestGcpAuthAndConfig:
    """Verifies GCP authentication parser, Service Account JSON, and error handling."""

    def test_inline_service_account_json_parsing(self):
        fake_sa = {
            "type": "service_account",
            "project_id": "test-dataforge-project",
            "private_key_id": "key123",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----\n",
            "client_email": "sa@test-dataforge-project.iam.gserviceaccount.com",
            "client_id": "1234567890",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        with patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_sa:
            mock_sa.return_value = MagicMock()
            with patch("google.cloud.storage.Client") as mock_client:
                mock_client.return_value = MagicMock()
                client = create_gcp_storage_client({
                    "service_account_json": json.dumps(fake_sa),
                    "project_id": "test-dataforge-project"
                })
                assert client is not None
                mock_sa.assert_called_once()

    def test_invalid_service_account_json_raises(self):
        with pytest.raises(StorageException) as exc_info:
            create_gcp_storage_client({
                "service_account_json": "INVALID_NOT_JSON{{"
            })
        assert exc_info.value.category == StorageErrorCategory.AUTHENTICATION_FAILED

    def test_impersonation_mode_flow(self):
        with patch("google.auth.default", return_value=(MagicMock(), "proj-1")):
            with patch("backend.app.connectors.storage.gcp_auth.ImpersonatedCredentials") as mock_imp:
                mock_imp.return_value = MagicMock()
                with patch("google.cloud.storage.Client") as mock_client:
                    mock_client.return_value = MagicMock()
                    create_gcp_storage_client({
                        "auth_mode": "adc",
                        "impersonate_service_account": "target-sa@proj-1.iam.gserviceaccount.com"
                    })
                    mock_imp.assert_called_once()
                    mock_client.assert_called_once()


    def test_custom_endpoint_config(self):
        with patch("google.auth.default", return_value=(MagicMock(), "proj-1")):
            with patch("google.cloud.storage.Client") as mock_client:
                create_gcp_storage_client({
                    "auth_mode": "adc",
                    "custom_endpoint": "http://127.0.0.1:9090"
                })
                call_kwargs = mock_client.call_args[1]
                assert "client_options" in call_kwargs
                assert call_kwargs["client_options"]["api_endpoint"] == "http://127.0.0.1:9090"


class TestGoogleCloudStorageConnectorCapabilitiesAndRegistry:
    """Verifies capabilities and provider registry resolution for GCS connector."""

    def test_gcs_capabilities(self):
        conn = GoogleCloudStorageConnector({"bucket": "my-gcs-lake"})
        caps = conn.get_capabilities()
        assert StorageCapability.BUCKET_DISCOVERY in caps
        assert StorageCapability.STREAM_READ in caps
        assert StorageCapability.STREAM_WRITE in caps
        assert StorageCapability.RESUMABLE_UPLOAD in caps
        assert StorageCapability.STORAGE_TIERING in caps
        assert not conn.has_capability(StorageCapability.HIERARCHICAL_NAMESPACE)

    def test_registry_lists_gcs_as_available(self):
        assert StorageProviderRegistry.is_provider_available("gcp_storage") is True

    def test_factory_creates_gcs_connector(self):
        with patch("backend.app.connectors.storage.gcp_storage.create_gcp_storage_client") as mock_create:
            mock_create.return_value = MagicMock()
            conn = get_connector("gcp_storage", {
                "bucket": "dataforge-gcs-bucket",
                "project_id": "corp-proj"
            })
            assert isinstance(conn, GoogleCloudStorageConnector)


class FakeBlob:
    """High-fidelity in-memory GCS Blob simulator conforming to google.cloud.storage.Blob."""
    def __init__(self, name, bucket, content=b"", content_type="application/octet-stream", storage_class="STANDARD"):
        self.name = name
        self.bucket = bucket
        self.content = content
        self.content_type = content_type
        self.storage_class = storage_class
        self.size = len(content)
        self.updated = datetime.now(timezone.utc)
        self.etag = f"etag_{name}_{len(content)}"
        self.metadata = {}

    def open(self, mode="rb", content_type=None, chunk_size=None):
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


class FakeBucket:
    """In-memory GCS Bucket simulator conforming to google.cloud.storage.Bucket."""
    def __init__(self, name, exists=True):
        self.name = name
        self._exists = exists
        self._blobs = {}

    def exists(self):
        return self._exists

    def blob(self, name, chunk_size=None):
        if name not in self._blobs:
            self._blobs[name] = FakeBlob(name, self)
        return self._blobs[name]

    def get_blob(self, name):
        return self._blobs.get(name)

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
    def __init__(self, project="test-project"):
        self.project = project
        self._buckets = {}

    def bucket(self, name):
        if name not in self._buckets:
            self._buckets[name] = FakeBucket(name)
        return self._buckets[name]

    def list_buckets(self, max_results=None):
        return list(self._buckets.values())

    def list_blobs(self, bucket, prefix="", delimiter=None):
        matched_blobs = []
        prefixes = set()
        prefix = prefix or ""

        for name, b in bucket._blobs.items():
            if name.startswith(prefix):
                rel = name[len(prefix):]
                if delimiter and delimiter in rel:
                    sub_prefix = prefix + rel.split(delimiter)[0] + delimiter
                    prefixes.add(sub_prefix)
                else:
                    matched_blobs.append(b)

        class _Iterator(list):
            def __init__(s, items, prefs):
                super().__init__(items)
                s.prefixes = prefs

        return _Iterator(matched_blobs, prefixes)


class TestGoogleCloudStorageOperations:
    """Comprehensive test suite validating GCS operations against simulated GCS engine."""

    BUCKET_NAME = "dataforge-gcs-test-bucket"

    @pytest.fixture
    def fake_client(self):
        client = FakeGcsClient(project="corp-data-2026")
        b = client.bucket(self.BUCKET_NAME)
        return client

    @pytest.fixture
    def connector(self, fake_client):
        conn = GoogleCloudStorageConnector({
            "bucket": self.BUCKET_NAME,
            "project_id": "corp-data-2026"
        })
        conn._client = fake_client
        conn._connected = True
        return conn

    def test_connection_test(self, connector):
        res = connector.test_connection()
        assert res.success is True
        assert self.BUCKET_NAME in res.message
        assert res.latency_ms is not None

    def test_connection_test_failure_on_nonexistent_bucket(self, connector, fake_client):
        non_b = FakeBucket("missing-bucket", exists=False)
        fake_client._buckets["missing-bucket"] = non_b
        bad_conn = GoogleCloudStorageConnector({"bucket": "missing-bucket"})
        bad_conn._client = fake_client
        bad_conn._connected = True

        res = bad_conn.test_connection()
        assert res.success is False
        assert "does not exist" in res.message.lower()

    def test_list_containers_and_buckets(self, connector, fake_client):
        fake_client.bucket("marketing-lake")
        buckets = connector.list_containers()
        assert self.BUCKET_NAME in buckets
        assert "marketing-lake" in buckets
        assert connector.list_buckets() == buckets

    def test_write_and_read_file(self, connector):
        data = b"Enterprise GCS Data Movement Test"
        written = connector.write_file(self.BUCKET_NAME, "raw/orders.json", data, content_type="application/json")
        assert written == len(data)

        read_data = connector.read_file(self.BUCKET_NAME, "raw/orders.json")
        assert read_data == data

    def test_streaming_chunked_read_and_write(self, connector):
        chunk1 = b"GCSChunkA_" * 512
        chunk2 = b"GCSChunkB_" * 512
        total_len = len(chunk1) + len(chunk2)

        def _stream():
            yield chunk1
            yield chunk2

        written = connector.write_stream(self.BUCKET_NAME, "stream/gcs.dat", _stream())
        assert written == total_len

        downloaded_chunks = list(connector.read_stream(self.BUCKET_NAME, "stream/gcs.dat", chunk_size=512))
        reassembled = b"".join(downloaded_chunks)
        assert reassembled == chunk1 + chunk2

    def test_upload_and_download_file(self, connector, tmp_path):
        src_path = str(tmp_path / "gcs_local_src.txt")
        content = b"Local file uploaded into Google Cloud Storage."
        with open(src_path, "wb") as f:
            f.write(content)

        uploaded = connector.upload_file(src_path, self.BUCKET_NAME, "uploads/gcs_file.txt")
        assert uploaded == len(content)

        dst_path = str(tmp_path / "gcs_local_dst.txt")
        downloaded = connector.download_file(self.BUCKET_NAME, "uploads/gcs_file.txt", dst_path)
        assert downloaded == len(content)
        with open(dst_path, "rb") as f:
            assert f.read() == content

    def test_get_object_metadata(self, connector):
        payload = b"Metadata content for GCS"
        connector.write_file(self.BUCKET_NAME, "meta/test.txt", payload, content_type="text/plain")

        meta = connector.get_object_metadata(self.BUCKET_NAME, "meta/test.txt")
        assert meta.name == "test.txt"
        assert meta.path == "meta/test.txt"
        assert meta.size_in_bytes == len(payload)
        assert meta.content_type == "text/plain"
        assert meta.storage_tier == "STANDARD"

    def test_listing_and_filtering(self, connector):
        connector.write_file(self.BUCKET_NAME, "datalake/2026/sales.parquet", b"1")
        connector.write_file(self.BUCKET_NAME, "datalake/2026/returns.parquet", b"2")
        connector.write_file(self.BUCKET_NAME, "datalake/overview.txt", b"3")

        # Flat listing (prefix directories returned as is_directory)
        flat = list(connector.list_files(self.BUCKET_NAME, prefix="datalake", recursive=False))
        names = [f.name for f in flat]
        assert "2026" in names
        assert "overview.txt" in names

        # Recursive listing
        rec = list(connector.list_files(self.BUCKET_NAME, prefix="datalake/2026", recursive=True))
        rec_paths = [r.path for r in rec]
        assert "datalake/2026/sales.parquet" in rec_paths
        assert "datalake/2026/returns.parquet" in rec_paths

        # List directories
        dirs = connector.list_directories(self.BUCKET_NAME, prefix="datalake")
        assert any("2026" in d for d in dirs)

    def test_copy_and_delete_file(self, connector):
        data = b"GCS copy and delete payload"
        connector.write_file(self.BUCKET_NAME, "orig.txt", data)

        # Copy
        copied = connector.copy_file(self.BUCKET_NAME, "orig.txt", self.BUCKET_NAME, "copy.txt")
        assert copied is True
        assert connector.read_file(self.BUCKET_NAME, "copy.txt") == data

        # Delete single file
        deleted = connector.delete_file(self.BUCKET_NAME, "orig.txt")
        assert deleted is True

        # Delete directory prefix
        connector.write_file(self.BUCKET_NAME, "purge/f1.txt", b"a")
        connector.write_file(self.BUCKET_NAME, "purge/f2.txt", b"b")
        del_count = connector.delete_directory(self.BUCKET_NAME, "purge")
        assert del_count == 2

    def test_missing_bucket_raises_invalid_path(self):
        conn = GoogleCloudStorageConnector({"project_id": "p1"})
        with pytest.raises(StorageException) as exc_info:
            conn._get_bucket_name(None)
        assert exc_info.value.category == StorageErrorCategory.INVALID_PATH

    def test_gcs_file_not_found_on_read(self, connector):
        with pytest.raises(StorageException) as exc_info:
            connector.read_file(self.BUCKET_NAME, "completely_missing_file.txt")
        assert exc_info.value.category == StorageErrorCategory.NOT_FOUND

    def test_gcs_file_not_found_on_metadata(self, connector):
        with pytest.raises(StorageException) as exc_info:
            connector.get_object_metadata(self.BUCKET_NAME, "completely_missing_file.txt")
        assert exc_info.value.category == StorageErrorCategory.NOT_FOUND

    def test_error_classification_403(self):
        from google.api_core.exceptions import Forbidden
        conn = GoogleCloudStorageConnector({"bucket": "b1"})
        with pytest.raises(StorageException) as exc_info:
            err = Forbidden("Access denied to GCS bucket")
            conn._classify_and_raise(err, "read_blob")
        assert exc_info.value.category == StorageErrorCategory.AUTHENTICATION_FAILED


class TestGoogleCloudStorageLiveIntegration:
    """Optional live integration test against actual GCP project when credentials exist."""

    @pytest.mark.skipif(
        not os.environ.get("DATAFORGE_GCP_SERVICE_ACCOUNT_KEY"),
        reason="DATAFORGE_GCP_SERVICE_ACCOUNT_KEY not provided. Skipping live GCP test."
    )
    def test_live_gcs_roundtrip(self):
        sa_key = os.environ["DATAFORGE_GCP_SERVICE_ACCOUNT_KEY"]
        conn = GoogleCloudStorageConnector({
            "service_account_json": sa_key,
            "project_id": os.environ.get("DATAFORGE_GCP_PROJECT_ID"),
            "bucket": os.environ.get("DATAFORGE_GCP_BUCKET")
        })
        res = conn.test_connection()
        assert res.success is True
