from typing import Dict, Any, List, Optional, Callable, Type, Set
from pydantic import BaseModel, Field
from backend.app.connectors.storage.models import (
    StorageCapability,
    StorageErrorCategory,
    StorageException
)
from backend.app.connectors.storage.base import BaseStorageConnector
from backend.app.schemas.storage import (
    LocalStorageConfig,
    AzureBlobStorageConfig,
    AzureADLSGen2Config,
    AWSS3Config,
    GCSConfig
)


class StorageProviderInfo(BaseModel):
    """Metadata describing a registered cloud/local storage provider."""
    provider_type: str
    display_name: str
    is_available: bool
    missing_reason: Optional[str] = None
    required_packages: List[str] = Field(default_factory=list)
    supported_capabilities: List[str] = Field(default_factory=list)


class StorageProviderRegistry:
    """
    Central registry for multi-cloud and local storage providers.
    Supports dynamic lazy-loading of provider SDKs (Rule 20: No mandatory cloud SDKs).
    """

    _providers: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_provider(
        cls,
        provider_type: str,
        display_name: str,
        connector_class: Optional[Type[BaseStorageConnector]],
        config_schema: Type[BaseModel],
        check_availability: Callable[[], tuple[bool, Optional[str]]],
        required_packages: List[str],
        default_capabilities: Set[StorageCapability]
    ) -> None:
        """Registers a storage connector provider."""
        ptype = provider_type.lower()
        cls._providers[ptype] = {
            "display_name": display_name,
            "connector_class": connector_class,
            "config_schema": config_schema,
            "check_availability": check_availability,
            "required_packages": required_packages,
            "default_capabilities": default_capabilities
        }

    @classmethod
    def is_provider_available(cls, provider_type: str) -> bool:
        """Returns True if the provider and its required SDK dependencies are available."""
        ptype = provider_type.lower()
        entry = cls._providers.get(ptype)
        if not entry:
            return False
        avail, _ = entry["check_availability"]()
        return avail

    @classmethod
    def get_missing_dependency_message(cls, provider_type: str) -> Optional[str]:
        """Returns installation instructions or error message if dependencies are missing."""
        ptype = provider_type.lower()
        entry = cls._providers.get(ptype)
        if not entry:
            return f"Storage provider '{provider_type}' is not registered."
        _, reason = entry["check_availability"]()
        return reason

    @classmethod
    def list_providers(cls) -> List[StorageProviderInfo]:
        """Lists all registered storage providers with live availability diagnostics."""
        result = []
        for ptype, entry in cls._providers.items():
            avail, reason = entry["check_availability"]()
            caps = [c.value for c in entry["default_capabilities"]]
            result.append(StorageProviderInfo(
                provider_type=ptype,
                display_name=entry["display_name"],
                is_available=avail,
                missing_reason=reason,
                required_packages=entry["required_packages"],
                supported_capabilities=caps
            ))
        return result

    @classmethod
    def create_connector(cls, provider_type: str, config: Dict[str, Any]) -> BaseStorageConnector:
        """
        Instantiates a storage connector for the requested provider.
        Validates dependencies and raises structured StorageException if missing.
        """
        ptype = provider_type.lower()
        # Aliases
        if ptype in ("s3", "amazon_s3"):
            ptype = "aws_s3"
        elif ptype in ("blob", "azure_blob_storage"):
            ptype = "azure_blob"
        elif ptype in ("adls", "adls_gen2", "azure_datalake"):
            ptype = "azure_adls"
        elif ptype in ("gcs", "google_storage"):
            ptype = "gcp_storage"
        elif ptype in ("local", "file", "filesystem", "local_file"):
            ptype = "local_storage"

        entry = cls._providers.get(ptype)
        if not entry:
            supported = ", ".join(cls._providers.keys())
            raise StorageException(
                f"Unknown storage provider '{provider_type}'. Supported providers: {supported}",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider=ptype
            )

        avail, reason = entry["check_availability"]()
        if not avail:
            packages = " ".join(entry["required_packages"])
            msg = (
                f"Storage provider '{entry['display_name']}' is unavailable because required SDK dependencies are missing. "
                f"Diagnostic details: {reason}. To enable this provider, install: pip install {packages}"
            )
            raise StorageException(
                msg,
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider=ptype
            )

        conn_cls = entry["connector_class"]
        if conn_cls is None:
            raise StorageException(
                f"Storage connector class for provider '{ptype}' is not implemented yet.",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider=ptype
            )

        return conn_cls(config)


# ----------------------------------------------------------------------
# Availability Checkers for Cloud SDKs (Rule 20 Compliance)
# ----------------------------------------------------------------------

def _check_local_availability() -> tuple[bool, Optional[str]]:
    return True, None


def _check_azure_blob_availability() -> tuple[bool, Optional[str]]:
    try:
        import azure.storage.blob  # noqa
        return True, None
    except ImportError as e:
        return False, f"Missing Python package 'azure-storage-blob' ({str(e)})"


