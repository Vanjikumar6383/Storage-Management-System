"""
Storage Connection & Metadata Ingestion API Endpoints.
"""

from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import StorageConnection, ConnectionSyncLog
from app.jobs.sync_job import run_connection_sync

router = APIRouter(prefix="/storage-connections", tags=["Storage Connections"])


class SyncResponseSchema(BaseModel):
    sync_id: str
    organization_id: str
    storage_connection_id: str
    status: str
    locations_discovered: int
    objects_discovered: int
    objects_created: int
    objects_updated: int
    objects_failed: int
    duration_seconds: Optional[float] = None
    error_summary: Optional[str] = None


class ConnectionResponseSchema(BaseModel):
    id: str
    organization_id: str
    name: str
    provider: str
    credential_reference: str


@router.get("", response_model=List[ConnectionResponseSchema])
def list_connections(db: Session = Depends(get_db)):
    """List configured storage connections."""
    conns = db.query(StorageConnection).all()
    return [
        ConnectionResponseSchema(
            id=str(c.id),
            organization_id=str(c.organization_id),
            name=c.name,
            provider=c.provider.value if hasattr(c.provider, "value") else str(c.provider),
            credential_reference=c.credential_reference,
        )
        for c in conns
    ]


@router.post("/{connection_id}/sync", response_model=SyncResponseSchema)
def trigger_connection_sync(connection_id: UUID, db: Session = Depends(get_db)):
    """Manually trigger metadata discovery & synchronization for a storage connection."""
    conn = db.query(StorageConnection).filter_by(id=connection_id).first()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage connection '{connection_id}' not found.",
        )

    try:
        sync_log = run_connection_sync(db=db, connection_id=connection_id)
        return SyncResponseSchema(
            sync_id=str(sync_log.id),
            organization_id=str(sync_log.organization_id),
            storage_connection_id=str(sync_log.storage_connection_id),
            status=sync_log.status,
            locations_discovered=sync_log.locations_discovered,
            objects_discovered=sync_log.objects_discovered,
            objects_created=sync_log.objects_created,
            objects_updated=sync_log.objects_updated,
            objects_failed=sync_log.objects_failed,
            duration_seconds=float(sync_log.duration_seconds) if sync_log.duration_seconds else None,
            error_summary=sync_log.error_summary,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync execution failed: {str(e)}",
        )


@router.get("/{connection_id}/sync-status", response_model=SyncResponseSchema)
def get_latest_sync_status(connection_id: UUID, db: Session = Depends(get_db)):
    """Retrieve the latest synchronization status log for a storage connection."""
    conn = db.query(StorageConnection).filter_by(id=connection_id).first()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage connection '{connection_id}' not found.",
        )

    latest_log = (
        db.query(ConnectionSyncLog)
        .filter_by(storage_connection_id=connection_id)
        .order_by(ConnectionSyncLog.started_at.desc())
        .first()
    )

    if not latest_log:
        raise HTTPException(
            status_code=status.HTTP_44_NOT_FOUND,
            detail=f"No sync history found for connection '{connection_id}'.",
        )

    return SyncResponseSchema(
        sync_id=str(latest_log.id),
        organization_id=str(latest_log.organization_id),
        storage_connection_id=str(latest_log.storage_connection_id),
        status=latest_log.status,
        locations_discovered=latest_log.locations_discovered,
        objects_discovered=latest_log.objects_discovered,
        objects_created=latest_log.objects_created,
        objects_updated=latest_log.objects_updated,
        objects_failed=latest_log.objects_failed,
        duration_seconds=float(latest_log.duration_seconds) if latest_log.duration_seconds else None,
        error_summary=latest_log.error_summary,
    )
