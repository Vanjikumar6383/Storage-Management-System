import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.database import Base


class RecommendationTypeEnum(str, enum.Enum):
    KEEP = "KEEP"
    MOVE_TO_INFREQUENT_ACCESS = "MOVE_TO_INFREQUENT_ACCESS"
    ARCHIVE = "ARCHIVE"
    DELETE_CANDIDATE = "DELETE_CANDIDATE"
    HOLD = "HOLD"


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("idx_rec_org_status", "organization_id", "status"),
        Index("idx_rec_org_obj", "organization_id", "object_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_type = Column(SQLEnum(RecommendationTypeEnum, name="recommendation_type_enum"), nullable=False)
    current_storage_class = Column(String(100), nullable=False)
    recommended_storage_class = Column(String(100), nullable=False)
    reason = Column(Text, nullable=False)
    evidence = Column(JSONB, nullable=False, default=dict)
    estimated_savings = Column(Numeric(12, 2), nullable=False, default=0.00)
    risk_level = Column(String(50), nullable=False, default="LOW")
    status = Column(String(50), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    object = relationship("StorageObject", back_populates="recommendations")
    approval_requests = relationship("ApprovalRequest", back_populates="recommendation", cascade="all, delete-orphan")
    migration_events = relationship("MigrationEvent", back_populates="recommendation")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("idx_appr_org_status", "organization_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_action = Column(String(50), nullable=False)  # DELETE, MIGRATE, ARCHIVE
    status = Column(String(50), nullable=False, default="PENDING")
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision = Column(String(50), nullable=True)  # APPROVED, REJECTED
    override_reason = Column(Text, nullable=True)

    recommendation = relationship("Recommendation", back_populates="approval_requests")
