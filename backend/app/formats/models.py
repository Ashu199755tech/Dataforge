from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class DataType(str, Enum):
    """Unified enterprise data types across all storage formats and databases."""
    STRING = "string"
    INTEGER = "integer"
    BIGINT = "bigint"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    DECIMAL = "decimal"
    BINARY = "binary"
    JSON = "json"
    ARRAY = "array"
    MAP = "map"
    UNKNOWN = "unknown"


class ColumnSchema(BaseModel):
    """Metadata specification for a single tabular column."""
    name: str = Field(..., description="Column identifier / field name")
    data_type: str = Field(default=DataType.STRING.value, description="Unified DataForge type")
    nullable: bool = Field(default=True, description="Whether column accepts null values")
    precision: Optional[int] = Field(default=None, description="Numeric precision for decimals")
    scale: Optional[int] = Field(default=None, description="Scale for decimals")
    description: Optional[str] = Field(default=None, description="Column documentation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Format-specific metadata tags")


class SchemaDefinition(BaseModel):
    """Complete schema definition for structured datasets."""
    columns: List[ColumnSchema] = Field(default_factory=list)
    primary_keys: List[str] = Field(default_factory=list)
    record_count: Optional[int] = Field(default=None)

    def column_names(self) -> List[str]:
        return [c.name for c in self.columns]

    def get_column(self, name: str) -> Optional[ColumnSchema]:
        for c in self.columns:
            if c.name.lower() == name.lower():
                return c
        return None


class PreviewResult(BaseModel):
    """Low-memory sample preview result returned to UI/API."""
    columns: List[ColumnSchema]
    rows: List[Dict[str, Any]]
    sample_row_count: int
    format_detected: str
    total_bytes_sampled: int
    truncated: bool = False
