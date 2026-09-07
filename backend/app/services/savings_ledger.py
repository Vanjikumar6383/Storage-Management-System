"""
Savings Ledger Service.
Tracks realized savings entries and rollback reversals using exact Decimal precision.
"""

from typing import Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.cost import SavingsLedger, StoragePricingCatalog
from app.services.pricing_provider import PricingProvider


class SavingsLedgerService:
    def __init__(self):
        self.pricing_provider = PricingProvider()

    def record_realized_savings(
        self,
        db: Session,
        organization_id: UUID,
        object_id: UUID,
        source_storage_class: str,
        destination_storage_class: str,
        object_size_bytes: int,
        migration_id: Optional[UUID] = None,
        recommendation_id: Optional[UUID] = None,
        provider: str = "LOCAL_S3",
        version: str = "2026-v1",
    ) -> SavingsLedger:
        """Create a realized savings record in the ledger."""
        size_gb = Decimal(str(object_size_bytes)) / Decimal("1073741824")  # 1024^3

        src_rate = self.pricing_provider.get_storage_price(db, provider, source_storage_class, version=version)
        dst_rate = self.pricing_provider.get_storage_price(db, provider, destination_storage_class, version=version)

        prev_cost = round(size_gb * src_rate, 4)
        new_cost = round(size_gb * dst_rate, 4)
        monthly_sav = max(prev_cost - new_cost, Decimal("0.0000"))
        annual_sav = monthly_sav * Decimal("12.0000")

        entry = SavingsLedger(
            organization_id=organization_id,
            object_id=object_id,
            recommendation_id=recommendation_id,
            migration_id=migration_id,
            source_storage_class=source_storage_class,
            destination_storage_class=destination_storage_class,
            object_size_bytes=object_size_bytes,
            previous_monthly_cost=prev_cost,
            new_monthly_cost=new_cost,
            monthly_savings=monthly_sav,
            annualized_savings=annual_sav,
            currency="USD",
            pricing_version=version,
            realized_at=datetime.now(timezone.utc),
            status="REALIZED",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def record_rollback_reversal(self, db: Session, migration_id: UUID) -> Optional[SavingsLedger]:
        """Mark an existing realized savings ledger entry as ROLLED_BACK."""
        entry = db.query(SavingsLedger).filter_by(migration_id=migration_id, status="REALIZED").first()
        if entry:
            entry.status = "ROLLED_BACK"
            db.commit()
            db.refresh(entry)
        return entry

    def get_realized_savings_totals(self, db: Session, organization_id: UUID) -> dict:
        """Calculate total active realized monthly and annual savings."""
        row = (
            db.query(
                func.coalesce(func.sum(SavingsLedger.monthly_savings), 0.0),
                func.coalesce(func.sum(SavingsLedger.annualized_savings), 0.0),
            )
            .filter(SavingsLedger.organization_id == organization_id, SavingsLedger.status == "REALIZED")
            .first()
        )
        return {
            "realized_monthly_savings_usd": float(row[0]) if row else 0.0,
            "realized_annual_savings_usd": float(row[1]) if row else 0.0,
        }
