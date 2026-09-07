import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Numeric, Date, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_org_timestamp", "organization_id", "timestamp"),
        Index("idx_audit_org_resource", "organization_id", "resource_type", "resource_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    outcome = Column(String(50), nullable=False, default="SUCCESS")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


class StorageCostSnapshot(Base):
    __tablename__ = "storage_cost_snapshots"
    __table_args__ = (
        Index("idx_cost_org_date", "organization_id", "snapshot_date"),
        Index("idx_cost_org_loc", "organization_id", "storage_location_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_location_id = Column(UUID(as_uuid=True), ForeignKey("storage_locations.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_class = Column(String(100), nullable=False)
    storage_bytes = Column(BigInteger, nullable=False, default=0)
    estimated_cost = Column(Numeric(12, 2), nullable=False, default=0.00)
    snapshot_date = Column(Date, nullable=False)
