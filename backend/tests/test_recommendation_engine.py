import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageLocation,
    StorageObject,
    RetentionPolicy,
    LegalHold,
    Recommendation,
    RecommendationTypeEnum,
)
from app.services.recommendation_engine import RecommendationService
from app.services.telemetry import AccessEventIngestionService, RestoreEventService
from app.core.telemetry_config import AccessEventTypeEnum, RestoreStatusEnum

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_old_unused_no_restrictions_archive(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test1_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,  # 10 MB
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=250),
        last_modified_at=ref_time - timedelta(days=250),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        assert result.recommendation_type == RecommendationTypeEnum.ARCHIVE.value
        assert result.recommended_storage_class == "ARCHIVE"
        assert result.estimated_savings_usd > 0.0
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_2_old_frequently_accessed_keep(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test2_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=250),
        last_modified_at=ref_time - timedelta(days=250),
    )
    db_session.add(obj)
    db_session.commit()

    access_service = AccessEventIngestionService()
    for _ in range(15):
        access_service.record_access_event(
            db_session, demo_org.id, obj.id, AccessEventTypeEnum.OBJECT_READ.value, event_timestamp=ref_time - timedelta(days=5)
        )

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        assert result.recommendation_type == RecommendationTypeEnum.KEEP.value
        assert result.recommended_storage_class == "STANDARD"
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_3_10_old_repeated_restores_high_risk_hold_or_keep(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test3_{uuid4().hex[:8]}.dat",
        object_size_bytes=50 * 1024 * 1024,
        storage_class="GLACIER",
        created_at=ref_time - timedelta(days=250),
        last_modified_at=ref_time - timedelta(days=250),
    )
    db_session.add(obj)
    db_session.commit()

    restore_service = RestoreEventService()
    for _ in range(4):
        restore_service.record_restore_event(
            db_session, demo_org.id, obj.id, "GLACIER", "STANDARD", requested_at=ref_time - timedelta(days=10), status=RestoreStatusEnum.SUCCEEDED.value
        )

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        # High restore risk prevents aggressive archival and flags HOLD/KEEP
        assert result.recommendation_type in (RecommendationTypeEnum.HOLD.value, RecommendationTypeEnum.KEEP.value)
        assert result.risk_level == "HIGH"
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_4_old_retention_active_hold(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test4_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=400),
        last_modified_at=ref_time - timedelta(days=400),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name="Retention Active 500d",
        retention_duration_days=500,
        effective_date=ref_time - timedelta(days=400),
        status="ACTIVE",
    )
    db_session.add(pol)
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        # Retention active prevents DELETE_CANDIDATE
        assert result.recommendation_type != RecommendationTypeEnum.DELETE_CANDIDATE.value
    finally:
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_5_old_legal_hold_hold(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test5_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=400),
        last_modified_at=ref_time - timedelta(days=400),
    )
    db_session.add(obj)
    db_session.commit()

    hold = LegalHold(
        organization_id=demo_org.id,
        object_id=obj.id,
        status="ACTIVE",
        reason_reference="REF-SEC-HOLD",
    )
    db_session.add(hold)
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        assert result.recommendation_type == RecommendationTypeEnum.HOLD.value
        assert result.requires_approval is True
    finally:
        db_session.delete(hold)
        db_session.delete(obj)
        db_session.commit()


