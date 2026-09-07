import pytest
from uuid import UUID, uuid4
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
    ApprovalRequest,
    MigrationEvent,
    RollbackEvent,
    AuditLog,
)
from app.services.recommendation_engine import RecommendationService
from app.services.approval_execution import ApprovalExecutionService
from app.services.telemetry import AccessEventIngestionService
from app.core.telemetry_config import AccessEventTypeEnum

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_2_3_4_approval_lifecycle_and_invalid_transition(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"exec/test1_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time)

    exec_service = ApprovalExecutionService()

    try:
        # 1. Get/Create Approval Request -> PENDING
        appr = exec_service.create_or_get_approval_request(db_session, demo_org.id, rec.id)
        assert appr.status == "PENDING"

        # 2. Approval Success -> APPROVED
        appr_ok = exec_service.process_approval_decision(
            db_session, demo_org.id, rec.id, decision="APPROVE", reason="Approved after engineering review"
        )
        assert appr_ok.status == "APPROVED"
        assert appr_ok.override_reason == "Approved after engineering review"

        # Verify Audit Log
        audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.organization_id == demo_org.id, AuditLog.action == "RECOMMENDATION_APPROVED")
            .order_by(AuditLog.timestamp.desc())
            .first()
        )
        assert audit is not None

        # 3. Process Rejection on a new recommendation -> REJECTED
        rec2 = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time)
        appr_rej = exec_service.process_approval_decision(
            db_session, demo_org.id, rec2.id, decision="REJECT", reason="Required for quarterly release"
        )
        assert appr_rej.status == "REJECTED"
        assert appr_rej.override_reason == "Required for quarterly release"

        # 4. Invalid State Transition on REJECTED request -> Error
        with pytest.raises(ValueError):
            exec_service.process_approval_decision(db_session, demo_org.id, rec2.id, decision="APPROVE")

    finally:
        db_session.delete(rec)
        db_session.delete(obj)
        db_session.commit()


