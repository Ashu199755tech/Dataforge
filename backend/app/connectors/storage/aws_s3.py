import io
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
from backend.app.connectors.storage.aws_auth import create_boto3_s3_client

try:
    import boto3
    import botocore
    from botocore.exceptions import ClientError, BotoCoreError, EndpointConnectionError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class AmazonS3Connector(BaseStorageConnector):
    """
    Amazon Web Services (AWS) S3 Storage Connector.
    Supports IAM Access Key, Session Token, STS AssumeRole, and Default Credential Chains.
    Implements bucket discovery, prefix browsing, chunked streaming, multipart uploads,
    server-side encryption (SSE-S3, SSE-KMS), and metadata inspection.
    """

    # S3 requires minimum 5MB per part for multipart uploads (except final part)
    MIN_MULTIPART_CHUNK_SIZE = 5 * 1024 * 1024

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if not HAS_BOTO3:
            raise StorageException(
                "boto3/botocore is not installed. Install with: pip install boto3 botocore",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider="aws_s3"
            )
        self.default_bucket = config.get("bucket") or config.get("bucket_name")
        self.server_side_encryption = config.get("server_side_encryption")
        self.kms_key_id = config.get("kms_key_id")
        self._s3_client = None

    def get_capabilities(self) -> Set[StorageCapability]:
        return {
            StorageCapability.BUCKET_DISCOVERY,
            StorageCapability.DIRECTORY_OPERATIONS,
            StorageCapability.STREAM_READ,
            StorageCapability.STREAM_WRITE,
            StorageCapability.MULTIPART_UPLOAD,
            StorageCapability.SERVER_SIDE_ENCRYPTION,
            StorageCapability.STORAGE_TIERING,
            StorageCapability.PRESIGNED_URLS,
            StorageCapability.DELETE_OBJECT,
            StorageCapability.COPY_OBJECT,
        }

    @property
    def s3_client(self):
        if self._s3_client is None:
            self.connect()
        return self._s3_client

    def connect(self) -> None:
        self._s3_client = create_boto3_s3_client(self.config)
        self._connected = True

    def close(self) -> None:
        if self._s3_client is not None:
            try:
                self._s3_client.close()
            except Exception:
                pass
            self._s3_client = None
        self._connected = False

    def _classify_and_raise(self, err: Exception, operation: str) -> None:
        if isinstance(err, StorageException):
            raise err
        msg = str(err)
        cat = StorageErrorCategory.UNKNOWN
        status = None

        if isinstance(err, ClientError):
            err_code = err.response.get("Error", {}).get("Code", "")
            err_msg = err.response.get("Error", {}).get("Message", msg)
            status = err.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if err_code in ("AccessDenied", "AuthFailure", "InvalidAccessKeyId", "SignatureDoesNotMatch") or status in (401, 403):
                cat = StorageErrorCategory.AUTHENTICATION_FAILED
            elif err_code in ("NoSuchBucket", "NotFound") or status == 404:
                cat = StorageErrorCategory.NOT_FOUND
            elif err_code == "NoSuchKey":
                cat = StorageErrorCategory.NOT_FOUND
            elif "SlowDown" in err_code or status == 429:
                cat = StorageErrorCategory.RATE_LIMITED
            msg = f"[{err_code}] {err_msg}"
        elif isinstance(err, EndpointConnectionError):
            cat = StorageErrorCategory.NETWORK_TIMEOUT

        raise StorageException(
            f"AWS S3 error during {operation}: {msg}",
            category=cat,
            provider="aws_s3",
            status_code=status,
            original_exception=err
        )

    # ------------------------------------------------------------------
    # Connection Testing
    # ------------------------------------------------------------------

    def test_connection(self) -> ConnectionTestResult:
        start = time.time()
        try:
            client = self.s3_client
            # Verify connectivity via list_buckets or head_bucket
            if self.default_bucket:
                client.head_bucket(Bucket=self.default_bucket)
                ver_msg = f"S3 Bucket '{self.default_bucket}' accessible"
            else:
                resp = client.list_buckets()
                cnt = len(resp.get("Buckets", []))
                ver_msg = f"AWS S3 API accessible ({cnt} buckets found)"

            latency = round((time.time() - start) * 1000, 2)
            return ConnectionTestResult(
                success=True,
                message=f"Successfully connected to AWS S3: {ver_msg}",
                latency_ms=latency,
                server_version="Amazon S3 Engine"
            )
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            clean_err = StorageException._sanitize_message(str(e))
            return ConnectionTestResult(
                success=False,
                message=f"AWS S3 connection failed: {clean_err}",
                latency_ms=latency
            )

    # ------------------------------------------------------------------
    # Bucket & Prefix Browsing
    # ------------------------------------------------------------------

    def list_containers(self) -> List[str]:
        try:
            resp = self.s3_client.list_buckets()
            return [b["Name"] for b in resp.get("Buckets", [])]
        except Exception as e:
            self._classify_and_raise(e, "list_containers")

    def _get_bucket_name(self, container: Optional[str]) -> str:
        bname = container or self.default_bucket
        if not bname:
            raise StorageException(
                "No S3 bucket specified and no default bucket configured.",
                category=StorageErrorCategory.INVALID_PATH,
                provider="aws_s3"
            )
        return bname

    def list_directories(self, container: str, prefix: str = "") -> List[str]:
        bname = self._get_bucket_name(container)
        norm_prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            dirs = []
            for page in paginator.paginate(Bucket=bname, Prefix=norm_prefix, Delimiter="/"):
                for cp in page.get("CommonPrefixes", []):
                    dirs.append(cp["Prefix"].rstrip("/"))
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
        bname = self._get_bucket_name(container)
        norm_prefix = prefix.strip("/")
        if norm_prefix:
            norm_prefix += "/" if not norm_prefix.endswith("/") else ""

        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            kwargs = {"Bucket": bname, "Prefix": norm_prefix}
            if not recursive:
                kwargs["Delimiter"] = "/"

            count = 0
            for page in paginator.paginate(**kwargs):
                if not recursive:
                    # CommonPrefixes represent virtual directories
                    for cp in page.get("CommonPrefixes", []):
                        dir_path = cp["Prefix"].rstrip("/")
                        yield StorageItem(
                            name=dir_path.split("/")[-1],
                            path=dir_path,
                            is_directory=True,
                            size_in_bytes=0,
                            content_type="inode/directory"
                        )
                        count += 1
                        if limit and count >= limit:
                            return

                for obj in page.get("Contents", []):
                    # Skip the folder marker itself if it matches the prefix exactly
                    if obj["Key"].endswith("/") and obj["Size"] == 0:
                        continue
                    yield StorageItem(
                        name=obj["Key"].split("/")[-1],
                        path=obj["Key"],
                        is_directory=False,
                        size_in_bytes=obj["Size"],
                        last_modified=obj["LastModified"],
                        etag=obj["ETag"].strip('"') if obj.get("ETag") else None,
                        storage_tier=obj.get("StorageClass", "STANDARD")
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
            resp = self.s3_client.head_object(Bucket=bname, Key=norm_key)
            return StorageItem(
                name=norm_key.split("/")[-1],
                path=norm_key,
                is_directory=False,
                size_in_bytes=resp["ContentLength"],
                last_modified=resp["LastModified"],
                content_type=resp.get("ContentType", "application/octet-stream"),
                etag=resp.get("ETag", "").strip('"'),
                metadata=resp.get("Metadata", {}),
                storage_tier=resp.get("StorageClass", "STANDARD")
            )
        except Exception as e:
            self._classify_and_raise(e, "get_object_metadata")

    # ------------------------------------------------------------------
    # Streaming Read & Multipart Write
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
            resp = self.s3_client.get_object(Bucket=bname, Key=norm_key)
            body = resp["Body"]
            for chunk in body.iter_chunks(chunk_size):
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

        # Prepare upload params
        extra_args = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata
        if self.server_side_encryption:
            extra_args["ServerSideEncryption"] = self.server_side_encryption
            if self.kms_key_id:
                extra_args["SSEKMSKeyId"] = self.kms_key_id

        # Buffer initial chunks to decide between single PutObject (< 5MB) and Multipart
        buffer = bytearray()
        part_number = 1
        parts = []
        upload_id = None
        total_bytes = 0

        try:
            for chunk in stream:
                buffer.extend(chunk)
                total_bytes += len(chunk)

                # If buffer reaches threshold (5MB), start multipart
                if len(buffer) >= self.MIN_MULTIPART_CHUNK_SIZE:
                    if upload_id is None:
                        create_resp = self.s3_client.create_multipart_upload(
                            Bucket=bname,
                            Key=norm_key,
                            **extra_args
                        )
                        upload_id = create_resp["UploadId"]

                    part_resp = self.s3_client.upload_part(
                        Bucket=bname,
                        Key=norm_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=bytes(buffer)
                    )
                    parts.append({"PartNumber": part_number, "ETag": part_resp["ETag"]})
                    part_number += 1
                    buffer.clear()

            # Finalize upload
            if upload_id is None:
                # Payload fit entirely within single PutObject
                self.s3_client.put_object(
                    Bucket=bname,
                    Key=norm_key,
                    Body=bytes(buffer),
                    **extra_args
                )
            else:
                # Upload remaining buffer if any
                if len(buffer) > 0:
                    part_resp = self.s3_client.upload_part(
                        Bucket=bname,
                        Key=norm_key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=bytes(buffer)
                    )
                    parts.append({"PartNumber": part_number, "ETag": part_resp["ETag"]})

                self.s3_client.complete_multipart_upload(
                    Bucket=bname,
                    Key=norm_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts}
                )

            return total_bytes

        except Exception as e:
            if upload_id:
                try:
                    self.s3_client.abort_multipart_upload(
                        Bucket=bname,
                        Key=norm_key,
                        UploadId=upload_id
                    )
                except Exception:
                    pass
            self._classify_and_raise(e, "write_stream")

    # ------------------------------------------------------------------
    # Mutation: Delete, Copy
    # ------------------------------------------------------------------

    def delete_file(self, container: str, object_key: str) -> bool:
        bname = self._get_bucket_name(container)
        norm_key = object_key.lstrip("/")
        try:
            self.s3_client.delete_object(Bucket=bname, Key=norm_key)
            return True
        except Exception as e:
            self._classify_and_raise(e, "delete_file")

    def delete_directory(self, container: str, prefix: str) -> int:
        bname = self._get_bucket_name(container)
        norm_prefix = prefix.strip("/") + "/" if prefix.strip("/") else ""
        try:
            paginator = self.s3_client.get_paginator("list_objects_v2")
            deleted_count = 0
            for page in paginator.paginate(Bucket=bname, Prefix=norm_prefix):
                objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if objects:
                    self.s3_client.delete_objects(
                        Bucket=bname,
                        Delete={"Objects": objects, "Quiet": True}
                    )
                    deleted_count += len(objects)
            return deleted_count
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
            copy_source = {"Bucket": src_bname, "Key": src_key.lstrip("/")}
            extra_args = {}
            if self.server_side_encryption:
                extra_args["ServerSideEncryption"] = self.server_side_encryption
            
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=dst_bname,
                Key=dst_key.lstrip("/"),
                **extra_args
            )
            return True
        except Exception as e:
            self._classify_and_raise(e, "copy_file")


# Register concrete connector into provider registry
StorageProviderRegistry._providers["aws_s3"]["connector_class"] = AmazonS3Connector
