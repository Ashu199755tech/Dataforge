from typing import Dict, Any
from backend.app.connectors.base import BaseConnector
from backend.app.connectors.postgres import PostgresConnector
from backend.app.connectors.mysql import MySQLConnector
from backend.app.connectors.sqlite import SQLiteConnector
from backend.app.connectors.local_file import LocalFileConnector


def get_connector(connector_type: str, config: Dict[str, Any]) -> BaseConnector:
    """
    Factory function returning a concrete connector instance.
    """
    ctype = connector_type.lower()
    if ctype in ("postgres", "postgresql", "pg"):
        return PostgresConnector(config)
    elif ctype in ("mysql", "mariadb"):
        return MySQLConnector(config)
    elif ctype in ("sqlite", "sqlite3"):
        return SQLiteConnector(config)
    elif ctype in ("file", "local_file", "filesystem", "csv", "json"):
        return LocalFileConnector(config)
    else:
        raise ValueError(f"Unsupported connector type: '{connector_type}'. Supported: postgres, mysql, sqlite, local_file")