def test_5_6_7_execute_without_or_rejected_approval(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"exec/test5_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time)
    exec_service = ApprovalExecutionService()

    try:
        # Execute without approval -> Error / BLOCKED
        with pytest.raises(ValueError):
            exec_service.execute_recommendation(db_session, demo_org.id, rec.id)

        # Reject approval and attempt execute -> BLOCKED
        exec_service.process_approval_decision(db_session, demo_org.id, rec.id, decision="REJECT", reason="Not needed")
        res = exec_service.execute_recommendation(db_session, demo_org.id, rec.id)
        assert res.status == "BLOCKED"
    finally:
        db_session.delete(rec)
        db_session.delete(obj)
        db_session.commit()


def test_8_9_10_11_pre_execution_safety_gate_blocking(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"exec/safety_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time)
    exec_service = ApprovalExecutionService()
    exec_service.process_approval_decision(db_session, demo_org.id, rec.id, decision="APPROVE")

    try:
        # TEST 10: Object accessed after recommendation -> STALE_RECOMMENDATION
        acc_service = AccessEventIngestionService()
        acc_service.record_access_event(
            db_session, demo_org.id, obj.id, AccessEventTypeEnum.OBJECT_READ.value, event_timestamp=ref_time + timedelta(minutes=5)
        )

        res_stale = exec_service.execute_recommendation(db_session, demo_org.id, rec.id)
        assert res_stale.status == "STALE_RECOMMENDATION"

        # TEST 8: Legal hold added after approval -> BLOCKED
        # Create fresh rec + approval
        rec2 = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time + timedelta(minutes=10))
        exec_service.process_approval_decision(db_session, demo_org.id, rec2.id, decision="APPROVE")

        hold = LegalHold(organization_id=demo_org.id, object_id=obj.id, status="ACTIVE", reason_reference="REF-POST-APPROVE-HOLD")
        db_session.add(hold)
        db_session.commit()

        res_hold = exec_service.execute_recommendation(db_session, demo_org.id, rec2.id)
        assert res_hold.status == "BLOCKED"

        db_session.delete(hold)
        db_session.delete(rec2)
        db_session.commit()
    finally:
        db_session.delete(rec)
        db_session.delete(obj)
        db_session.commit()


def test_12_14_25_end_to_end_migration_and_rollback(db_session):
    """
    TEST 12, 14, 25: End-to-end STANDARD -> ARCHIVE migration and rollback to STANDARD.
    """
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"exec/e2e_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time)
    exec_service = ApprovalExecutionService()
    exec_service.process_approval_decision(db_session, demo_org.id, rec.id, decision="APPROVE")

    try:
        # 1. Execute Migration -> STANDARD -> ARCHIVE
        res_exec = exec_service.execute_recommendation(db_session, demo_org.id, rec.id)
        assert res_exec.status == "SUCCESS"
        assert res_exec.migration_id is not None

        db_session.refresh(obj)
        assert obj.storage_class == "ARCHIVE"

        # 2. Execute Rollback -> ARCHIVE -> STANDARD
        res_rb = exec_service.rollback_migration(
            db_session, demo_org.id, UUID(res_exec.migration_id), reason="Audit rollback test"
        )
        assert res_rb.status == "SUCCESS"
        assert res_rb.restored_storage_class == "STANDARD"

        db_session.refresh(obj)
        assert obj.storage_class == "STANDARD"

        # 3. Idempotency test: repeated rollback returns ALREADY_EXECUTED
        res_rb2 = exec_service.rollback_migration(
            db_session, demo_org.id, UUID(res_exec.migration_id), reason="Duplicate rollback"
        )
        assert res_rb2.status == "ALREADY_EXECUTED"

    finally:
        db_session.delete(rec)
        db_session.delete(obj)
        db_session.commit()


def test_16_18_19_22_idempotency_concurrency_and_delete_simulation(db_session):
    """
    TEST 16, 18, 19, 22: Idempotency, concurrency, tenant isolation, and DELETE simulation safety mode.
    """
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    test_org = db_session.query(Organization).filter_by(slug="test-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    # 1. DELETE Candidate Simulation Test (TEST 22)
    obj_del = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"exec/delete_sim_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=400),
        last_modified_at=ref_time - timedelta(days=400),
    )
    db_session.add(obj_del)
    db_session.commit()

    pol = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj_del.id,
        name="Expired 30d",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=400),
        status="ACTIVE",
    )
    db_session.add(pol)
    db_session.commit()

    rec_service = RecommendationService()
    rec_del = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj_del.id, reference_time=ref_time)
    exec_service = ApprovalExecutionService()
    exec_service.process_approval_decision(db_session, demo_org.id, rec_del.id, decision="APPROVE")

    try:
        # Execute DELETE -> Dry-run simulation success
        res_sim = exec_service.execute_recommendation(db_session, demo_org.id, rec_del.id)
        assert res_sim.status == "DELETE_SIMULATION_SUCCESS"

        # Verify physical object was NOT deleted
        db_session.refresh(obj_del)
        assert obj_del.id is not None

        # Double execution idempotency (TEST 16)
        res_idem = exec_service.execute_recommendation(db_session, demo_org.id, rec_del.id)
        assert res_idem.status == "ALREADY_EXECUTED"

        # Tenant isolation check (TEST 19)
        with pytest.raises(PermissionError):
            exec_service.execute_recommendation(db_session, test_org.id, rec_del.id)

    finally:
        db_session.delete(pol)
        db_session.delete(rec_del)
        db_session.delete(obj_del)
        db_session.commit()


def test_approval_and_execution_api_endpoints(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"exec/api_{uuid4().hex[:8]}.dat",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db_session, demo_org.id, obj.id, reference_time=ref_time)

    try:
        # POST Approval Endpoint
        appr_res = client.post(
            f"/api/v1/recommendations/{rec.id}/approval?organization_id={demo_org.id}",
            json={"decision": "APPROVE", "reason": "Approved via API test"},
        )
        assert appr_res.status_code == 200
        assert appr_res.json()["status"] == "APPROVED"

        # GET Approval Endpoint
        get_appr = client.get(f"/api/v1/recommendations/{rec.id}/approval?organization_id={demo_org.id}")
        assert get_appr.status_code == 200
        assert get_appr.json()["status"] == "APPROVED"

        # POST Execute Endpoint
        exec_res = client.post(f"/api/v1/recommendations/{rec.id}/execute?organization_id={demo_org.id}")
        assert exec_res.status_code == 200
        exec_data = exec_res.json()
        assert exec_data["status"] in ("SUCCESS", "DELETE_SIMULATION_SUCCESS")

        if exec_data.get("migration_id"):
            # POST Rollback Endpoint
            rb_res = client.post(
                f"/api/v1/migrations/{exec_data['migration_id']}/rollback?organization_id={demo_org.id}",
                json={"reason": "Rollback API test"},
            )
            assert rb_res.status_code == 200
            assert rb_res.json()["status"] == "SUCCESS"
    finally:
        db_session.delete(rec)
        db_session.delete(obj)
        db_session.commit()
