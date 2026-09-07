"""
Provider-Independent Pricing Abstraction & Catalog Management.
Manages pricing records, rate lookups, minimum storage duration checks, and transition fees.
"""

from typing import Optional
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.cost import StoragePricingCatalog

DEFAULT_DEMO_PRICING = {
    "STANDARD": {
        "price_per_gb_month": Decimal("0.023000"),
        "retrieval_price_per_gb": Decimal("0.000000"),
        "minimum_storage_days": 0,
        "transition_price_per_gb": Decimal("0.000000"),
    },
    "INFREQUENT_ACCESS": {
        "price_per_gb_month": Decimal("0.012500"),
        "retrieval_price_per_gb": Decimal("0.010000"),
        "minimum_storage_days": 30,
        "transition_price_per_gb": Decimal("0.000000"),
    },
    "ARCHIVE": {
        "price_per_gb_month": Decimal("0.004000"),
        "retrieval_price_per_gb": Decimal("0.030000"),
        "minimum_storage_days": 90,
        "transition_price_per_gb": Decimal("0.000000"),
    },
}


class PricingProvider:
    """Provider-agnostic pricing service abstraction."""

    def seed_default_demo_pricing(self, db: Session, provider: str = "LOCAL_S3", version: str = "2026-v1"):
        """Seed default demo pricing catalog entries into PostgreSQL if missing."""
        for s_class, rates in DEFAULT_DEMO_PRICING.items():
            existing = (
                db.query(StoragePricingCatalog)
                .filter_by(provider=provider, storage_class=s_class, region="us-east-1", pricing_version=version)
                .first()
            )
            if not existing:
                item = StoragePricingCatalog(
                    provider=provider,
                    storage_class=s_class,
                    region="us-east-1",
                    price_per_gb_month=rates["price_per_gb_month"],
                    retrieval_price_per_gb=rates["retrieval_price_per_gb"],
                    minimum_storage_days=rates["minimum_storage_days"],
                    transition_price_per_gb=rates["transition_price_per_gb"],
                    currency="USD",
                    pricing_version=version,
                    active=True,
                )
                db.add(item)
        db.commit()

    def get_pricing_record(
        self,
        db: Session,
        provider: str = "LOCAL_S3",
        storage_class: str = "STANDARD",
        region: str = "us-east-1",
        version: str = "2026-v1",
    ) -> Optional[StoragePricingCatalog]:
        """Fetch active pricing catalog row."""
        return (
            db.query(StoragePricingCatalog)
            .filter(
                StoragePricingCatalog.provider == provider,
                StoragePricingCatalog.storage_class == storage_class,
                StoragePricingCatalog.region == region,
                StoragePricingCatalog.pricing_version == version,
                StoragePricingCatalog.active == True,
            )
            .first()
        )

    def get_storage_price(
        self,
        db: Session,
        provider: str = "LOCAL_S3",
        storage_class: str = "STANDARD",
        region: str = "us-east-1",
        version: str = "2026-v1",
    ) -> Decimal:
        """Fetch storage rate per GB-month using Decimal precision."""
        rec = self.get_pricing_record(db, provider, storage_class, region, version)
        if rec:
            return Decimal(str(rec.price_per_gb_month))
        # Fallback to default demo assumption
        fallback = DEFAULT_DEMO_PRICING.get(storage_class.upper(), DEFAULT_DEMO_PRICING["STANDARD"])
        return fallback["price_per_gb_month"]

    def get_retrieval_price(
        self,
        db: Session,
        provider: str = "LOCAL_S3",
        storage_class: str = "STANDARD",
        region: str = "us-east-1",
        version: str = "2026-v1",
    ) -> Decimal:
        """Fetch retrieval rate per GB."""
        rec = self.get_pricing_record(db, provider, storage_class, region, version)
        if rec:
            return Decimal(str(rec.retrieval_price_per_gb))
        fallback = DEFAULT_DEMO_PRICING.get(storage_class.upper(), DEFAULT_DEMO_PRICING["STANDARD"])
        return fallback["retrieval_price_per_gb"]

    def get_minimum_storage_duration(
        self,
        db: Session,
        provider: str = "LOCAL_S3",
        storage_class: str = "STANDARD",
        region: str = "us-east-1",
        version: str = "2026-v1",
    ) -> int:
        """Fetch minimum required storage retention days."""
        rec = self.get_pricing_record(db, provider, storage_class, region, version)
        if rec:
            return rec.minimum_storage_days
        fallback = DEFAULT_DEMO_PRICING.get(storage_class.upper(), DEFAULT_DEMO_PRICING["STANDARD"])
        return fallback["minimum_storage_days"]

    def get_transition_cost(
        self,
        db: Session,
        provider: str = "LOCAL_S3",
        source_class: str = "STANDARD",
        target_class: str = "ARCHIVE",
        region: str = "us-east-1",
        version: str = "2026-v1",
    ) -> Decimal:
        """Fetch transition cost per GB."""
        rec = self.get_pricing_record(db, provider, target_class, region, version)
        if rec:
            return Decimal(str(rec.transition_price_per_gb))
        return Decimal("0.000000")
