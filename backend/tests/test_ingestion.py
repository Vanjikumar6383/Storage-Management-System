import pytest
from datetime import datetime, timezone
from app.db.database import SessionLocal
from app.models import Organization, StorageConnection, StorageLocation, StorageObject
from app.connectors.base import NormalizedStorageLocation, NormalizedObjectMetadata
from app.services.ingestion import MetadataIngestionService


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_ingest_location_and_objects_idempotency(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = db_session.query(StorageConnection).filter_by(organization_id=demo_org.id).first()

    service = MetadataIngestionService()
    norm_loc = NormalizedStorageLocation(name="test-ingest-bucket", region="us-west-2")

    # Ingest location
    db_loc = service.ingest_location(db_session, demo_org.id, conn.id, norm_loc)
    assert db_loc.name == "test-ingest-bucket"

    now = datetime.now(timezone.utc)
    norm_objs = [
        NormalizedObjectMetadata(
            external_object_id="s3://test-ingest-bucket/obj1.bin",
            storage_location="test-ingest-bucket",
            object_key="obj1.bin",
            object_size_bytes=100,
            storage_class="STANDARD",
            last_modified_at=now,
        ),
        NormalizedObjectMetadata(
            external_object_id="s3://test-ingest-bucket/obj2.bin",
            storage_location="test-ingest-bucket",
            object_key="obj2.bin",
            object_size_bytes=200,
            storage_class="STANDARD",
            last_modified_at=now,
        ),
    ]

    # Initial ingestion -> 2 created
    stats1 = service.ingest_objects(db_session, demo_org.id, db_loc.id, norm_objs)
    assert stats1["created"] == 2
    assert stats1["updated"] == 0
    assert stats1["skipped"] == 0

    # Repeat ingestion (unmodified) -> 2 skipped, 0 created
    stats2 = service.ingest_objects(db_session, demo_org.id, db_loc.id, norm_objs)
    assert stats2["created"] == 0
    assert stats2["updated"] == 0
    assert stats2["skipped"] == 2

    # Modify metadata for obj1 -> 1 updated, 1 skipped
    norm_objs[0].object_size_bytes = 150
    stats3 = service.ingest_objects(db_session, demo_org.id, db_loc.id, norm_objs)
    assert stats3["updated"] == 1
    assert stats3["skipped"] == 1

    # Cleanup
    db_session.delete(db_loc)
    db_session.commit()
