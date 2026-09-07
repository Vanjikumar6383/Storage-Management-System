"""
Production Storage Cost, Savings Engine, Snapshot Manager, Counterfactual Experiment Service, and Error Analysis.
Operates with exact Decimal precision and bulk SQL aggregation.
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from uuid import UUID
from datetime import datetime, date, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Organization,
    Environment,
    StorageLocation,
    StorageObject,
    Recommendation,
    ApprovalRequest,
    LegalHold,
    RetentionPolicy,
    StorageCostSnapshot,
)
from app.models.cost import SavingsLedger
from app.services.pricing_provider import PricingProvider
from app.services.savings_ledger import SavingsLedgerService


class CostSummaryService:
    def __init__(self):
        self.pricing = PricingProvider()
        self.ledger_service = SavingsLedgerService()

    def get_organization_cost_summary(
        self,
        db: Session,
        organization_id: UUID,
        provider: str = "LOCAL_S3",
        version: str = "2026-v1",
    ) -> Dict[str, Any]:
        """Calculates multi-tenant cost and savings summary."""
        # Ensure default demo pricing exists
        self.pricing.seed_default_demo_pricing(db, provider, version)

        # 1. Total storage bytes & count
        tot_bytes = (
            db.query(func.coalesce(func.sum(StorageObject.object_size_bytes), 0))
            .filter(StorageObject.organization_id == organization_id)
            .scalar()
        )
        tot_objects = (
            db.query(func.count(StorageObject.id))
            .filter(StorageObject.organization_id == organization_id)
            .scalar()
        )

        # 2. Storage & Cost by class
        class_rows = (
            db.query(
                StorageObject.storage_class,
                func.count(StorageObject.id),
                func.coalesce(func.sum(StorageObject.object_size_bytes), 0),
            )
            .filter(StorageObject.organization_id == organization_id)
            .group_by(StorageObject.storage_class)
            .all()
        )

        current_cost_dec = Decimal("0.0000")
        storage_by_class = []
        cost_by_class = []

        tot_bytes_dec = Decimal(str(tot_bytes))
        for s_class, count, bytes_sum in class_rows:
            size_gb = Decimal(str(bytes_sum)) / Decimal("1073741824")
            rate = self.pricing.get_storage_price(db, provider, s_class, version=version)
            class_cost = round(size_gb * rate, 4)
            current_cost_dec += class_cost

            pct = float(round((Decimal(str(bytes_sum)) / tot_bytes_dec * Decimal("100.0")) if tot_bytes_dec > 0 else Decimal("0.0"), 2))

            storage_by_class.append({
                "storage_class": s_class,
                "object_count": count,
                "size_bytes": bytes_sum,
                "percentage": pct,
            })
            cost_by_class.append({
                "storage_class": s_class,
                "monthly_cost_usd": float(class_cost),
                "price_per_gb_month_usd": float(rate),
            })

        # 3. Cost by Environment
        env_rows = db.query(Environment).filter_by(organization_id=organization_id).all()
        cost_by_environment = []
        for env in env_rows:
            env_bytes = (
                db.query(func.coalesce(func.sum(StorageObject.object_size_bytes), 0))
                .filter(StorageObject.environment_id == env.id)
                .scalar()
            )
            env_gb = Decimal(str(env_bytes)) / Decimal("1073741824")
            env_cost = round(env_gb * self.pricing.get_storage_price(db, provider, "STANDARD", version=version), 4)
            cost_by_environment.append({
                "environment_id": str(env.id),
                "environment_name": env.name,
                "environment_type": env.environment_type,
                "size_bytes": env_bytes,
                "monthly_cost_usd": float(env_cost),
            })

        # 4. Recommendation & Savings Metrics
        recs = db.query(Recommendation).filter(Recommendation.organization_id == organization_id).all()
        potential_sav_dec = Decimal("0.0000")
        approved_sav_dec = Decimal("0.0000")

        for r in recs:
            sav_dec = Decimal(str(r.estimated_savings))
            potential_sav_dec += sav_dec
            if r.status in ("APPROVED", "EXECUTION_PENDING", "EXECUTING"):
                approved_sav_dec += sav_dec

        # 5. Realized savings from Ledger
        ledger_totals = self.ledger_service.get_realized_savings_totals(db, organization_id)
        realized_monthly_usd = ledger_totals["realized_monthly_savings_usd"]
        realized_annual_usd = ledger_totals["realized_annual_savings_usd"]

        return {
            "total_storage_bytes": int(tot_bytes),
            "total_storage_gb": float(round(tot_bytes_dec / Decimal("1073741824"), 4)),
            "total_objects": int(tot_objects),
            "current_monthly_cost_usd": float(round(current_cost_dec, 2)),
            "potential_monthly_savings_usd": float(round(potential_sav_dec, 2)),
            "approved_monthly_savings_usd": float(round(approved_sav_dec, 2)),
            "realized_monthly_savings_usd": float(round(realized_monthly_usd, 2)),
            "potential_annual_savings_usd": float(round(potential_sav_dec * Decimal("12.0"), 2)),
            "realized_annual_savings_usd": float(round(Decimal(str(realized_annual_usd)), 2)),
            "storage_by_class": storage_by_class,
            "cost_by_class": cost_by_class,
            "cost_by_environment": cost_by_environment,
            "pricing_disclaimer": "Demo pricing — not provider billing.",
            "pricing_version": version,
        }


class SnapshotService:
    """Service to record and query daily cost snapshots."""

    def __init__(self):
        self.pricing = PricingProvider()

    def create_daily_snapshots(
        self,
        db: Session,
        snapshot_date: Optional[date] = None,
        provider: str = "LOCAL_S3",
        version: str = "2026-v1",
    ) -> int:
        """Calculates and persists daily storage cost snapshots per location."""
        if not snapshot_date:
            snapshot_date = datetime.now(timezone.utc).date()

        locations = db.query(StorageLocation).all()
        created_count = 0

        for loc in locations:
            class_rows = (
                db.query(
                    StorageObject.storage_class,
                    func.coalesce(func.sum(StorageObject.object_size_bytes), 0),
                )
                .filter(StorageObject.storage_location_id == loc.id)
                .group_by(StorageObject.storage_class)
                .all()
            )

            for s_class, bytes_sum in class_rows:
                # Prevent duplicate snapshot for org + loc + class + date
                existing = (
                    db.query(StorageCostSnapshot)
                    .filter_by(
                        organization_id=loc.organization_id,
                        storage_location_id=loc.id,
                        storage_class=s_class,
                        snapshot_date=snapshot_date,
                    )
                    .first()
                )
                if not existing:
                    size_gb = Decimal(str(bytes_sum)) / Decimal("1073741824")
                    rate = self.pricing.get_storage_price(db, provider, s_class, version=version)
                    est_cost = round(size_gb * rate, 2)

                    snap = StorageCostSnapshot(
                        organization_id=loc.organization_id,
                        storage_location_id=loc.id,
                        storage_class=s_class,
                        storage_bytes=bytes_sum,
                        estimated_cost=est_cost,
                        snapshot_date=snapshot_date,
                    )
                    db.add(snap)
                    created_count += 1
        db.commit()
        return created_count


class ExperimentService:
    """Calculates counterfactual BASELINE vs OPTIMIZED storage cost experiments."""

    def __init__(self):
        self.pricing = PricingProvider()

    def run_counterfactual_experiment(
        self,
        db: Session,
        organization_id: UUID,
        provider: str = "LOCAL_S3",
        version: str = "2026-v1",
    ) -> Dict[str, Any]:
        """Compares baseline vs counterfactual optimized storage costs across all objects."""
        objs = db.query(StorageObject).filter(StorageObject.organization_id == organization_id).all()
        recs = db.query(Recommendation).filter(Recommendation.organization_id == organization_id).all()
        rec_map = {r.object_id: r for r in recs}

        baseline_cost_dec = Decimal("0.0000")
        optimized_cost_dec = Decimal("0.0000")

        objects_eligible = 0
        objects_kept = 0
        objects_archived = 0
        objects_ia = 0
        delete_candidates = 0
        blocked_retention = 0
        blocked_legal = 0
        high_restore_risk = 0
        requires_review = 0

        for o in objs:
            size_gb = Decimal(str(o.object_size_bytes)) / Decimal("1073741824")
            src_rate = self.pricing.get_storage_price(db, provider, o.storage_class, version=version)
            obj_base_cost = round(size_gb * src_rate, 4)
            baseline_cost_dec += obj_base_cost

            rec = rec_map.get(o.id)
            if not rec:
                optimized_cost_dec += obj_base_cost
                objects_kept += 1
                continue

            rec_type = rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type)
            ev = rec.evidence or {}

            if ev.get("legal_hold_active"):
                blocked_legal += 1
            if ev.get("retention_status") == "ACTIVE_RETENTION":
                blocked_retention += 1
            if ev.get("restore_risk_level") == "HIGH":
                high_restore_risk += 1

            if rec_type == "KEEP":
                objects_kept += 1
                optimized_cost_dec += obj_base_cost
            elif rec_type == "HOLD" or rec.status == "BLOCKED":
                optimized_cost_dec += obj_base_cost
            elif rec_type == "MOVE_TO_INFREQUENT_ACCESS":
                objects_eligible += 1
                objects_ia += 1
                target_rate = self.pricing.get_storage_price(db, provider, "INFREQUENT_ACCESS", version=version)
                optimized_cost_dec += round(size_gb * target_rate, 4)
            elif rec_type == "ARCHIVE":
                objects_eligible += 1
                objects_archived += 1
                target_rate = self.pricing.get_storage_price(db, provider, "ARCHIVE", version=version)
                optimized_cost_dec += round(size_gb * target_rate, 4)
            elif rec_type == "DELETE_CANDIDATE":
                objects_eligible += 1
                delete_candidates += 1
                # Delete target cost is $0.00
                optimized_cost_dec += Decimal("0.0000")
            else:
                requires_review += 1
                optimized_cost_dec += obj_base_cost

        estimated_sav_dec = max(baseline_cost_dec - optimized_cost_dec, Decimal("0.0000"))

        sav_pct = None
        if baseline_cost_dec > Decimal("0.0000"):
            sav_pct = float(round((estimated_sav_dec / baseline_cost_dec) * Decimal("100.0"), 2))

        return {
            "organization_id": str(organization_id),
            "total_objects_analyzed": len(objs),
            "baseline_monthly_cost_usd": float(round(baseline_cost_dec, 2)),
            "optimized_monthly_cost_usd": float(round(optimized_cost_dec, 2)),
            "estimated_monthly_savings_usd": float(round(estimated_sav_dec, 2)),
            "estimated_savings_percentage": sav_pct,
            "objects_eligible_for_optimization": objects_eligible,
            "objects_kept": objects_kept,
            "objects_archived": objects_archived,
            "objects_moved_to_infrequent_access": objects_ia,
            "delete_candidates": delete_candidates,
            "blocked_by_retention": blocked_retention,
            "blocked_by_legal_hold": blocked_legal,
            "high_restore_risk_objects": high_restore_risk,
            "recommendations_requiring_review": requires_review,
            "pricing_disclaimer": "Demo pricing — not provider billing.",
        }


class ErrorAnalysisService:
    """Categorizes unexecuted recommendations for error analysis reporting."""

    def classify_unexecuted_recommendations(self, db: Session, organization_id: UUID) -> Dict[str, Any]:
        recs = db.query(Recommendation).filter(Recommendation.organization_id == organization_id).all()
        
        categories = {
            "RETENTION_BLOCK": 0,
            "LEGAL_HOLD": 0,
            "HIGH_RESTORE_RISK": 0,
            "POLICY_CONFLICT": 0,
            "STALE_RECOMMENDATION": 0,
            "APPROVAL_REJECTED": 0,
            "EXECUTION_FAILED": 0,
            "MINIMUM_STORAGE_CONSTRAINT": 0,
            "INSUFFICIENT_DATA": 0,
            "OTHER": 0,
        }

        unexecuted_count = 0
        for r in recs:
            if r.status == "EXECUTED":
                continue

            unexecuted_count += 1
            ev = r.evidence or {}

            if r.status == "REJECTED":
                categories["APPROVAL_REJECTED"] += 1
            elif r.status == "STALE":
                categories["STALE_RECOMMENDATION"] += 1
            elif r.status == "EXECUTION_FAILED":
                categories["EXECUTION_FAILED"] += 1
            elif ev.get("legal_hold_active"):
                categories["LEGAL_HOLD"] += 1
            elif ev.get("retention_status") == "ACTIVE_RETENTION":
                categories["RETENTION_BLOCK"] += 1
            elif ev.get("restore_risk_level") == "HIGH":
                categories["HIGH_RESTORE_RISK"] += 1
            elif ev.get("minimum_duration_warning"):
                categories["MINIMUM_STORAGE_CONSTRAINT"] += 1
            else:
                categories["OTHER"] += 1

        return {
            "total_unexecuted_recommendations": unexecuted_count,
            "category_breakdown": categories,
        }
