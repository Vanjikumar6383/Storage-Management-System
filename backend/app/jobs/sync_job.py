"""
Background synchronization job for storage connection metadata discovery.
"""

import time
import logging
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session
from app.models import StorageConnection, ConnectionSyncLog
from app.connectors.factory import ConnectorFactory
from app.services.ingestion import MetadataIngestionService

logger = logging.getLogger("storage.sync.job")


def run_connection_sync(
    db: Session,
    connection_id: UUID,
    connector_override: Optional[object] = None,
) -> ConnectionSyncLog:
    """
    Execute background synchronization job for a storage connection.
    Idempotently discovers buckets and object metadata and updates PostgreSQL.
    """
    start_time = time.time()
    now = datetime.now(timezone.utc)

    conn = db.query(StorageConnection).filter_by(id=connection_id).first()
    if not conn:
        raise ValueError(f"Storage connection '{connection_id}' not found.")

    sync_log = ConnectionSyncLog(
        organization_id=conn.organization_id,
        storage_connection_id=conn.id,
        started_at=now,
        status="IN_PROGRESS",
    )
    db.add(sync_log)
    db.commit()
    db.refresh(sync_log)

    logger.info(f"Starting metadata sync for connection '{conn.name}' (ID: {conn.id}).")

    try:
        # Resolve connector via ConnectorFactory
        connector = connector_override
        if not connector:
            connector = ConnectorFactory.get_connector_for_connection(db, conn)

        # Step 1: Validate connection
        if not connector.test_connection():
            raise RuntimeError("Storage endpoint connection test failed. Check credentials and endpoint URL.")

        # Step 2: Discover storage locations (buckets)
        locations = connector.list_storage_locations()
        sync_log.locations_discovered = len(locations)

        ingestion_service = MetadataIngestionService()
        tot_discovered = 0
        tot_created = 0
        tot_updated = 0
        tot_failed = 0

        # Step 3: Discover & ingest objects for each location
        for loc in locations:
            db_loc = ingestion_service.ingest_location(
                db=db,
                organization_id=conn.organization_id,
                connection_id=conn.id,
                norm_location=loc,
            )

            cursor = None
            while True:
                objects, next_cursor = connector.list_objects(loc.name, cursor=cursor)
                tot_discovered += len(objects)

                if objects:
                    stats = ingestion_service.ingest_objects(
                        db=db,
                        organization_id=conn.organization_id,
                        storage_location_id=db_loc.id,
                        norm_objects=objects,
                    )
                    tot_created += stats["created"]
                    tot_updated += stats["updated"]
                    tot_failed += stats["failed"]

                cursor = next_cursor
                if not cursor:
                    break

        elapsed = time.time() - start_time
        sync_log.status = "SUCCESS"
        sync_log.completed_at = datetime.now(timezone.utc)
        sync_log.objects_discovered = tot_discovered
        sync_log.objects_created = tot_created
        sync_log.objects_updated = tot_updated
        sync_log.objects_failed = tot_failed
        sync_log.duration_seconds = round(elapsed, 2)
        db.commit()
        db.refresh(sync_log)

        logger.info(
            f"Sync completed successfully for '{conn.name}'. Discovered: {tot_discovered}, "
            f"Created: {tot_created}, Updated: {tot_updated}, Duration: {sync_log.duration_seconds}s."
        )
        return sync_log

    except Exception as e:
        elapsed = time.time() - start_time
        db.rollback()

        error_msg = str(e)
        sync_log.status = "FAILED"
        sync_log.completed_at = datetime.now(timezone.utc)
        sync_log.error_summary = error_msg
        sync_log.duration_seconds = round(elapsed, 2)
        db.commit()
        db.refresh(sync_log)

        logger.error(f"Sync failed for connection '{conn.name}': {error_msg}")
        return sync_log
