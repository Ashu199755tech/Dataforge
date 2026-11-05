import json
from typing import Dict, Any, Tuple, Optional
from backend.app.connectors.storage.models import StorageErrorCategory, StorageException

try:
    import google.auth
    from google.oauth2 import service_account
    from google.auth.impersonated_credentials import Credentials as ImpersonatedCredentials
    from google.cloud import storage
    from google.api_core.exceptions import GoogleAPICallError
    HAS_GCP_STORAGE = True
except ImportError:
    HAS_GCP_STORAGE = False


def create_gcp_storage_client(config: Dict[str, Any]) -> Any:
    """
    Creates and returns a configured google.cloud.storage.Client supporting:
    1. Service Account JSON key (inline dict or JSON string)
    2. Service Account JSON file path
    3. Application Default Credentials (ADC)
    4. Service Account Impersonation
    5. Custom API endpoint (e.g. for local GCS emulator / testbench)
    """
    if not HAS_GCP_STORAGE:
        raise StorageException(
            "google-cloud-storage and google-auth are required. Install with: pip install google-cloud-storage google-auth",
            category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
            provider="gcp_storage"
        )

    project_id = config.get("project_id")
    auth_mode = config.get("auth_mode", "service_account_json").lower()
    sa_json = config.get("service_account_json")
    sa_path = config.get("service_account_path")
    impersonate_sa = config.get("impersonate_service_account")
    custom_endpoint = config.get("custom_endpoint") or config.get("api_endpoint")

    credentials = None

    try:
        # 1. Inline Service Account JSON
        if sa_json:
            if isinstance(sa_json, str):
                try:
                    info = json.loads(sa_json)
                except Exception as e:
                    raise StorageException(
                        f"Invalid service_account_json: {str(e)}",
                        category=StorageErrorCategory.AUTHENTICATION_FAILED,
                        provider="gcp_storage"
                    )
            elif isinstance(sa_json, dict):
                info = sa_json
            else:
                raise StorageException(
                    "service_account_json must be a JSON string or dict.",
                    category=StorageErrorCategory.AUTHENTICATION_FAILED,
                    provider="gcp_storage"
                )

            project_id = project_id or info.get("project_id")
            credentials = service_account.Credentials.from_service_account_info(info)

        # 2. Service Account Key File Path
        elif sa_path:
            credentials = service_account.Credentials.from_service_account_file(sa_path)
            if hasattr(credentials, "project_id") and credentials.project_id:
                project_id = project_id or credentials.project_id

        # 3. Application Default Credentials (ADC) or Environment
        elif auth_mode in ("adc", "workload_identity", "default"):
            credentials, default_project = google.auth.default()
            project_id = project_id or default_project

        # 4. Service Account Impersonation (if target SA specified)
        if credentials and impersonate_sa:
            credentials = ImpersonatedCredentials(
                source_credentials=credentials,
                target_principal=impersonate_sa,
                target_scopes=["https://www.googleapis.com/auth/devstorage.full_control"],
                lifetime=3600
            )

        client_kwargs = {}
        if project_id:
            client_kwargs["project"] = project_id
        if credentials:
            client_kwargs["credentials"] = credentials
        if custom_endpoint:
            client_kwargs["client_options"] = {"api_endpoint": custom_endpoint.rstrip("/")}

        return storage.Client(**client_kwargs)

    except GoogleAPICallError as e:
        raise StorageException(
            f"Failed to authenticate GCP client: {str(e)}",
            category=StorageErrorCategory.AUTHENTICATION_FAILED,
            provider="gcp_storage",
            original_exception=e
        )
    except Exception as e:
        if isinstance(e, StorageException):
            raise e
        raise StorageException(
            f"Error initializing GCP Cloud Storage client: {str(e)}",
            category=StorageErrorCategory.UNKNOWN,
            provider="gcp_storage",
            original_exception=e
        )
