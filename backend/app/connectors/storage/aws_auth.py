from typing import Dict, Any, Tuple, Optional
from backend.app.connectors.storage.models import StorageErrorCategory, StorageException

try:
    import boto3
    import botocore
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def create_boto3_s3_client(config: Dict[str, Any]) -> Any:
    """
    Creates and returns a configured boto3 S3 client supporting:
    1. Direct Access Key ID + Secret Access Key
    2. Temporary credentials with Session Token
    3. STS AssumeRole (cross-account or elevated role delegation)
    4. Default AWS Credentials Provider Chain (EC2/ECS IAM roles, env vars)
    5. Custom endpoint URLs for Moto, LocalStack, MinIO, or private AWS endpoints
    """
    if not HAS_BOTO3:
        raise StorageException(
            "boto3 and botocore are required for AWS S3. Install with: pip install boto3 botocore",
            category=StorageErrorCategory.OPERATION_NOT_SUPPORTED,
            provider="aws_s3"
        )

    auth_mode = config.get("auth_mode", "access_key").lower()
    region_name = config.get("region_name") or config.get("region", "us-east-1")
    endpoint_url = config.get("endpoint_url")
    access_key_id = config.get("access_key_id") or config.get("aws_access_key_id")
    secret_access_key = config.get("secret_access_key") or config.get("aws_secret_access_key")
    session_token = config.get("session_token") or config.get("aws_session_token")
    role_arn = config.get("role_arn")
    external_id = config.get("external_id")
    role_session_name = config.get("role_session_name", "DataForgeTransferSession")

    # Client retry and timeout tuning
    boto_cfg = Config(
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=10,
        read_timeout=60
    )

    try:
        # 1. STS AssumeRole Mode
        if auth_mode in ("sts_assume_role", "assume_role") or role_arn:
            if not role_arn:
                raise StorageException(
                    "STS AssumeRole mode requires 'role_arn'.",
                    category=StorageErrorCategory.AUTHENTICATION_FAILED,
                    provider="aws_s3"
                )

            # Base session for STS call
            base_session = boto3.Session(
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                aws_session_token=session_token,
                region_name=region_name
            )
            sts_client = base_session.client("sts", endpoint_url=endpoint_url)

            assume_role_kwargs = {
                "RoleArn": role_arn,
                "RoleSessionName": role_session_name
            }
            if external_id:
                assume_role_kwargs["ExternalId"] = external_id

            assumed = sts_client.assume_role(**assume_role_kwargs)
            credentials = assumed["Credentials"]

            return boto3.client(
                "s3",
                region_name=region_name,
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                endpoint_url=endpoint_url,
                config=boto_cfg
            )

        # 2. Explicit Access Key / Session Token Mode
        if access_key_id and secret_access_key:
            return boto3.client(
                "s3",
                region_name=region_name,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                aws_session_token=session_token,
                endpoint_url=endpoint_url,
                config=boto_cfg
            )

        # 3. Default Chain (IAM Instance Profile / ECS Task Role / Env Vars)
        return boto3.client(
            "s3",
            region_name=region_name,
            endpoint_url=endpoint_url,
            config=boto_cfg
        )

    except ClientError as e:
        err_code = e.response.get("Error", {}).get("Code", "ClientError")
        err_msg = e.response.get("Error", {}).get("Message", str(e))
        cat = StorageErrorCategory.AUTHENTICATION_FAILED if "Auth" in err_code or "AccessDenied" in err_code else StorageErrorCategory.UNKNOWN
        raise StorageException(
            f"Failed to authenticate AWS client: [{err_code}] {err_msg}",
            category=cat,
            provider="aws_s3",
            original_exception=e
        )
    except Exception as e:
        if isinstance(e, StorageException):
            raise e
        raise StorageException(
            f"Error initializing AWS S3 client: {str(e)}",
            category=StorageErrorCategory.UNKNOWN,
            provider="aws_s3",
            original_exception=e
        )
