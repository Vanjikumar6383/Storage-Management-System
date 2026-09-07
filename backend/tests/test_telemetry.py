import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models import Organization, StorageLocation, StorageObject, AccessEvent, RestoreEvent
from app.services.telemetry import (
    AccessEventIngestionService,
    RestoreEventService,
    ObjectUsageProfileService,
    UsageAggregationService,
    RestoreRiskService,
)
from app.core.telemetry_config import AccessEventTypeEnum, RestoreStatusEnum, AccessFrequencyEnum, RestoreRiskEnum

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_access_event_ingestion_and_idempotency(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="telemetry/test1.dat",
        object_size_bytes=1024,
        storage_class="STANDARD",
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
    )
    db_session.add(obj)
    db_session.commit()

    service = AccessEventIngestionService()
    idempotency_key = f"idem-key-{uuid4()}"

    # 1. Valid Event Ingestion
    event1 = service.record_access_event(
        db=db_session,
        organization_id=demo_org.id,
        object_id=obj.id,
        event_type=AccessEventTypeEnum.OBJECT_READ.value,
        idempotency_key=idempotency_key,
    )
    assert event1 is not None
    assert event1.idempotency_key == idempotency_key

    # 2. Duplicate Event (Idempotency) -> returns same event without duplicate row
    event2 = service.record_access_event(
        db=db_session,
        organization_id=demo_org.id,
        object_id=obj.id,
        event_type=AccessEventTypeEnum.OBJECT_READ.value,
        idempotency_key=idempotency_key,
    )
    assert event2.id == event1.id

    # 3. Tenant Mismatch -> PermissionError
    test_org = db_session.query(Organization).filter_by(slug="test-organization").first()
    with pytest.raises(PermissionError):
        service.record_access_event(
            db=db_session,
            organization_id=test_org.id,
            object_id=obj.id,
            event_type=AccessEventTypeEnum.OBJECT_READ.value,
        )

    # Cleanup
    db_session.delete(obj)
    db_session.commit()


def test_meaningful_access_vs_operational_metadata(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    now = datetime.now(timezone.utc)
    old_access = now - timedelta(days=10)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="telemetry/meta_vs_read.dat",
        object_size_bytes=2048,
        storage_class="STANDARD",
        created_at=now - timedelta(days=20),
        last_modified_at=now - timedelta(days=20),
        last_accessed_at=old_access,
    )
    db_session.add(obj)
    db_session.commit()

    service = AccessEventIngestionService()

    # Metadata operational read -> Should NOT update last_accessed_at
    service.record_access_event(
        db=db_session,
        organization_id=demo_org.id,
        object_id=obj.id,
        event_type=AccessEventTypeEnum.OBJECT_METADATA_READ.value,
        event_timestamp=now,
    )
    db_session.refresh(obj)
    assert obj.last_accessed_at == old_access

    # Object payload read -> SHOULD update last_accessed_at
    service.record_access_event(
        db=db_session,
        organization_id=demo_org.id,
        object_id=obj.id,
        event_type=AccessEventTypeEnum.OBJECT_READ.value,
        event_timestamp=now,
    )
    db_session.refresh(obj)
    assert obj.last_accessed_at == now

    # Cleanup
    db_session.delete(obj)
    db_session.commit()


def test_restore_event_ingestion_and_failure_metrics(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="telemetry/restore_test.dat",
        object_size_bytes=4096,
        storage_class="GLACIER",
        created_at=datetime.now(timezone.utc) - timedelta(days=100),
        last_modified_at=datetime.now(timezone.utc) - timedelta(days=100),
    )
    db_session.add(obj)
    db_session.commit()

    service = RestoreEventService()

    # Record 1 successful restore and 1 failed restore
    service.record_restore_event(
        db=db_session,
        organization_id=demo_org.id,
        object_id=obj.id,
        source_storage_class="GLACIER",
        target_storage_class="STANDARD",
        status=RestoreStatusEnum.SUCCEEDED.value,
        restore_duration_seconds=3600,
    )
    service.record_restore_event(
        db=db_session,
        organization_id=demo_org.id,
        object_id=obj.id,
        source_storage_class="GLACIER",
        target_storage_class="STANDARD",
        status=RestoreStatusEnum.FAILED.value,
        failure_reason="Storage quota exceeded",
    )

    profile_service = ObjectUsageProfileService()
    profile = profile_service.build_usage_profile(db_session, demo_org.id, obj.id)

    assert profile.restores_90d == 2
    assert profile.restore_success_rate == 0.5  # 1 succeeded out of 2 attempts
    assert profile.avg_restore_duration_seconds == 3600.0

    # Cleanup
    db_session.delete(obj)
    db_session.commit()


