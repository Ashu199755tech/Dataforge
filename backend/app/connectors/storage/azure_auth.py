from typing import Dict, Any, Optional, Tuple
from backend.app.connectors.storage.models import StorageErrorCategory, StorageException

try:
    from azure.identity import (
        ClientSecretCredential,
        ManagedIdentityCredential,
        DefaultAzureCredential
    )
    from azure.core.credentials import AzureSasCredential
    HAS_AZURE_IDENTITY = True
except ImportError:
    HAS_AZURE_IDENTITY = False

# Well-known Azurite emulator credentials
AZURITE_ACCOUNT_NAME = "devstoreaccount1"
AZURITE_ACCOUNT_KEY = (
    "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="
)


def build_azure_credentials_and_endpoints(
    config: Dict[str, Any],
    service_type: str = "blob"  # "blob" or "dfs"
) -> Tuple[str, Any, Optional[str]]:
    """
    Parses configuration and returns:
    (service_url, credential, connection_string)
    
    Supports:
    1. Direct connection_string (including UseDevelopmentStorage=true)
    2. Account Key (or Azurite dev account)
    3. SAS Token
    4. Service Principal (Client ID + Client Secret + Tenant ID)
    5. Managed Identity (or DefaultAzureCredential)
    """
    conn_str = config.get("connection_string")
    account_name = config.get("account_name", "").strip()
    account_key = config.get("account_key", "").strip()
    sas_token = config.get("sas_token", "").strip()
    auth_mode = config.get("auth_mode", "account_key").lower()
    custom_endpoint = config.get("custom_endpoint", "").strip()
    endpoint_suffix = config.get("endpoint_suffix", "core.windows.net").strip()

    # Azurite connection string shortcut
    if config.get("use_development_storage") or account_name == AZURITE_ACCOUNT_NAME:
        if not custom_endpoint:
            custom_endpoint = "http://127.0.0.1:10000" if service_type == "blob" else "http://127.0.0.1:10002"
        account_name = AZURITE_ACCOUNT_NAME
        account_key = account_key or AZURITE_ACCOUNT_KEY

    # 1. Connection string mode
    if conn_str:
        return "", None, conn_str

    if not account_name:
        raise StorageException(
            "Azure Storage 'account_name' is required when connection_string is not provided.",
            category=StorageErrorCategory.AUTHENTICATION_FAILED,
            provider=f"azure_{service_type}"
        )

    # Custom endpoint with account key (e.g. Azurite emulator or private storage gateway)
    if custom_endpoint and account_key:
        endpoint = custom_endpoint.rstrip("/")
        if not endpoint.endswith(account_name):
            endpoint = f"{endpoint}/{account_name}"
        protocol = "http" if endpoint.startswith("http://") else "https"
        ep_param = "BlobEndpoint" if service_type == "blob" else "BlobEndpoint"
        built_conn_str = (
            f"DefaultEndpointsProtocol={protocol};"
            f"AccountName={account_name};"
            f"AccountKey={account_key};"
            f"{ep_param}={endpoint};"
        )
        return "", None, built_conn_str


    # Resolve service URL
    if custom_endpoint:
        # Emulator / custom endpoint format: e.g. http://127.0.0.1:10000/devstoreaccount1
        base = custom_endpoint.rstrip("/")
        if not base.endswith(account_name):
            service_url = f"{base}/{account_name}"
        else:
            service_url = base
    else:
        domain = "blob" if service_type == "blob" else "dfs"
        service_url = f"https://{account_name}.{domain}.{endpoint_suffix}"

    # 2. SAS Token
    if auth_mode == "sas_token" or sas_token:
        clean_sas = sas_token.lstrip("?")
        if not HAS_AZURE_IDENTITY:
            # Can append SAS to URL or use AzureSasCredential
            return f"{service_url}?{clean_sas}", None, None
        return service_url, AzureSasCredential(clean_sas), None

    # 3. Service Principal
    if auth_mode == "service_principal":
        client_id = config.get("client_id", "").strip()
        client_secret = config.get("client_secret", "").strip()
        tenant_id = config.get("tenant_id", "").strip()
        if not (client_id and client_secret and tenant_id):
            raise StorageException(
                "Service Principal auth requires 'client_id', 'client_secret', and 'tenant_id'.",
                category=StorageErrorCategory.AUTHENTICATION_FAILED,
                provider=f"azure_{service_type}"
            )
        if not HAS_AZURE_IDENTITY:
            raise StorageException(
                "azure-identity is required for Service Principal authentication. Install with: pip install azure-identity",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider=f"azure_{service_type}"
            )
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        return service_url, credential, None

    # 4. Managed Identity
    if auth_mode in ("managed_identity", "default_identity", "adc"):
        if not HAS_AZURE_IDENTITY:
            raise StorageException(
                "azure-identity is required for Managed Identity authentication.",
                category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
                provider=f"azure_{service_type}"
            )
        client_id = config.get("client_id")
        credential = ManagedIdentityCredential(client_id=client_id) if client_id else DefaultAzureCredential()
        return service_url, credential, None

    # 5. Account Key (SharedKey)
    if account_key:
        return service_url, account_key, None

    # Fallback to DefaultAzureCredential if available
    if HAS_AZURE_IDENTITY:
        return service_url, DefaultAzureCredential(), None

    raise StorageException(
        f"No valid authentication credentials found for Azure Storage account '{account_name}'.",
        category=StorageErrorCategory.AUTHENTICATION_FAILED,
        provider=f"azure_{service_type}"
    )
