import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class ConnectionSyncLog(Base):
    __tablename__ = "connection_sync_logs"
    __table_args__ = (
        Index("idx_sync_org_conn", "organization_id", "storage_connection_id"),
        Index("idx_sync_org_status", "organization_id", "status"),
        Index("idx_sync_started", "started_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_connection_id = Column(UUID(as_uuid=True), ForeignKey("storage_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="IN_PROGRESS")
    locations_discovered = Column(Integer, nullable=False, default=0)
    objects_discovered = Column(Integer, nullable=False, default=0)
    objects_created = Column(Integer, nullable=False, default=0)
    objects_updated = Column(Integer, nullable=False, default=0)
    objects_failed = Column(Integer, nullable=False, default=0)
    error_summary = Column(Text, nullable=True)
    duration_seconds = Column(Numeric(10, 2), nullable=True)
