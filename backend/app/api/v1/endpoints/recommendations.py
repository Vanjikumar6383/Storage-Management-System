"""
Storage Lifecycle Recommendation REST API Endpoints.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import Recommendation
from app.services.recommendation_engine import RecommendationService, RecommendationResult

router = APIRouter(tags=["Recommendation Engine"])


class RecommendationOutSchema(BaseModel):
    id: UUID
    organization_id: UUID
    object_id: UUID
    recommendation_type: str
    current_storage_class: str
    recommended_storage_class: str
    reason: str
    evidence: dict
    estimated_savings: float
    risk_level: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("/objects/{object_id}/recommendation", response_model=RecommendationOutSchema)
def generate_recommendation_for_object(
    object_id: UUID,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Generate or update an explainable storage lifecycle recommendation for a single object.
    Side-effect free on storage.
    """
    service = RecommendationService()
    try:
        rec = service.generate_and_save_recommendation(db, organization_id, object_id)
        return RecommendationOutSchema(
            id=rec.id,
            organization_id=rec.organization_id,
            object_id=rec.object_id,
            recommendation_type=rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type),
            current_storage_class=rec.current_storage_class,
            recommended_storage_class=rec.recommended_storage_class,
            reason=rec.reason,
            evidence=rec.evidence,
            estimated_savings=float(rec.estimated_savings),
            risk_level=rec.risk_level,
            status=rec.status,
            created_at=rec.created_at.isoformat(),
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/objects/{object_id}/recommendation", response_model=RecommendationOutSchema)
def get_recommendation_for_object(
    object_id: UUID,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Fetch latest active recommendation for an object.
    """
    rec = (
        db.query(Recommendation)
        .filter(
            Recommendation.organization_id == organization_id,
            Recommendation.object_id == object_id,
        )
        .order_by(Recommendation.created_at.desc())
        .first()
    )
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No recommendation found for object.")

    return RecommendationOutSchema(
        id=rec.id,
        organization_id=rec.organization_id,
        object_id=rec.object_id,
        recommendation_type=rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type),
        current_storage_class=rec.current_storage_class,
        recommended_storage_class=rec.recommended_storage_class,
        reason=rec.reason,
        evidence=rec.evidence,
        estimated_savings=float(rec.estimated_savings),
        risk_level=rec.risk_level,
        status=rec.status,
        created_at=rec.created_at.isoformat(),
    )


@router.post("/organizations/{organization_id}/recommendations/run", response_model=List[RecommendationOutSchema])
def run_batch_recommendations(
    organization_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Batch generate storage lifecycle recommendations for an organization using efficient aggregation.
    """
    service = RecommendationService()
    recs = service.batch_generate_recommendations(db, organization_id, limit=limit, offset=offset)

    out = []
    for rec in recs:
        out.append(
            RecommendationOutSchema(
                id=rec.id,
                organization_id=rec.organization_id,
                object_id=rec.object_id,
                recommendation_type=rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type),
                current_storage_class=rec.current_storage_class,
                recommended_storage_class=rec.recommended_storage_class,
                reason=rec.reason,
                evidence=rec.evidence,
                estimated_savings=float(rec.estimated_savings),
                risk_level=rec.risk_level,
                status=rec.status,
                created_at=rec.created_at.isoformat(),
            )
        )
    return out
