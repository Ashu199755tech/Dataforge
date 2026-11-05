from abc import ABC, abstractmethod
from typing import List, Dict, Any, Iterator, Optional
from pydantic import BaseModel


class ColumnMetadata(BaseModel):
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    default_value: Optional[str] = None


class TableMetadata(BaseModel):
    name: str
    schema_name: Optional[str] = None
    table_type: str = "TABLE"  # TABLE or VIEW
    approx_row_count: Optional[int] = None
    columns: List[ColumnMetadata] = []


class ConnectionTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None
    server_version: Optional[str] = None


class BaseConnector(ABC):
    """
    Standard interface for all DataFlow Enterprise data connectors.
    All database and storage integrations inherit from this class.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """Verifies network connectivity and authentication."""
        pass

    @abstractmethod
    def discover_schemas(self) -> List[str]:
        """Lists available databases or schemas."""
        pass

    @abstractmethod
    def discover_tables(self, schema_name: Optional[str] = None) -> List[TableMetadata]:
        """Discovers tables and views."""
        pass

    @abstractmethod
    def discover_columns(self, table_name: str, schema_name: Optional[str] = None) -> List[ColumnMetadata]:
        """Inspects column definitions for a given table."""
        pass

    @abstractmethod
    def read_data_stream(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filter_expr: Optional[str] = None,
        watermark_column: Optional[str] = None,
        watermark_value: Optional[Any] = None,
        batch_size: int = 5000,
        schema_name: Optional[str] = None
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Streams records in chunks to prevent high memory consumption.
        Yields batches of dicts.
        """
        pass

    @abstractmethod
    def write_data_batch(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        write_mode: str = "append",  # append, overwrite, upsert
        key_columns: Optional[List[str]] = None,
        column_mappings: Optional[List[Dict[str, str]]] = None,
        schema_name: Optional[str] = None,
        auto_create_table: bool = True
    ) -> int:
        """
        Writes a batch of records to the destination table.
        Returns the number of rows successfully written.
        """
        pass

    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executes arbitrary SQL and returns rows as dicts."""
        pass
