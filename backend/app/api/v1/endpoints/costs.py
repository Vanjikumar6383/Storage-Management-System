"""
Production Storage Cost & Savings Engine REST API Endpoints.
All endpoints enforce multi-tenant organization isolation.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.cost_engine import (
    CostSummaryService,
    SnapshotService,
    ExperimentService,
    ErrorAnalysisService,
)
from app.models import StorageCostSnapshot
from app.models.cost import SavingsLedger

router = APIRouter(prefix="/costs", tags=["Storage Cost & Savings Engine"])


@router.get("/summary")
def get_cost_summary(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Fetch comprehensive storage cost & savings summary for organization.
    """
    service = CostSummaryService()
    return service.get_organization_cost_summary(db=db, organization_id=organization_id)


@router.get("/by-class")
def get_cost_by_class(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Fetch monthly cost and storage size breakdown by storage class.
    """
    service = CostSummaryService()
    summary = service.get_organization_cost_summary(db=db, organization_id=organization_id)
    return {
        "storage_by_class": summary["storage_by_class"],
        "cost_by_class": summary["cost_by_class"],
        "pricing_disclaimer": summary["pricing_disclaimer"],
    }


@router.get("/by-environment")
def get_cost_by_environment(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Fetch cost breakdown grouped by development environment.
    """
    service = CostSummaryService()
    summary = service.get_organization_cost_summary(db=db, organization_id=organization_id)
    return {
        "cost_by_environment": summary["cost_by_environment"],
        "pricing_disclaimer": summary["pricing_disclaimer"],
    }


@router.get("/history")
def get_cost_history(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Fetch daily historical storage cost snapshot trends.
    """
    snaps = (
        db.query(StorageCostSnapshot)
        .filter(StorageCostSnapshot.organization_id == organization_id)
        .order_by(StorageCostSnapshot.snapshot_date.desc())
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": str(s.id),
            "storage_location_id": str(s.storage_location_id),
            "storage_class": s.storage_class,
            "storage_bytes": s.storage_bytes,
            "estimated_cost": float(s.estimated_cost),
            "snapshot_date": s.snapshot_date.isoformat(),
        }
        for s in snaps
    ]
    return {"total": len(items), "items": items, "pricing_disclaimer": "Demo pricing — not provider billing."}


@router.get("/savings")
def get_savings_breakdown(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Fetch distinct savings breakdown (ESTIMATED vs APPROVED vs REALIZED).
    """
    service = CostSummaryService()
    summary = service.get_organization_cost_summary(db=db, organization_id=organization_id)
    return {
        "potential_monthly_savings_usd": summary["potential_monthly_savings_usd"],
        "approved_monthly_savings_usd": summary["approved_monthly_savings_usd"],
        "realized_monthly_savings_usd": summary["realized_monthly_savings_usd"],
        "potential_annual_savings_usd": summary["potential_annual_savings_usd"],
        "realized_annual_savings_usd": summary["realized_annual_savings_usd"],
        "pricing_disclaimer": summary["pricing_disclaimer"],
    }


@router.get("/ledger")
def get_savings_ledger(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    Fetch immutable realized savings ledger entries and reversals.
    """
    rows = (
        db.query(SavingsLedger)
        .filter(SavingsLedger.organization_id == organization_id)
        .order_by(SavingsLedger.realized_at.desc())
        .limit(limit)
        .all()
    )

    items = [
        {
            "id": str(r.id),
            "object_id": str(r.object_id),
            "migration_id": str(r.migration_id) if r.migration_id else None,
            "recommendation_id": str(r.recommendation_id) if r.recommendation_id else None,
            "source_storage_class": r.source_storage_class,
            "destination_storage_class": r.destination_storage_class,
            "object_size_bytes": r.object_size_bytes,
            "previous_monthly_cost_usd": float(r.previous_monthly_cost),
            "new_monthly_cost_usd": float(r.new_monthly_cost),
            "monthly_savings_usd": float(r.monthly_savings),
            "annualized_savings_usd": float(r.annualized_savings),
            "currency": r.currency,
            "pricing_version": r.pricing_version,
            "realized_at": r.realized_at.isoformat(),
            "status": r.status,
        }
        for r in rows
    ]
    return {"total": len(items), "items": items}


@router.get("/experiment")
def run_cost_experiment(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Executes counterfactual BASELINE vs OPTIMIZED cost experiment across all tenant objects.
    """
    service = ExperimentService()
    return service.run_counterfactual_experiment(db=db, organization_id=organization_id)


@router.get("/error-analysis")
def get_error_analysis(
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Classifies unexecuted recommendations into error analysis categories.
    """
    service = ErrorAnalysisService()
    return service.classify_unexecuted_recommendations(db=db, organization_id=organization_id)
