import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"
    __table_args__ = (
        Index("idx_retention_org_priority", "organization_id", "priority"),
        Index("idx_retention_object", "object_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=True, index=True)
    environment_id = Column(UUID(as_uuid=True), ForeignKey("environments.id", ondelete="CASCADE"), nullable=True, index=True)
    storage_location_id = Column(UUID(as_uuid=True), ForeignKey("storage_locations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    retention_duration_days = Column(Integer, nullable=False)
    effective_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")
    priority = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    object = relationship("StorageObject", foreign_keys=[object_id])


class LegalHold(Base):
    __tablename__ = "legal_holds"
    __table_args__ = (
        Index("idx_legal_hold_org_obj", "organization_id", "object_id"),
        Index("idx_legal_hold_obj_status", "object_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="ACTIVE")
    reason_reference = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)

    object = relationship("StorageObject", back_populates="legal_holds")
