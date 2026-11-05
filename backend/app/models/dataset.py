from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Integer, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    connection_id = Column(String(36), ForeignKey("connections.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False, index=True)
    description = Column(Text, nullable=True)
    dataset_type = Column(String(50), nullable=False)  # RelationalTable, RelationalQuery, DelimitedText, Json, Parquet, Avro, Orc, Excel, Binary
    
    # Target location definition:
    # Relational: {"schema": "public", "table": "users", "query": ""}
    # Cloud / Storage: {"bucket": "raw", "path": "orders/2026", "file_name": "orders.parquet"}
    location_config = Column(JSON, nullable=False, default=dict)
    
    # Format settings: delimiter, quote_char, compression, has_header, encoding, sheet_name
    format_settings = Column(JSON, nullable=False, default=dict)
    
    # Parameter definitions: {"date_partition": {"type": "String", "default_value": "2026-11-05"}}
    parameters = Column(JSON, nullable=False, default=dict)
    
    # Schema definition: list of columns [{"name": "col", "type": "VARCHAR", "nullable": True}]
    schema_definition = Column(JSON, nullable=False, default=list)
    current_version = Column(Integer, default=1, nullable=False)
    
    # Schema drift detection metadata
    schema_status = Column(String(30), default="Current", nullable=False)  # Current, DriftDetected, NeedsSync
    last_drift_check_at = Column(DateTime, nullable=True)
    last_drift_summary = Column(JSON, nullable=True, default=dict)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    connection = relationship("Connection", backref="datasets")
    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan", order_by="desc(DatasetVersion.version_number)")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    schema_snapshot = Column(JSON, nullable=False, default=list)
    location_snapshot = Column(JSON, nullable=False, default=dict)
    format_snapshot = Column(JSON, nullable=False, default=dict)
    change_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    dataset = relationship("Dataset", back_populates="versions")
