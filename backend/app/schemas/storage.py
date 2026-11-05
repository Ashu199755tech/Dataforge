from typing import Optional, Dict, Any, List, Literal, Union
from pydantic import BaseModel, Field, SecretStr


class LocalStorageConfig(BaseModel):
    """Configuration for local filesystem / shared NFS/SMB mount storage."""
    provider_type: Literal["local_storage", "local_file"] = "local_storage"
    base_path: str = Field(default="./data_storage", description="Base root directory for storage")
    create_if_missing: bool = Field(default=True, description="Automatically create root directory if missing")


class AzureBlobStorageConfig(BaseModel):
    """Configuration for Microsoft Azure Blob Storage."""
    provider_type: Literal["azure_blob"] = "azure_blob"
    account_name: str = Field(..., description="Azure Storage Account Name")
    container_name: Optional[str] = Field(default=None, description="Default Azure Blob Container Name")
    auth_mode: Literal["account_key", "sas_token", "service_principal", "managed_identity"] = Field(
        default="account_key",
        description="Authentication mechanism"
    )
    # Auth credentials (sanitized on export)
    account_key: Optional[str] = Field(default=None, description="Storage Account Key")
    sas_token: Optional[str] = Field(default=None, description="Shared Access Signature token")
    client_id: Optional[str] = Field(default=None, description="Azure Service Principal Client ID")
    client_secret: Optional[str] = Field(default=None, description="Azure Service Principal Client Secret")
    tenant_id: Optional[str] = Field(default=None, description="Azure Active Directory Tenant ID")
    endpoint_suffix: str = Field(default="core.windows.net", description="Azure cloud endpoint suffix")
    custom_endpoint: Optional[str] = Field(default=None, description="Custom endpoint for Azurite emulator")


class AzureADLSGen2Config(BaseModel):
    """Configuration for Microsoft Azure Data Lake Storage Gen2."""
    provider_type: Literal["azure_adls", "azure_datalake"] = "azure_adls"
    account_name: str = Field(..., description="Azure Storage Account Name")
    filesystem: Optional[str] = Field(default=None, description="ADLS Gen2 Filesystem / Container Name")
    auth_mode: Literal["account_key", "sas_token", "service_principal", "managed_identity"] = Field(
        default="account_key",
        description="Authentication mechanism"
    )
    account_key: Optional[str] = Field(default=None, description="Storage Account Key")
    sas_token: Optional[str] = Field(default=None, description="Shared Access Signature token")
    client_id: Optional[str] = Field(default=None, description="Azure Service Principal Client ID")
    client_secret: Optional[str] = Field(default=None, description="Azure Service Principal Client Secret")
    tenant_id: Optional[str] = Field(default=None, description="Azure Active Directory Tenant ID")
    endpoint_suffix: str = Field(default="dfs.core.windows.net", description="ADLS Gen2 DFS endpoint suffix")
    custom_endpoint: Optional[str] = Field(default=None, description="Custom endpoint for Azurite emulator")


class AWSS3Config(BaseModel):
    """Configuration for Amazon Web Services (AWS) S3."""
    provider_type: Literal["aws_s3", "s3"] = "aws_s3"
    bucket: Optional[str] = Field(default=None, description="Default S3 Bucket Name")
    region_name: str = Field(default="us-east-1", description="AWS Region (e.g. us-east-1, eu-west-1)")
    auth_mode: Literal["access_key", "iam_role", "sts_assume_role", "default_chain"] = Field(
        default="access_key",
        description="AWS Authentication method"
    )
    access_key_id: Optional[str] = Field(default=None, description="AWS Access Key ID")
    secret_access_key: Optional[str] = Field(default=None, description="AWS Secret Access Key")
    session_token: Optional[str] = Field(default=None, description="AWS Session Token (for temporary credentials)")
    role_arn: Optional[str] = Field(default=None, description="IAM Role ARN for STS AssumeRole")
    role_session_name: Optional[str] = Field(default="DataForgeTransferSession", description="STS Session Name")
    external_id: Optional[str] = Field(default=None, description="STS External ID for cross-account access")
    endpoint_url: Optional[str] = Field(default=None, description="Custom endpoint for Moto/LocalStack/MinIO")
    server_side_encryption: Optional[Literal["AES256", "aws:kms"]] = Field(
        default=None,
        description="Server-side encryption algorithm"
    )
    kms_key_id: Optional[str] = Field(default=None, description="AWS KMS Key ID or ARN")


class GCSConfig(BaseModel):
    """Configuration for Google Cloud Platform (GCP) Cloud Storage."""
    provider_type: Literal["gcp_storage", "gcs"] = "gcp_storage"
    project_id: Optional[str] = Field(default=None, description="Google Cloud Project ID")
    bucket: Optional[str] = Field(default=None, description="Default GCS Bucket Name")
    auth_mode: Literal["service_account_json", "service_account_path", "adc", "workload_identity"] = Field(
        default="service_account_json",
        description="GCP Authentication method"
    )
    service_account_json: Optional[Union[Dict[str, Any], str]] = Field(
        default=None,
        description="Service account JSON key content or string"
    )
    service_account_path: Optional[str] = Field(default=None, description="Path to Service Account JSON key file")
    impersonate_service_account: Optional[str] = Field(default=None, description="Target SA email for impersonation")
    custom_endpoint: Optional[str] = Field(default=None, description="Custom endpoint for GCS emulator")


SENSITIVE_STORAGE_FIELDS = {
    "account_key",
    "sas_token",
    "client_secret",
    "secret_access_key",
    "session_token",
    "service_account_json",
    "private_key",
    "private_key_id",
}


def sanitize_storage_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a copy of the configuration dictionary with all sensitive
    credentials, tokens, and private keys securely redacted.
    """
    sanitized: Dict[str, Any] = {}
    for k, v in config.items():
        if k in SENSITIVE_STORAGE_FIELDS:
            sanitized[k] = "***REDACTED***" if v else None
        elif isinstance(v, dict):
            sanitized[k] = sanitize_storage_config(v)
        else:
            sanitized[k] = v
    return sanitized
