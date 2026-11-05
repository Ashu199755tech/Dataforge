import os
import io
import pytest
from moto import mock_aws
import boto3

from backend.app.connectors.storage.models import (
    StorageItem,
    StorageCapability,
    StorageErrorCategory,
    StorageException
)
from backend.app.connectors.storage.aws_auth import create_boto3_s3_client
from backend.app.connectors.storage.aws_s3 import AmazonS3Connector
from backend.app.connectors.storage.registry import StorageProviderRegistry
from backend.app.connectors.factory import get_connector


class TestAwsAuthAndConfig:
    """Verifies AWS credential parsing, STS AssumeRole, and error handling."""

    def test_direct_access_key_client(self):
        client = create_boto3_s3_client({
            "access_key_id": "MOCKACCESSKEY12345",
            "secret_access_key": "MOCKSECRETKEY67890",
            "region_name": "us-west-2"
        })
        assert client.meta.region_name == "us-west-2"

    def test_temporary_session_token_client(self):
        client = create_boto3_s3_client({
            "access_key_id": "MOCKACCESSKEY12345",
            "secret_access_key": "MOCKSECRETKEY67890",
            "session_token": "MOCKSESSIONTOKEN999",
            "region_name": "eu-central-1"
        })
        assert client.meta.region_name == "eu-central-1"

    @mock_aws
    def test_sts_assume_role_mode(self):
        # Create mock STS client and role
        client = create_boto3_s3_client({
            "auth_mode": "sts_assume_role",
            "role_arn": "arn:aws:iam::123456789012:role/MockDataForgeRole",
            "access_key_id": "MOCKAKID",
            "secret_access_key": "MOCKSECRET",
            "region_name": "us-east-1"
        })
        assert client is not None

    def test_sts_assume_role_missing_role_arn_raises(self):
        with pytest.raises(StorageException) as exc_info:
            create_boto3_s3_client({
                "auth_mode": "sts_assume_role",
                # role_arn omitted
            })
        assert exc_info.value.category == StorageErrorCategory.AUTHENTICATION_FAILED


class TestAmazonS3ConnectorCapabilitiesAndRegistry:
    """Verifies capabilities and provider registry resolution for S3 connector."""

    def test_s3_capabilities(self):
        conn = AmazonS3Connector({"bucket": "my-lake"})
        caps = conn.get_capabilities()
        assert StorageCapability.BUCKET_DISCOVERY in caps
        assert StorageCapability.STREAM_READ in caps
        assert StorageCapability.STREAM_WRITE in caps
        assert StorageCapability.MULTIPART_UPLOAD in caps
        assert StorageCapability.SERVER_SIDE_ENCRYPTION in caps
        assert StorageCapability.STORAGE_TIERING in caps
        assert not conn.has_capability(StorageCapability.HIERARCHICAL_NAMESPACE)

    def test_registry_lists_s3_as_available(self):
        assert StorageProviderRegistry.is_provider_available("aws_s3") is True

    def test_factory_creates_s3_connector(self):
        conn = get_connector("aws_s3", {
            "bucket": "test-lake",
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        })
        assert isinstance(conn, AmazonS3Connector)


