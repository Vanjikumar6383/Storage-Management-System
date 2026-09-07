"""
Approval, Execution, and Rollback REST API Endpoints.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.approval_execution import (
    ApprovalExecutionService,
    ApprovalDecisionRequest,
    ExecutionResult,
    RollbackResult,
)

router = APIRouter(tags=["Approval & Lifecycle Execution Engine"])


class ApprovalOutSchema(BaseModel):
    id: UUID
    organization_id: UUID
    recommendation_id: UUID
    requested_action: str
    status: str
    decision: Optional[str] = None
    override_reason: Optional[str] = None
    requested_at: str
    decided_at: Optional[str] = None

    class Config:
        from_attributes = True


class RollbackReqSchema(BaseModel):
    reason: str = Field("Operator requested rollback", description="Reason for executing rollback")


@router.post("/recommendations/{recommendation_id}/approval", response_model=ApprovalOutSchema)
def submit_approval_decision(
    recommendation_id: UUID,
    payload: ApprovalDecisionRequest,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Submit human approval or rejection for a recommendation.
    """
    service = ApprovalExecutionService()
    try:
        appr = service.process_approval_decision(
            db=db,
            organization_id=organization_id,
            recommendation_id=recommendation_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        return ApprovalOutSchema(
            id=appr.id,
            organization_id=appr.organization_id,
            recommendation_id=appr.recommendation_id,
            requested_action=appr.requested_action,
            status=appr.status,
            decision=appr.decision,
            override_reason=appr.override_reason,
            requested_at=appr.requested_at.isoformat(),
            decided_at=appr.decided_at.isoformat() if appr.decided_at else None,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get("/recommendations/{recommendation_id}/approval", response_model=ApprovalOutSchema)
def get_approval_status(
    recommendation_id: UUID,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Fetch approval status for a recommendation.
    """
    service = ApprovalExecutionService()
    try:
        appr = service.create_or_get_approval_request(db, organization_id, recommendation_id)
        return ApprovalOutSchema(
            id=appr.id,
            organization_id=appr.organization_id,
            recommendation_id=appr.recommendation_id,
            requested_action=appr.requested_action,
            status=appr.status,
            decision=appr.decision,
            override_reason=appr.override_reason,
            requested_at=appr.requested_at.isoformat(),
            decided_at=appr.decided_at.isoformat() if appr.decided_at else None,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/recommendations/{recommendation_id}/execute", response_model=ExecutionResult)
def execute_approved_recommendation(
    recommendation_id: UUID,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Execute an approved lifecycle recommendation.
    Verifies human approval and runs pre-execution safety gate.
    """
    service = ApprovalExecutionService()
    try:
        return service.execute_recommendation(db=db, organization_id=organization_id, recommendation_id=recommendation_id)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post("/migrations/{migration_id}/rollback", response_model=RollbackResult)
def rollback_completed_migration(
    migration_id: UUID,
    payload: RollbackReqSchema,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """
    Roll back a completed migration event to its original storage class.
    """
    service = ApprovalExecutionService()
    try:
        return service.rollback_migration(db=db, organization_id=organization_id, migration_id=migration_id, reason=payload.reason)
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
