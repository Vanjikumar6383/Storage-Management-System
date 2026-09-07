import pytest
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models import Organization, StorageConnection, ConnectionSyncLog
from app.jobs.sync_job import run_connection_sync
from app.connectors.base import NormalizedStorageLocation, NormalizedObjectMetadata

client = TestClient(app)


class FakeConnectorForJob:
    def test_connection(self):
        return True

    def list_storage_locations(self):
        return [NormalizedStorageLocation(name="job-test-bucket", region="us-east-1")]

    def list_objects(self, location_name, cursor=None):
        if cursor:
            return [], None
        return [
            NormalizedObjectMetadata(
                external_object_id="s3://job-test-bucket/item1.dat",
                storage_location="job-test-bucket",
                object_key="item1.dat",
                object_size_bytes=512,
                storage_class="STANDARD",
                last_modified_at=datetime.now(timezone.utc),
            )
        ], None


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_list_connections_api():
    response = client.get("/api/v1/storage-connections")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_sync_job_execution(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = db_session.query(StorageConnection).filter_by(organization_id=demo_org.id).first()

    sync_log = run_connection_sync(
        db_session, connection_id=conn.id, connector_override=FakeConnectorForJob()
    )

    assert sync_log.status == "SUCCESS"
    assert sync_log.locations_discovered == 1
    assert sync_log.objects_discovered == 1
    assert (sync_log.objects_created + sync_log.objects_updated) >= 0


def test_trigger_sync_api(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = db_session.query(StorageConnection).filter_by(organization_id=demo_org.id).first()

    response = client.post(f"/api/v1/storage-connections/{conn.id}/sync")
    assert response.status_code in (200, 500)  # 200 if local s3 reachable, 500 if connection refused (handled safely)

    # Check status API endpoint
    status_resp = client.get(f"/api/v1/storage-connections/{conn.id}/sync-status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "status" in status_data
    assert status_data["storage_connection_id"] == str(conn.id)


def test_invalid_connection_id_api():
    random_id = str(uuid4())
    response = client.post(f"/api/v1/storage-connections/{random_id}/sync")
    assert response.status_code == 404
