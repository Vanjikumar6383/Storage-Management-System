"""
Metadata Ingestion Service responsible for idempotent database updates.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Dict

from sqlalchemy.orm import Session
from app.connectors.base import NormalizedStorageLocation, NormalizedObjectMetadata
from app.models import StorageLocation, StorageObject

logger = logging.getLogger("storage.service.ingestion")


class MetadataIngestionService:
    """Service for synchronizing normalized external storage metadata into PostgreSQL."""

    def ingest_location(
        self,
        db: Session,
        organization_id: UUID,
        connection_id: UUID,
        norm_location: NormalizedStorageLocation,
    ) -> StorageLocation:
        """Upsert a storage location record idempotently."""
        loc = (
            db.query(StorageLocation)
            .filter_by(storage_connection_id=connection_id, name=norm_location.name)
            .first()
        )
        if not loc:
            loc = StorageLocation(
                organization_id=organization_id,
                storage_connection_id=connection_id,
                name=norm_location.name,
                region=norm_location.region or "default",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(loc)
            db.commit()
            db.refresh(loc)
            logger.info(f"Created storage location: '{loc.name}' (ID: {loc.id}).")
        else:
            if norm_location.region and loc.region != norm_location.region:
                loc.region = norm_location.region
                loc.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(loc)
        return loc

    def ingest_objects(
        self,
        db: Session,
        organization_id: UUID,
        storage_location_id: UUID,
        norm_objects: List[NormalizedObjectMetadata],
    ) -> Dict[str, int]:
        """
        Upsert a batch of normalized object metadata idempotently into storage_objects.
        Returns dictionary counting created, updated, skipped, and failed records.
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        now = datetime.now(timezone.utc)

        for meta in norm_objects:
            try:
                existing_obj = (
                    db.query(StorageObject)
                    .filter_by(
                        storage_location_id=storage_location_id,
                        object_key=meta.object_key,
                    )
                    .first()
                )

                if not existing_obj:
                    # Insert new object record
                    new_obj = StorageObject(
                        organization_id=organization_id,
                        storage_location_id=storage_location_id,
                        object_key=meta.object_key,
                        object_size_bytes=meta.object_size_bytes,
                        storage_class=meta.storage_class,
                        current_state="ACTIVE",
                        created_at=meta.last_modified_at or now,
                        last_modified_at=meta.last_modified_at or now,
                        discovered_at=now,
                        updated_at=now,
                    )
                    db.add(new_obj)
                    db.commit()
                    stats["created"] += 1
                else:
                    # Check if metadata changed
                    changed = False
                    if existing_obj.object_size_bytes != meta.object_size_bytes:
                        existing_obj.object_size_bytes = meta.object_size_bytes
                        changed = True
                    if existing_obj.storage_class != meta.storage_class:
                        existing_obj.storage_class = meta.storage_class
                        changed = True
                    if existing_obj.last_modified_at != meta.last_modified_at:
                        existing_obj.last_modified_at = meta.last_modified_at
                        changed = True

                    if changed:
                        existing_obj.updated_at = now
                        db.commit()
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to ingest object '{meta.object_key}': {e}")
                stats["failed"] += 1

        return stats
