from typing import Dict, Any
from backend.app.connectors.base import BaseConnector
from backend.app.connectors.postgres import PostgresConnector
from backend.app.connectors.mysql import MySQLConnector
from backend.app.connectors.sqlite import SQLiteConnector
from backend.app.connectors.local_file import LocalFileConnector
from backend.app.connectors.storage.registry import StorageProviderRegistry
from backend.app.connectors.storage.local import LocalStorageConnector


def get_connector(connector_type: str, config: Dict[str, Any]) -> BaseConnector:
    """
    Factory function returning a concrete connector instance.
    Supports relational databases and multi-cloud object storage providers.
    """
    ctype = connector_type.lower()
    if ctype in ("postgres", "postgresql", "pg"):
        return PostgresConnector(config)
    elif ctype in ("mysql", "mariadb"):
        return MySQLConnector(config)
    elif ctype in ("sqlite", "sqlite3"):
        return SQLiteConnector(config)
    elif ctype in ("snowflake", "sf", "snowflake_db"):
        from backend.app.connectors.snowflake import SnowflakeConnector
        return SnowflakeConnector(config)
    elif ctype in ("file", "local_file", "filesystem", "csv", "json"):
        return LocalFileConnector(config)
    elif ctype in ("local_storage",):
        return LocalStorageConnector(config)
    elif ctype in ("azure_blob", "blob", "azure_adls", "adls", "adls_gen2", "aws_s3", "s3", "gcp_storage", "gcs"):
        return StorageProviderRegistry.create_connector(ctype, config)
    else:
        raise ValueError(
            f"Unsupported connector type: '{connector_type}'. "
            f"Supported: postgres, mysql, sqlite, snowflake, local_file, local_storage, azure_blob, azure_adls, aws_s3, gcp_storage"
        )