class TestAmazonS3MotoIntegration:
    """Integration test suite executing real AWS S3 SDK calls against Moto local emulator."""

    BUCKET_NAME = "dataforge-enterprise-test-bucket"

    @pytest.fixture(autouse=True)
    def moto_environment(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
        monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        with mock_aws():
            yield

    @pytest.fixture
    def s3_client(self):
        s3 = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing"
        )
        s3.create_bucket(Bucket=self.BUCKET_NAME)
        return s3

    @pytest.fixture
    def connector(self, s3_client):
        return AmazonS3Connector({
            "bucket": self.BUCKET_NAME,
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })

    def test_connection_test(self, connector):
        res = connector.test_connection()
        assert res.success is True
        assert self.BUCKET_NAME in res.message
        assert res.latency_ms is not None

    def test_connection_test_failure_on_nonexistent_bucket(self):
        bad_conn = AmazonS3Connector({
            "bucket": "completely-nonexistent-bucket-xyz-999",
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing"
        })
        res = bad_conn.test_connection()
        assert res.success is False
        assert "failed" in res.message.lower()

    def test_list_containers_and_buckets(self, connector, s3_client):
        s3_client.create_bucket(Bucket="another-bucket-finance")
        buckets = connector.list_containers()
        assert self.BUCKET_NAME in buckets
        assert "another-bucket-finance" in buckets
        # Verify alias
        assert connector.list_buckets() == buckets

    def test_write_and_read_file(self, connector):
        data = b"Enterprise AWS S3 Data Movement Engine Payload"
        written = connector.write_file(self.BUCKET_NAME, "raw/sales.csv", data, content_type="text/csv")
        assert written == len(data)

        read_data = connector.read_file(self.BUCKET_NAME, "raw/sales.csv")
        assert read_data == data

    def test_streaming_chunked_read_and_write(self, connector):
        chunk1 = b"S3ChunkOne_" * 1024
        chunk2 = b"S3ChunkTwo_" * 1024
        total_len = len(chunk1) + len(chunk2)

        def _gen():
            yield chunk1
            yield chunk2

        written = connector.write_stream(self.BUCKET_NAME, "stream/blob.bin", _gen())
        assert written == total_len

        downloaded_chunks = list(connector.read_stream(self.BUCKET_NAME, "stream/blob.bin", chunk_size=1024))
        assembled = b"".join(downloaded_chunks)
        assert assembled == chunk1 + chunk2

    def test_multipart_upload_over_threshold(self, connector):
        # 5MB + 1KB to strictly trigger multipart chunk flow (MIN_MULTIPART_CHUNK_SIZE)
        large_part_1 = b"M" * (5 * 1024 * 1024)
        large_part_2 = b"N" * 2048
        total_size = len(large_part_1) + len(large_part_2)

        def _large_stream():
            yield large_part_1
            yield large_part_2

        written = connector.write_stream(self.BUCKET_NAME, "large/multipart.dat", _large_stream())
        assert written == total_size

        meta = connector.get_object_metadata(self.BUCKET_NAME, "large/multipart.dat")
        assert meta.size_in_bytes == total_size
        # S3 multipart upload ETags contain a dash representing the part count, e.g. '...-2'
        assert "-" in meta.etag

    def test_upload_and_download_file(self, connector, tmp_path):
        src_path = str(tmp_path / "s3_local_source.txt")
        content = b"Local file to be uploaded to Amazon S3."
        with open(src_path, "wb") as f:
            f.write(content)

        uploaded = connector.upload_file(src_path, self.BUCKET_NAME, "uploads/s3_uploaded.txt")
        assert uploaded == len(content)

        dst_path = str(tmp_path / "s3_downloaded.txt")
        downloaded = connector.download_file(self.BUCKET_NAME, "uploads/s3_uploaded.txt", dst_path)
        assert downloaded == len(content)
        with open(dst_path, "rb") as f:
            assert f.read() == content

    def test_metadata_and_encryption(self, s3_client):
        enc_conn = AmazonS3Connector({
            "bucket": self.BUCKET_NAME,
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing",
            "server_side_encryption": "AES256"
        })
        payload = b"Encrypted financial report data"
        enc_conn.write_file(self.BUCKET_NAME, "secure/report.csv", payload, content_type="text/csv")

        meta = enc_conn.get_object_metadata(self.BUCKET_NAME, "secure/report.csv")
        assert meta.name == "report.csv"
        assert meta.size_in_bytes == len(payload)
        assert meta.content_type == "text/csv"

    def test_listing_and_filtering(self, connector):
        connector.write_file(self.BUCKET_NAME, "logs/2026/01/app.log", b"1")
        connector.write_file(self.BUCKET_NAME, "logs/2026/02/app.log", b"2")
        connector.write_file(self.BUCKET_NAME, "logs/summary.txt", b"summary")

        # Flat listing: folder prefix returned as is_directory item
        flat = list(connector.list_files(self.BUCKET_NAME, prefix="logs", recursive=False))
        names = [f.name for f in flat]
        assert "2026" in names
        assert "summary.txt" in names

        # Recursive listing: discovers nested files
        rec = list(connector.list_files(self.BUCKET_NAME, prefix="logs/2026", recursive=True))
        rec_paths = [r.path for r in rec]
        assert "logs/2026/01/app.log" in rec_paths
        assert "logs/2026/02/app.log" in rec_paths

        # List directories
        dirs = connector.list_directories(self.BUCKET_NAME, prefix="logs")
        assert any("2026" in d for d in dirs)

    def test_copy_and_delete_file(self, connector):
        data = b"S3 copy and delete content"
        connector.write_file(self.BUCKET_NAME, "data/file.txt", data)

        # Copy
        copied = connector.copy_file(self.BUCKET_NAME, "data/file.txt", self.BUCKET_NAME, "backup/file.txt")
        assert copied is True
        assert connector.read_file(self.BUCKET_NAME, "backup/file.txt") == data

        # Delete single file
        deleted = connector.delete_file(self.BUCKET_NAME, "data/file.txt")
        assert deleted is True

        # Delete directory prefix
        connector.write_file(self.BUCKET_NAME, "del_batch/a.txt", b"a")
        connector.write_file(self.BUCKET_NAME, "del_batch/b.txt", b"b")
        del_count = connector.delete_directory(self.BUCKET_NAME, "del_batch")
        assert del_count == 2


    def test_s3_missing_bucket_raises(self):
        conn = AmazonS3Connector({"region_name": "us-east-1"})
        with pytest.raises(StorageException) as exc_info:
            conn._get_bucket_name(None)
        assert exc_info.value.category == StorageErrorCategory.INVALID_PATH

    def test_s3_error_classification_403(self):
        from botocore.exceptions import ClientError
        conn = AmazonS3Connector({"bucket": "test-b"})
        with pytest.raises(StorageException) as exc_info:
            err = ClientError({
                "Error": {"Code": "AccessDenied", "Message": "Access Denied by IAM Policy"},
                "ResponseMetadata": {"HTTPStatusCode": 403}
            }, "GetObject")
            conn._classify_and_raise(err, "GetObject")
        assert exc_info.value.category == StorageErrorCategory.AUTHENTICATION_FAILED
        assert exc_info.value.status_code == 403

    def test_s3_kms_encryption(self, s3_client):
        kms_conn = AmazonS3Connector({
            "bucket": self.BUCKET_NAME,
            "region_name": "us-east-1",
            "access_key_id": "testing",
            "secret_access_key": "testing",
            "server_side_encryption": "aws:kms",
            "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
        })
        payload = b"KMS Encrypted Payload"
        kms_conn.write_file(self.BUCKET_NAME, "kms/secure.csv", payload)
        meta = kms_conn.get_object_metadata(self.BUCKET_NAME, "kms/secure.csv")
        assert meta.size_in_bytes == len(payload)


class TestAmazonS3LiveIntegration:
    """Optional live integration test against actual AWS account when credentials exist."""

    @pytest.mark.skipif(
        not os.environ.get("DATAFORGE_AWS_ACCESS_KEY_ID"),
        reason="DATAFORGE_AWS_ACCESS_KEY_ID not provided. Skipping live AWS S3 test."
    )
    def test_live_aws_s3_roundtrip(self):
        conn = AmazonS3Connector({
            "access_key_id": os.environ["DATAFORGE_AWS_ACCESS_KEY_ID"],
            "secret_access_key": os.environ["DATAFORGE_AWS_SECRET_ACCESS_KEY"],
            "region_name": os.environ.get("DATAFORGE_AWS_REGION", "us-east-1"),
            "bucket": os.environ.get("DATAFORGE_AWS_BUCKET")
        })
        res = conn.test_connection()
        assert res.success is True