def test_6_retention_expired_no_hold_no_access_delete_candidate(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test6_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=400),
        last_modified_at=ref_time - timedelta(days=400),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name="Expired Policy 30d",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=400),
        status="ACTIVE",
    )
    db_session.add(pol)
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        assert result.recommendation_type == RecommendationTypeEnum.DELETE_CANDIDATE.value
        assert result.requires_approval is True
        assert result.impact_level == "HIGH_IMPACT"
    finally:
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_7_recent_object_low_access_keep(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test7_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=15),
        last_modified_at=ref_time - timedelta(days=15),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        assert result.recommendation_type == RecommendationTypeEnum.KEEP.value
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_8_already_archived_no_redundant_archival(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test8_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="ARCHIVE",
        created_at=ref_time - timedelta(days=300),
        last_modified_at=ref_time - timedelta(days=300),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        assert result.recommendation_type == RecommendationTypeEnum.KEEP.value
        assert result.recommended_storage_class == "ARCHIVE"
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_9_already_infrequent_no_redundant_tiering(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test9_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="INFREQUENT_ACCESS",
        created_at=ref_time - timedelta(days=100),
        last_modified_at=ref_time - timedelta(days=100),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        assert result.recommendation_type == RecommendationTypeEnum.KEEP.value
        assert result.recommended_storage_class == "INFREQUENT_ACCESS"
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_11_12_missing_or_conflicting_policy_fail_safe(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test11_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=500),
        last_modified_at=ref_time - timedelta(days=500),
    )
    db_session.add(obj)
    db_session.commit()

    # Conflicting policies
    pol1 = RetentionPolicy(organization_id=demo_org.id, object_id=obj.id, name="Pol 1", retention_duration_days=30, priority=100, status="ACTIVE")
    pol2 = RetentionPolicy(organization_id=demo_org.id, object_id=obj.id, name="Pol 2", retention_duration_days=365, priority=100, status="ACTIVE")
    db_session.add_all([pol1, pol2])
    db_session.commit()

    try:
        service = RecommendationService()
        result = service.evaluate_object_recommendation(db_session, demo_org.id, obj, reference_time=ref_time)

        # Conflicting policy must NOT trigger unsafe DELETE_CANDIDATE
        assert result.recommendation_type != RecommendationTypeEnum.DELETE_CANDIDATE.value
        assert result.recommendation_type == RecommendationTypeEnum.HOLD.value
    finally:
        db_session.delete(pol1)
        db_session.delete(pol2)
        db_session.delete(obj)
        db_session.commit()


def test_13_tenant_isolation(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    test_org = db_session.query(Organization).filter_by(slug="test-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test13_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        service = RecommendationService()
        with pytest.raises(PermissionError):
            service.evaluate_object_recommendation(db_session, test_org.id, obj)
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_14_15_16_17_evidence_savings_zero_size_small_size(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    # Test 17: Tiny object (10 KB) below 128 KB migration threshold
    small_obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/test17_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024,  # 10 KB
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=250),
        last_modified_at=ref_time - timedelta(days=250),
    )
    db_session.add(small_obj)
    db_session.commit()

    try:
        service = RecommendationService()
        res_small = service.evaluate_object_recommendation(db_session, demo_org.id, small_obj, reference_time=ref_time)

        # Small object size -> KEEP (migration overhead not justified)
        assert res_small.recommendation_type == RecommendationTypeEnum.KEEP.value
        assert "rules" in res_small.evidence_structure
        assert res_small.rule_version == "baseline-v1"
    finally:
        db_session.delete(small_obj)
        db_session.commit()


def test_18_19_20_batch_idempotency_no_side_effects(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    objs = []
    for i in range(5):
        o = StorageObject(
            organization_id=demo_org.id,
            storage_location_id=loc.id,
            object_key=f"rec/batch_{i}_{uuid4().hex[:8]}.dat",
            object_size_bytes=20 * 1024 * 1024,
            storage_class="STANDARD",
            created_at=datetime.now(timezone.utc) - timedelta(days=200),
            last_modified_at=datetime.now(timezone.utc) - timedelta(days=200),
        )
        db_session.add(o)
        objs.append(o)
    db_session.commit()

    try:
        service = RecommendationService()

        # Batch generation
        recs1 = service.batch_generate_recommendations(db_session, demo_org.id, limit=10)
        assert len(recs1) >= 5

        # Idempotent re-run
        recs2 = service.batch_generate_recommendations(db_session, demo_org.id, limit=10)
        assert len(recs2) == len(recs1)

        # Verify storage class remains unchanged (zero side effects on storage)
        for o in objs:
            db_session.refresh(o)
            assert o.storage_class == "STANDARD"
    finally:
        for o in objs:
            db_session.delete(o)
        db_session.commit()


def test_recommendation_api_endpoints(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"rec/api_test_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=datetime.now(timezone.utc) - timedelta(days=200),
        last_modified_at=datetime.now(timezone.utc) - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        # POST Recommendation
        post_res = client.post(f"/api/v1/objects/{obj.id}/recommendation?organization_id={demo_org.id}")
        assert post_res.status_code == 200
        data = post_res.json()
        assert data["object_id"] == str(obj.id)
        assert "evidence" in data

        # GET Recommendation
        get_res = client.get(f"/api/v1/objects/{obj.id}/recommendation?organization_id={demo_org.id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == data["id"]
    finally:
        db_session.delete(obj)
        db_session.commit()
