from enum import Enum
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from pydantic import BaseModel, Field


class StorageCapability(str, Enum):
    """Capabilities supported by storage providers."""
    BUCKET_DISCOVERY = "bucket_discovery"
    CONTAINER_DISCOVERY = "container_discovery"
    HIERARCHICAL_NAMESPACE = "hierarchical_namespace"  # Native atomic directory operations (e.g., ADLS Gen2)
    DIRECTORY_OPERATIONS = "directory_operations"      # Virtual or native directory listing & deletion
    STREAM_READ = "stream_read"                        # Chunked streaming binary read
    STREAM_WRITE = "stream_write"                      # Chunked streaming binary write
    MULTIPART_UPLOAD = "multipart_upload"              # AWS S3 / Azure Block Blob multipart uploads
    RESUMABLE_UPLOAD = "resumable_upload"              # GCP GCS resumable sessions
    SERVER_SIDE_ENCRYPTION = "server_side_encryption"  # KMS, customer-managed or provider-managed keys
    STORAGE_TIERING = "storage_tiering"                # Hot, Cool, Cold, Archive tiering
    PRESIGNED_URLS = "presigned_urls"                  # Ephemeral shared access tokens/URLs
    DELETE_OBJECT = "delete_object"                    # Single object deletion
    COPY_OBJECT = "copy_object"                        # Provider-side copy
    MOVE_OBJECT = "move_object"                        # Provider-side move / rename


class StorageErrorCategory(str, Enum):
    """Classified storage error types for enterprise monitoring & diagnostics."""
    AUTHENTICATION_FAILED = "authentication_failed"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    BUCKET_NOT_FOUND = "bucket_not_found"
    QUOTA_EXCEEDED = "quota_exceeded"
    NETWORK_TIMEOUT = "network_timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_PATH = "invalid_path"
    OPERATION_NOT_SUPPORTED = "operation_not_supported"
    INTEGRITY_CHECK_FAILED = "integrity_check_failed"
    UNKNOWN = "unknown"


class StorageItem(BaseModel):
    """Represents an object, file, or virtual directory in cloud/local storage."""
    name: str = Field(..., description="Basename of the file or directory")
    path: str = Field(..., description="Full relative path within the container or bucket")
    is_directory: bool = Field(default=False, description="True if this item represents a directory or prefix")
    size_in_bytes: int = Field(default=0, description="Size in bytes (0 for directories)")
    last_modified: Optional[datetime] = Field(default=None, description="Last modification timestamp")
    content_type: Optional[str] = Field(default=None, description="MIME content type (e.g. application/octet-stream)")
    etag: Optional[str] = Field(default=None, description="Entity tag or hash string")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Custom metadata tags")
    storage_tier: Optional[str] = Field(default=None, description="Storage tier (Hot, Standard, Cold, Archive, etc.)")


class StorageMetadata(BaseModel):
    """Detailed metadata for a storage item or container."""
    item: StorageItem
    container: str
    owner: Optional[str] = None
    encryption_algorithm: Optional[str] = None
    kms_key_id: Optional[str] = None
    checksum_sha256: Optional[str] = None
    checksum_md5: Optional[str] = None
    checksum_crc32c: Optional[str] = None
    custom_properties: Dict[str, Any] = Field(default_factory=dict)


class StorageException(Exception):
    """
    Standardized exception thrown by all storage connectors.
    Sanitizes secrets, wraps the underlying provider exception, and classifies errors.
    """
    def __init__(
        self,
        message: str,
        category: StorageErrorCategory = StorageErrorCategory.UNKNOWN,
        provider: str = "storage",
        status_code: Optional[int] = None,
        original_exception: Optional[Exception] = None
    ):
        self.category = category
        self.provider = provider
        self.status_code = status_code
        self.original_exception = original_exception
        # Ensure credentials/tokens are never exposed in exception strings
        sanitized_msg = self._sanitize_message(message)
        super().__init__(f"[{provider.upper()}][{category.value}] {sanitized_msg}")

    @staticmethod
    def _sanitize_message(msg: str) -> str:
        import re
        # Mask AWS keys, Azure SAS signatures, GCP private keys, Bearer tokens
        sanitized = re.sub(r'(sig|signature|token|key|secret|password)=([^&\s]+)', r'\1=***REDACTED***', msg, flags=re.IGNORECASE)
        sanitized = re.sub(r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', 'Bearer ***REDACTED***', sanitized)
        sanitized = re.sub(r'(AKIA[0-9A-Z]{16})', '***AWS_KEY_REDACTED***', sanitized)
        return sanitized
