"""
Telemetry & Usage Profile REST API Endpoints.
"""

from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.telemetry import (
    AccessEventIngestionService,
    RestoreEventService,
    ObjectUsageProfileService,
    ObjectUsageProfile,
)

router = APIRouter(prefix="/objects", tags=["Telemetry & Object Usage"])


class AccessEventCreateSchema(BaseModel):
    event_type: str = Field(..., description="Type of event (OBJECT_READ, OBJECT_RESTORED, OBJECT_METADATA_READ, etc.)")
    event_timestamp: Optional[datetime] = Field(None, description="Event occurrence timestamp")
    source: Optional[str] = Field(None, description="System source or connector identifier")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata key-value attributes")
    idempotency_key: Optional[str] = Field(None, description="Unique client idempotency token")


class AccessEventResponseSchema(BaseModel):
    id: str
    organization_id: str
    object_id: str
    event_type: str
    event_timestamp: datetime
    source: Optional[str] = None
    idempotency_key: Optional[str] = None


class RestoreEventCreateSchema(BaseModel):
    source_storage_class: str = Field(..., description="Source storage tier (e.g. GLACIER)")
    target_storage_class: str = Field(..., description="Destination storage tier (e.g. STANDARD)")
    requested_at: Optional[datetime] = Field(None, description="Restore request timestamp")
    completed_at: Optional[datetime] = Field(None, description="Restore completion timestamp")
    status: str = Field(default="REQUESTED", description="Restore status (REQUESTED, IN_PROGRESS, SUCCEEDED, FAILED, CANCELLED)")
    restore_duration_seconds: Optional[int] = Field(None, description="Total duration of restore process in seconds")
    failure_reason: Optional[str] = Field(None, description="Error reason if restore failed")
    idempotency_key: Optional[str] = Field(None, description="Unique client idempotency token")


class RestoreEventResponseSchema(BaseModel):
    id: str
    organization_id: str
    object_id: str
    status: str
    source_storage_class: str
    target_storage_class: str
    requested_at: datetime
    completed_at: Optional[datetime] = None
    restore_duration_seconds: Optional[int] = None
    failure_reason: Optional[str] = None


@router.post("/{object_id}/access-events", response_model=AccessEventResponseSchema, status_code=status.HTTP_201_CREATED)
def record_access_event(
    object_id: UUID,
    payload: AccessEventCreateSchema,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """Record an object access event with tenant scoping and idempotency."""
    service = AccessEventIngestionService()
    try:
        event = service.record_access_event(
            db=db,
            organization_id=organization_id,
            object_id=object_id,
            event_type=payload.event_type,
            event_timestamp=payload.event_timestamp,
            source=payload.source,
            metadata=payload.metadata,
            idempotency_key=payload.idempotency_key,
        )
        return AccessEventResponseSchema(
            id=str(event.id),
            organization_id=str(event.organization_id),
            object_id=str(event.object_id),
            event_type=event.event_type,
            event_timestamp=event.event_timestamp,
            source=event.source,
            idempotency_key=event.idempotency_key,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/{object_id}/restore-events", response_model=RestoreEventResponseSchema, status_code=status.HTTP_201_CREATED)
def record_restore_event(
    object_id: UUID,
    payload: RestoreEventCreateSchema,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """Record an object restore event with tenant scoping."""
    service = RestoreEventService()
    try:
        event = service.record_restore_event(
            db=db,
            organization_id=organization_id,
            object_id=object_id,
            source_storage_class=payload.source_storage_class,
            target_storage_class=payload.target_storage_class,
            requested_at=payload.requested_at,
            completed_at=payload.completed_at,
            status=payload.status,
            restore_duration_seconds=payload.restore_duration_seconds,
            failure_reason=payload.failure_reason,
            idempotency_key=payload.idempotency_key,
        )
        return RestoreEventResponseSchema(
            id=str(event.id),
            organization_id=str(event.organization_id),
            object_id=str(event.object_id),
            status=event.status,
            source_storage_class=event.source_storage_class,
            target_storage_class=event.target_storage_class,
            requested_at=event.requested_at,
            completed_at=event.completed_at,
            restore_duration_seconds=event.restore_duration_seconds,
            failure_reason=event.failure_reason,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get("/{object_id}/usage-profile", response_model=ObjectUsageProfile)
def get_object_usage_profile(
    object_id: UUID,
    organization_id: UUID = Query(..., description="Tenant organization context ID"),
    db: Session = Depends(get_db),
):
    """Calculate and return the telemetry evidence usage profile for a storage object."""
    service = ObjectUsageProfileService()
    try:
        return service.build_usage_profile(db=db, organization_id=organization_id, object_id=object_id)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
