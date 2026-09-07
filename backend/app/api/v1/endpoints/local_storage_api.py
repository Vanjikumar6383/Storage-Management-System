"""
Local Storage Linking Endpoints.
Enables organizations to link local storage directories to the platform.

PRIVACY POLICY:
The scanner reads only filesystem metadata (filename, size, timestamps).
File byte contents are strictly NEVER accessed, read, or transmitted.
"""

from typing import Dict, Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.local_scanner import LocalFolderScannerService
from app.models import StorageConnection, StorageProviderEnum

router = APIRouter(prefix="/organizations/{organization_id}/storage", tags=["Local Storage Linking"])


class LinkLocalStorageRequest(BaseModel):
    local_path: str = Field(
        ...,
        description="Local folder path (e.g. D:/MyStorage, C:/Users/Documents/Archive)",
        min_length=2,
    )
    max_files: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of files to index in this scan",
    )
    run_ml_recommendations: bool = Field(
        default=True,
        description="Automatically run ML lifecycle optimizer on indexed files",
    )


@router.post("/link-local")
def link_local_storage_folder(
    organization_id: UUID,
    payload: LinkLocalStorageRequest,
    db: Session = Depends(get_db),
):
    """
    Scans a local filesystem folder and indexes file metadata (filename, size, created/modified/accessed times).
    
    GUARANTEE:
    - Zero file content reading: actual file contents are never read or stored.
    - Runs the Machine Learning Lifecycle Engine immediately on discovered files.
    """
    scanner = LocalFolderScannerService()
    try:
        result = scanner.scan_and_link(
            db=db,
            organization_id=organization_id,
            local_path=payload.local_path,
            max_files=payload.max_files,
            run_ml_recommendations=payload.run_ml_recommendations,
        )
        return result
    except FileNotFoundError as fnf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(fnf),
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan and link local storage: {str(exc)}",
        )


@router.get("/linked-local")
def list_linked_local_storages(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    """List all currently linked local storage directories for the given organization."""
    connections = (
        db.query(StorageConnection)
        .filter(
            StorageConnection.organization_id == organization_id,
            StorageConnection.provider == StorageProviderEnum.LOCAL_S3_COMPATIBLE,
        )
        .all()
    )

    results = []
    for c in connections:
        locs = [
            {"id": str(loc.id), "name": loc.name, "region": loc.region, "objects_count": len(loc.objects)}
            for loc in c.storage_locations
        ]
        results.append({
            "connection_id": str(c.id),
            "name": c.name,
            "path": c.config.get("path") if isinstance(c.config, dict) else None,
            "privacy_mode": "METADATA_ONLY",
            "registered_at": c.created_at.isoformat(),
            "locations": locs,
        })

    return {"organization_id": str(organization_id), "linked_directories": results}
