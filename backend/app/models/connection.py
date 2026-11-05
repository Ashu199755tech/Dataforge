from sqlalchemy import Column, String, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.app.core.database import Base


class Connection(Base):
    __tablename__ = "connections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    connector_type = Column(String(50), nullable=False)  # postgres, mysql, sqlite, etc.
    description = Column(Text, nullable=True)
    config_encrypted = Column(Text, nullable=False)  # Fernet encrypted JSON credentials
    schema_cache = Column(JSON, nullable=True, default=dict)
    status = Column(String(30), default="Unverified", nullable=False)  # Active, Failed, Unverified
    last_tested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    project = relationship("Project", back_populates="connections")
