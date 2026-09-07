import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.database import Base


class AccessEvent(Base):
    __tablename__ = "access_events"
    __table_args__ = (
        Index("idx_access_org_obj", "organization_id", "object_id"),
        Index("idx_access_timestamp", "event_timestamp"),
        Index("idx_access_idempotency", "idempotency_key", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    event_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    source = Column(String(255), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    idempotency_key = Column(String(255), nullable=True)

    object = relationship("StorageObject", back_populates="access_events")


class RestoreEvent(Base):
    __tablename__ = "restore_events"
    __table_args__ = (
        Index("idx_restore_org_obj", "organization_id", "object_id"),
        Index("idx_restore_idempotency", "idempotency_key", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="REQUESTED")
    source_storage_class = Column(String(100), nullable=False)
    target_storage_class = Column(String(100), nullable=False)
    restore_duration_seconds = Column(Integer, nullable=True)
    failure_reason = Column(Text, nullable=True)
    idempotency_key = Column(String(255), nullable=True)

    object = relationship("StorageObject", back_populates="restore_events")


class MigrationEvent(Base):
    __tablename__ = "migration_events"
    __table_args__ = (
        Index("idx_migration_org_obj", "organization_id", "object_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True, index=True)
    source_storage_class = Column(String(100), nullable=False)
    destination_storage_class = Column(String(100), nullable=False)
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="PENDING")
    error_message = Column(Text, nullable=True)
    rollback_status = Column(String(50), nullable=False, default="NONE")

    object = relationship("StorageObject", back_populates="migration_events")
    recommendation = relationship("Recommendation", back_populates="migration_events")
    rollback_events = relationship("RollbackEvent", back_populates="migration", cascade="all, delete-orphan")


class RollbackEvent(Base):
    __tablename__ = "rollback_events"
    __table_args__ = (
        Index("idx_rollback_org_mig", "organization_id", "migration_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    migration_id = Column(UUID(as_uuid=True), ForeignKey("migration_events.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False, default="PENDING")
    error_message = Column(Text, nullable=True)

    migration = relationship("MigrationEvent", back_populates="rollback_events")
