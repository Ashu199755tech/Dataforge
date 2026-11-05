import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON, Integer, Boolean, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class LineageNode(Base):
    """
    Represents an entity in the data lineage graph.
    Can be a Dataset, Database Table, Cloud Storage File/Prefix, Pipeline, or DataFlow.
    """
    __tablename__ = "lineage_nodes"
    __table_args__ = (UniqueConstraint("project_id", "qualified_name", name="uq_project_node_qualified_name"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Entity Categorization
    node_type = Column(String(50), nullable=False, index=True)  # Dataset, Table, StorageFile, Pipeline, Activity, DataFlow
    name = Column(String(200), nullable=False)
    qualified_name = Column(String(500), nullable=False, index=True) # e.g., "dataset:cust_orders" or "s3://lake/sales.parquet"
    
    # Storage & Provider Metadata
    provider = Column(String(50), default="generic", nullable=False)  # postgres, mysql, sqlite, azure_blob, azure_adls, aws_s3, gcp_storage
    location_uri = Column(String(1000), nullable=True)               # e.g., "s3://corp-lake/bronze/sales/"
    
    # Optional foreign key references if linking to existing DataForge entities
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="SET NULL"), nullable=True)
    connection_id = Column(String(36), ForeignKey("connections.id", ondelete="SET NULL"), nullable=True)
    
    # Schema Definition (List of column objects: [{"name": "id", "type": "INTEGER"}])
    schema_json = Column(JSON, default=list, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", backref="lineage_nodes")
    dataset = relationship("Dataset", backref="lineage_node")
    pipeline = relationship("Pipeline", backref="lineage_node")
    connection = relationship("Connection", backref="lineage_nodes")

    # Relationships to edges
    outgoing_edges = relationship("LineageEdge", foreign_keys="[LineageEdge.source_node_id]", back_populates="source_node", cascade="all, delete-orphan")
    incoming_edges = relationship("LineageEdge", foreign_keys="[LineageEdge.target_node_id]", back_populates="target_node", cascade="all, delete-orphan")


class LineageEdge(Base):
    """
    Represents directed data movement or dependency between two LineageNodes.
    """
    __tablename__ = "lineage_edges"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    source_node_id = Column(String(36), ForeignKey("lineage_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(String(36), ForeignKey("lineage_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    edge_type = Column(String(50), default="FlowsTo", nullable=False) # FlowsTo, DerivesFrom, Consumes, Produces
    pipeline_id = Column(String(36), ForeignKey("pipelines.id", ondelete="SET NULL"), nullable=True)
    activity_name = Column(String(150), nullable=True)
    
    # Confidence Level
    confidence = Column(String(50), default="exact", nullable=False)  # exact, derived, partial, unknown
    metadata_json = Column(JSON, default=dict, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    source_node = relationship("LineageNode", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node = relationship("LineageNode", foreign_keys=[target_node_id], back_populates="incoming_edges")
    column_mappings = relationship("ColumnLineage", back_populates="edge", cascade="all, delete-orphan")


class ColumnLineage(Base):
    """
    Fine-grained column-level lineage tracing transformation paths between source and target columns.
    """
    __tablename__ = "column_lineage"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    edge_id = Column(String(36), ForeignKey("lineage_edges.id", ondelete="CASCADE"), nullable=False, index=True)
    
    source_column = Column(String(150), nullable=False)
    target_column = Column(String(150), nullable=False)
    
    transformation_type = Column(String(50), default="direct", nullable=False)  # direct, derived, aggregate, passthrough, mask
    expression = Column(Text, nullable=True)                                    # e.g., "UPPER(cust_name)" or "SUM(amount)"
    confidence = Column(String(50), default="exact", nullable=False)           # exact, derived, partial, unknown
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    edge = relationship("LineageEdge", back_populates="column_mappings")
