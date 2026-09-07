"""
Policy Evaluation REST API Endpoint.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.policy_engine import PolicyEngineService, PolicyDecision

router = APIRouter(prefix="/objects", tags=["Policy Engine & Governance"])


class PolicyEvaluationRequestSchema(BaseModel):
    action: str = Field(..., description="Proposed action (KEEP, MOVE_TO_INFREQUENT_ACCESS, ARCHIVE, DELETE)")


@router.post("/{object_id}/policy-evaluation", response_model=PolicyDecision)
def evaluate_policy_for_object(
    object_id: UUID,
    payload: PolicyEvaluationRequestSchema,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Evaluate governance rules (retention policies and legal holds) for a proposed lifecycle action.
    Pure simulation endpoint with no storage side-effects.
    """
    engine = PolicyEngineService()
    try:
        return engine.evaluate_action(
            db=db,
            organization_id=organization_id,
            object_id=object_id,
            proposed_action=payload.action,
            audit=True,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