def _check_azure_adls_availability() -> tuple[bool, Optional[str]]:
    try:
        import azure.storage.filedatalake  # noqa
        return True, None
    except ImportError as e:
        return False, f"Missing Python package 'azure-storage-file-datalake' ({str(e)})"


def _check_aws_s3_availability() -> tuple[bool, Optional[str]]:
    try:
        import boto3  # noqa
        import botocore  # noqa
        return True, None
    except ImportError as e:
        return False, f"Missing Python package 'boto3' / 'botocore' ({str(e)})"


def _check_gcp_storage_availability() -> tuple[bool, Optional[str]]:
    try:
        import google.cloud.storage  # noqa
        return True, None
    except ImportError as e:
        return False, f"Missing Python package 'google-cloud-storage' ({str(e)})"


# ----------------------------------------------------------------------
# Initial Registration of Standard Providers
# ----------------------------------------------------------------------

StorageProviderRegistry.register_provider(
    provider_type="local_storage",
    display_name="Local Filesystem & Network Storage",
    connector_class=None,  # Bound when LocalStorageConnector module is imported
    config_schema=LocalStorageConfig,
    check_availability=_check_local_availability,
    required_packages=[],
    default_capabilities={
        StorageCapability.CONTAINER_DISCOVERY,
        StorageCapability.DIRECTORY_OPERATIONS,
        StorageCapability.STREAM_READ,
        StorageCapability.STREAM_WRITE,
        StorageCapability.DELETE_OBJECT,
        StorageCapability.COPY_OBJECT,
        StorageCapability.MOVE_OBJECT
    }
)

StorageProviderRegistry.register_provider(
    provider_type="azure_blob",
    display_name="Azure Blob Storage",
    connector_class=None,  # Bound in Phase 2
    config_schema=AzureBlobStorageConfig,
    check_availability=_check_azure_blob_availability,
    required_packages=["azure-storage-blob", "azure-identity"],
    default_capabilities={
        StorageCapability.CONTAINER_DISCOVERY,
        StorageCapability.DIRECTORY_OPERATIONS,
        StorageCapability.STREAM_READ,
        StorageCapability.STREAM_WRITE,
        StorageCapability.MULTIPART_UPLOAD,
        StorageCapability.PRESIGNED_URLS,
        StorageCapability.DELETE_OBJECT,
        StorageCapability.COPY_OBJECT
    }
)

StorageProviderRegistry.register_provider(
    provider_type="azure_adls",
    display_name="Azure Data Lake Storage Gen2 (ADLS Gen2)",
    connector_class=None,  # Bound in Phase 2
    config_schema=AzureADLSGen2Config,
    check_availability=_check_azure_adls_availability,
    required_packages=["azure-storage-file-datalake", "azure-identity"],
    default_capabilities={
        StorageCapability.CONTAINER_DISCOVERY,
        StorageCapability.HIERARCHICAL_NAMESPACE,
        StorageCapability.DIRECTORY_OPERATIONS,
        StorageCapability.STREAM_READ,
        StorageCapability.STREAM_WRITE,
        StorageCapability.MULTIPART_UPLOAD,
        StorageCapability.DELETE_OBJECT,
        StorageCapability.COPY_OBJECT,
        StorageCapability.MOVE_OBJECT
    }
)

StorageProviderRegistry.register_provider(
    provider_type="aws_s3",
    display_name="Amazon Web Services S3",
    connector_class=None,  # Bound in Phase 3
    config_schema=AWSS3Config,
    check_availability=_check_aws_s3_availability,
    required_packages=["boto3", "botocore"],
    default_capabilities={
        StorageCapability.BUCKET_DISCOVERY,
        StorageCapability.DIRECTORY_OPERATIONS,
        StorageCapability.STREAM_READ,
        StorageCapability.STREAM_WRITE,
        StorageCapability.MULTIPART_UPLOAD,
        StorageCapability.SERVER_SIDE_ENCRYPTION,
        StorageCapability.STORAGE_TIERING,
        StorageCapability.PRESIGNED_URLS,
        StorageCapability.DELETE_OBJECT,
        StorageCapability.COPY_OBJECT
    }
)

StorageProviderRegistry.register_provider(
    provider_type="gcp_storage",
    display_name="Google Cloud Storage (GCS)",
    connector_class=None,  # Bound in Phase 4
    config_schema=GCSConfig,
    check_availability=_check_gcp_storage_availability,
    required_packages=["google-cloud-storage", "google-auth"],
    default_capabilities={
        StorageCapability.BUCKET_DISCOVERY,
        StorageCapability.DIRECTORY_OPERATIONS,
        StorageCapability.STREAM_READ,
        StorageCapability.STREAM_WRITE,
        StorageCapability.RESUMABLE_UPLOAD,
        StorageCapability.STORAGE_TIERING,
        StorageCapability.PRESIGNED_URLS,
        StorageCapability.DELETE_OBJECT,
        StorageCapability.COPY_OBJECT
    }
)
