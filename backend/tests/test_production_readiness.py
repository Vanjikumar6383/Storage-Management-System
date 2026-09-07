"""
Production Readiness, Observability, Middleware & Safety Regression Test Suite.
Verifies liveness, readiness, request correlation IDs, security headers, standardized error formatting, and delete simulation safety.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from app.models import Organization, StorageLocation, StorageObject, Recommendation, RecommendationTypeEnum
from app.services.approval_execution import ApprovalExecutionService

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_liveness_endpoint():
    """TEST 1: Verify liveness endpoint returns 200 OK and HEALTHY status."""
    response = client.get("/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"


def test_readiness_endpoint():
    """TEST 2: Verify readiness endpoint checks DB connectivity and storage configuration."""
    response = client.get("/health/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["database_status"] == "HEALTHY"
    assert data["storage_status"] in ("HEALTHY", "DEGRADED")


def test_system_info_endpoint():
    """TEST 3: Verify /info endpoint returns application metadata."""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "environment" in data
    assert data["delete_safety_mode"] == "SIMULATION_ONLY"


def test_request_id_header_propagation():
    """TEST 4: Verify X-Request-ID header is generated or propagated on response."""
    custom_req_id = "req-test-correlation-999"
    response = client.get("/info", headers={"X-Request-ID": custom_req_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_req_id

    # Test auto-generated request ID when header omitted
    auto_resp = client.get("/info")
    assert auto_resp.status_code == 200
    assert "X-Request-ID" in auto_resp.headers
    assert auto_resp.headers["X-Request-ID"].startswith("req-")


def test_security_http_headers_present():
    """TEST 5: Verify production security HTTP headers are present on responses."""
    response = client.get("/info")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_delete_candidate_simulation_safety(db_session):
    """TEST 6: Verify DELETE_CANDIDATE execution remains simulation-only and NEVER deletes physical payloads."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"delete_test/safe_{uuid4().hex[:6]}.tmp",
        object_size_bytes=100 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=400),
        last_modified_at=ref_time - timedelta(days=400),
    )
    db_session.add(obj)
    db_session.commit()

    from app.models import RetentionPolicy, Recommendation
    from app.services.recommendation_engine import RecommendationService

    pol = RetentionPolicy(
        organization_id=org.id,
        object_id=obj.id,
        name="Expired Retention Test Policy",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=400),
        status="ACTIVE",
    )
    db_session.add(pol)
    db_session.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db_session, org.id, obj.id, reference_time=ref_time)

    service = ApprovalExecutionService()
    appr = service.create_or_get_approval_request(db_session, org.id, rec.id)
    appr.status = "APPROVED"
    db_session.commit()

    try:
        exec_res = service.execute_recommendation(db_session, org.id, rec.id)
        assert exec_res.status == "DELETE_SIMULATION_SUCCESS"
        assert any("simulation" in r.lower() for r in exec_res.reasons)

        # Confirm object still exists in DB (no hard physical deletion)
        db_obj = db_session.query(StorageObject).filter_by(id=obj.id).first()
        assert db_obj is not None
    finally:
        db_session.delete(pol)
        db_session.delete(rec)
        db_session.delete(obj)
        db_session.commit()