def test_scenarios_a_b_c_d_e(db_session):
    """
    Validates controlled test scenarios A, B, C, D, E.
    """
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    ref_time = datetime.now(timezone.utc)
    access_service = AccessEventIngestionService()
    restore_service = RestoreEventService()
    profile_service = ObjectUsageProfileService()

    # Scenario A: Age=200d, Accesses 90d=0, Restores 90d=0
    obj_a = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="scenarios/scenario_a.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj_a)
    db_session.commit()
    prof_a = profile_service.build_usage_profile(db_session, demo_org.id, obj_a.id, reference_time=ref_time)
    assert prof_a.age_days >= 200
    assert prof_a.accesses_90d == 0
    assert prof_a.restores_90d == 0
    assert prof_a.access_frequency == AccessFrequencyEnum.NONE.value
    assert prof_a.restore_risk == RestoreRiskEnum.LOW.value

    # Scenario B: Age=200d, Accesses 90d=25 (all in last 30d)
    obj_b = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="scenarios/scenario_b.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj_b)
    db_session.commit()

    for i in range(25):
        access_service.record_access_event(
            db_session,
            demo_org.id,
            obj_b.id,
            event_type=AccessEventTypeEnum.OBJECT_READ.value,
            event_timestamp=ref_time - timedelta(days=5),
        )

    prof_b = profile_service.build_usage_profile(db_session, demo_org.id, obj_b.id, reference_time=ref_time)
    assert prof_b.accesses_30d == 25
    assert prof_b.access_frequency == AccessFrequencyEnum.HIGH.value

    # Scenario C: Age=200d, Accesses 90d=0, Restores 90d=5
    obj_c = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="scenarios/scenario_c.dat",
        object_size_bytes=100,
        storage_class="GLACIER",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj_c)
    db_session.commit()

    for i in range(5):
        restore_service.record_restore_event(
            db_session,
            demo_org.id,
            obj_c.id,
            source_storage_class="GLACIER",
            target_storage_class="STANDARD",
            requested_at=ref_time - timedelta(days=10),
            status=RestoreStatusEnum.SUCCEEDED.value,
        )

    prof_c = profile_service.build_usage_profile(db_session, demo_org.id, obj_c.id, reference_time=ref_time)
    assert prof_c.restores_90d == 5
    assert prof_c.restore_risk == RestoreRiskEnum.HIGH.value

    # Scenario D: Age=20d, Accesses 30d=10
    obj_d = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="scenarios/scenario_d.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=20),
        last_modified_at=ref_time - timedelta(days=20),
    )
    db_session.add(obj_d)
    db_session.commit()

    for i in range(10):
        access_service.record_access_event(
            db_session,
            demo_org.id,
            obj_d.id,
            event_type=AccessEventTypeEnum.OBJECT_READ.value,
            event_timestamp=ref_time - timedelta(days=2),
        )

    prof_d = profile_service.build_usage_profile(db_session, demo_org.id, obj_d.id, reference_time=ref_time)
    assert prof_d.accesses_30d == 10
    assert prof_d.access_frequency == AccessFrequencyEnum.MEDIUM.value

    # Scenario E: Age=300d, No access events, No restore events
    obj_e = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="scenarios/scenario_e.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=300),
        last_modified_at=ref_time - timedelta(days=300),
    )
    db_session.add(obj_e)
    db_session.commit()

    prof_e = profile_service.build_usage_profile(db_session, demo_org.id, obj_e.id, reference_time=ref_time)
    assert prof_e.access_frequency == AccessFrequencyEnum.NONE.value
    assert prof_e.restore_risk == RestoreRiskEnum.LOW.value

    # Cleanup
    for o in [obj_a, obj_b, obj_c, obj_d, obj_e]:
        db_session.delete(o)
    db_session.commit()


def test_batch_aggregation_performance(db_session):
    """
    Verifies that batch profile building calculates metrics across multiple objects in a single query.
    """
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    objs = []
    for i in range(10):
        o = StorageObject(
            organization_id=demo_org.id,
            storage_location_id=loc.id,
            object_key=f"batch/perf_{i}.dat",
            object_size_bytes=100,
            storage_class="STANDARD",
            created_at=datetime.now(timezone.utc),
            last_modified_at=datetime.now(timezone.utc),
        )
        db_session.add(o)
        objs.append(o)
    db_session.commit()

    obj_ids = [o.id for o in objs]

    profile_service = ObjectUsageProfileService()
    profiles = profile_service.batch_build_usage_profiles(db_session, demo_org.id, object_ids=obj_ids)

    assert len(profiles) == 10

    # Cleanup
    for o in objs:
        db_session.delete(o)
    db_session.commit()


def test_telemetry_api_endpoints(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key="api/telemetry_test.dat",
        object_size_bytes=500,
        storage_class="STANDARD",
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
    )
    db_session.add(obj)
    db_session.commit()

    # 1. Post Access Event
    acc_resp = client.post(
        f"/api/v1/objects/{obj.id}/access-events?organization_id={demo_org.id}",
        json={"event_type": "OBJECT_READ", "source": "api-test"},
    )
    assert acc_resp.status_code == 201
    assert acc_resp.json()["object_id"] == str(obj.id)

    # 2. Post Restore Event
    rst_resp = client.post(
        f"/api/v1/objects/{obj.id}/restore-events?organization_id={demo_org.id}",
        json={
            "source_storage_class": "GLACIER",
            "target_storage_class": "STANDARD",
            "status": "SUCCEEDED",
            "restore_duration_seconds": 1800,
        },
    )
    assert rst_resp.status_code == 201

    # 3. Get Usage Profile
    prof_resp = client.get(f"/api/v1/objects/{obj.id}/usage-profile?organization_id={demo_org.id}")
    assert prof_resp.status_code == 200
    prof_data = prof_resp.json()
    assert prof_data["object_id"] == str(obj.id)
    assert prof_data["accesses_30d"] == 1
    assert prof_data["restores_30d"] == 1

    # 4. Tenant Isolation Check (Org A cannot request Org B object profile)
    test_org = db_session.query(Organization).filter_by(slug="test-organization").first()
    iso_resp = client.get(f"/api/v1/objects/{obj.id}/usage-profile?organization_id={test_org.id}")
    assert iso_resp.status_code == 404

    # Cleanup
    db_session.delete(obj)
    db_session.commit()
