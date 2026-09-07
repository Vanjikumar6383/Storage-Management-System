import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Numeric, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class StoragePricingCatalog(Base):
    __tablename__ = "storage_pricing_catalog"
    __table_args__ = (
        Index("idx_pricing_lookup", "provider", "storage_class", "region", "pricing_version", unique=True),
        Index("idx_pricing_active", "provider", "active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False, default="LOCAL_S3")
    storage_class = Column(String(100), nullable=False)
    region = Column(String(50), nullable=False, default="us-east-1")
    price_per_gb_month = Column(Numeric(12, 6), nullable=False)
    retrieval_price_per_gb = Column(Numeric(12, 6), nullable=False, default=0.000000)
    minimum_storage_days = Column(Integer, nullable=False, default=0)
    transition_price_per_gb = Column(Numeric(12, 6), nullable=False, default=0.000000)
    currency = Column(String(10), nullable=False, default="USD")
    effective_from = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    effective_until = Column(DateTime(timezone=True), nullable=True)
    pricing_version = Column(String(50), nullable=False, default="2026-v1")
    active = Column(Boolean, nullable=False, default=True)


class SavingsLedger(Base):
    __tablename__ = "savings_ledger"
    __table_args__ = (
        Index("idx_savings_org_date", "organization_id", "realized_at"),
        Index("idx_savings_migration", "migration_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    object_id = Column(UUID(as_uuid=True), ForeignKey("storage_objects.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id = Column(UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True)
    migration_id = Column(UUID(as_uuid=True), ForeignKey("migration_events.id", ondelete="SET NULL"), nullable=True)
    source_storage_class = Column(String(100), nullable=False)
    destination_storage_class = Column(String(100), nullable=False)
    object_size_bytes = Column(BigInteger, nullable=False)
    previous_monthly_cost = Column(Numeric(12, 4), nullable=False)
    new_monthly_cost = Column(Numeric(12, 4), nullable=False)
    monthly_savings = Column(Numeric(12, 4), nullable=False)
    annualized_savings = Column(Numeric(12, 4), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    pricing_version = Column(String(50), nullable=False, default="2026-v1")
    realized_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), nullable=False, default="REALIZED")  # REALIZED | ROLLED_BACK
