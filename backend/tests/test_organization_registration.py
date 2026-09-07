import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.models import Organization

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_register_organization_with_sample_telemetry(db_session):
    unique_suffix = uuid.uuid4().hex[:6]
    payload = {
        "name": f"Acme Robotics {unique_suffix}",
        "slug": f"acme-robotics-{unique_suffix}",
        "admin_email": f"admin-{unique_suffix}@acme-robotics.io",
        "plan": "ENTERPRISE_PRO",
        "provider": "LOCAL_S3_COMPATIBLE",
        "bucket_name": f"acme-data-{unique_suffix}",
        "region": "us-west-2",
        "environment_name": "production",
        "seed_sample_data": True,
    }

    res = client.post("/api/v1/organizations/register", json=payload)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["name"] == payload["name"]
    assert data["slug"] == payload["slug"]
    assert data["plan"] == "ENTERPRISE_PRO"
    assert data["admin_email"] == payload["admin_email"].lower()
    assert "session_token" in data
    assert "environment_id" in data
    assert "location_id" in data

    # Verify organization in DB
    created_org = db_session.query(Organization).filter_by(slug=payload["slug"]).first()
    assert created_org is not None

    # Test login with slug
    login_res = client.post("/api/v1/organizations/login", json={"slug_or_email": payload["slug"]})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert login_data["slug"] == payload["slug"]
    assert login_data["plan"] == "ENTERPRISE_PRO"
    assert login_data["objects_count"] >= 5

    # Test login with admin email
    login_email_res = client.post("/api/v1/organizations/login", json={"slug_or_email": payload["admin_email"]})
    assert login_email_res.status_code == 200
    assert login_email_res.json()["id"] == str(created_org.id)

    # Test service-details endpoint
    service_res = client.get(f"/api/v1/organizations/{created_org.id}/service-details")
    assert service_res.status_code == 200
    svc_data = service_res.json()
    assert svc_data["plan"] == "ENTERPRISE_PRO"
    assert "COMPLIANCE_LOCK_ENFORCEMENT" in svc_data["features_enabled"]
    assert svc_data["objects_count"] >= 5


def test_register_duplicate_slug_conflict():
    unique_suffix = uuid.uuid4().hex[:6]
    payload = {
        "name": f"Duplicate Test Org {unique_suffix}",
        "slug": f"dup-slug-{unique_suffix}",
        "admin_email": f"dup-{unique_suffix}@test.io",
        "plan": "DEVELOPMENT_FREE",
        "seed_sample_data": False,
    }

    res1 = client.post("/api/v1/organizations/register", json=payload)
    assert res1.status_code == 201

    # Attempt duplicate registration with same slug
    res2 = client.post("/api/v1/organizations/register", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"]


def test_login_non_existent_organization():
    res = client.post("/api/v1/organizations/login", json={"slug_or_email": "non-existent-org-slug-xyz"})
    assert res.status_code == 404
