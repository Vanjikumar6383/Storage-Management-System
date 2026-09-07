import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Integer, DateTime, Text, ForeignKey, Enum as SQLEnum, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.database import Base


class StorageProviderEnum(str, enum.Enum):
    AWS_S3 = "AWS_S3"
    AZURE_BLOB = "AZURE_BLOB"
    GOOGLE_CLOUD_STORAGE = "GOOGLE_CLOUD_STORAGE"
    LOCAL_S3_COMPATIBLE = "LOCAL_S3_COMPATIBLE"


class StorageConnection(Base):
    __tablename__ = "storage_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    provider = Column(SQLEnum(StorageProviderEnum, name="storage_provider_enum"), nullable=False)
    credential_reference = Column(String(255), nullable=False)
    config = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    organization = relationship("Organization", back_populates="storage_connections")
    environments = relationship("Environment", back_populates="storage_connection", cascade="all, delete-orphan")
    storage_locations = relationship("StorageLocation", back_populates="storage_connection", cascade="all, delete-orphan")


class Environment(Base):
    __tablename__ = "environments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_connection_id = Column(UUID(as_uuid=True), ForeignKey("storage_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    environment_type = Column(String(50), nullable=True, default="DEVELOPMENT")
    expected_lifetime_days = Column(Integer, nullable=True, default=90)
    status = Column(String(50), nullable=False, default="ACTIVE")
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    organization = relationship("Organization", back_populates="environments")
    storage_connection = relationship("StorageConnection", back_populates="environments")
    objects = relationship("StorageObject", back_populates="environment")


class StorageLocation(Base):
    __tablename__ = "storage_locations"
    __table_args__ = (
        UniqueConstraint("storage_connection_id", "name", name="uq_location_conn_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_connection_id = Column(UUID(as_uuid=True), ForeignKey("storage_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    region = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    organization = relationship("Organization", back_populates="storage_locations")
    storage_connection = relationship("StorageConnection", back_populates="storage_locations")
    objects = relationship("StorageObject", back_populates="storage_location", cascade="all, delete-orphan")


class StorageObject(Base):
    __tablename__ = "storage_objects"
    __table_args__ = (
        UniqueConstraint("storage_location_id", "object_key", name="uq_object_location_key"),
        Index("idx_obj_org_env", "organization_id", "environment_id"),
        Index("idx_obj_org_loc", "organization_id", "storage_location_id"),
        Index("idx_obj_org_accessed", "organization_id", "last_accessed_at"),
        Index("idx_obj_org_class", "organization_id", "storage_class"),
        Index("idx_obj_org_state", "organization_id", "current_state"),
        Index("idx_obj_partition", "dataset_partition"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_location_id = Column(UUID(as_uuid=True), ForeignKey("storage_locations.id", ondelete="CASCADE"), nullable=False, index=True)
    environment_id = Column(UUID(as_uuid=True), ForeignKey("environments.id", ondelete="SET NULL"), nullable=True, index=True)
    object_key = Column(String(1024), nullable=False)
    object_size_bytes = Column(BigInteger, nullable=False, default=0)
    object_type = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    storage_class = Column(String(100), nullable=False, default="STANDARD")
    current_state = Column(String(50), nullable=False, default="ACTIVE")
    dataset_partition = Column(String(50), nullable=True, default="DEVELOPMENT")
    scenario_tag = Column(String(50), nullable=True)
    ground_truth_action = Column(String(50), nullable=True)
    ground_truth_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    last_modified_at = Column(DateTime(timezone=True), nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    access_count_30d = Column(Integer, nullable=False, default=0)
    access_count_90d = Column(Integer, nullable=False, default=0)
    version_count = Column(Integer, nullable=False, default=1)
    discovered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    storage_location = relationship("StorageLocation", back_populates="objects")
    environment = relationship("Environment", back_populates="objects")
    access_events = relationship("AccessEvent", back_populates="object", cascade="all, delete-orphan")
    restore_events = relationship("RestoreEvent", back_populates="object", cascade="all, delete-orphan")
    legal_holds = relationship("LegalHold", back_populates="object", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="object", cascade="all, delete-orphan")
    migration_events = relationship("MigrationEvent", back_populates="object", cascade="all, delete-orphan")
