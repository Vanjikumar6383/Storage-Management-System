import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageLocation,
    Environment,
    StorageObject,
    RetentionPolicy,
    LegalHold,
)
from app.services.policy_engine import (
    PolicyEngineService,
    PolicyDecisionEnum,
    RetentionStateEnum,
)

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_retention_active_no_legal_hold(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/test1_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=10),
        last_modified_at=ref_time - timedelta(days=10),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name=f"Obj Active Policy 30d {uuid4().hex[:8]}",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=10),
        status="ACTIVE",
    )
    db_session.add(pol)
    db_session.commit()

    try:
        engine = PolicyEngineService()
        decision = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)

        assert decision.decision == PolicyDecisionEnum.BLOCKED.value
        assert decision.retention_state == RetentionStateEnum.ACTIVE.value
        assert decision.legal_hold_active is False
    finally:
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_2_retention_expired_no_legal_hold(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/test2_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=100),
        last_modified_at=ref_time - timedelta(days=100),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name=f"Obj Expired Policy 30d {uuid4().hex[:8]}",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=100),
        status="ACTIVE",
    )
    db_session.add(pol)
    db_session.commit()

    try:
        engine = PolicyEngineService()
        decision = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)

        assert decision.decision == PolicyDecisionEnum.ALLOWED.value
        assert decision.retention_state == RetentionStateEnum.EXPIRED.value
        assert decision.legal_hold_active is False
    finally:
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_3_retention_expired_active_legal_hold(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/test3_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=100),
        last_modified_at=ref_time - timedelta(days=100),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name=f"Obj Expired Policy 30d {uuid4().hex[:8]}",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=100),
        status="ACTIVE",
    )
    hold = LegalHold(
        organization_id=demo_org.id,
        object_id=obj.id,
        status="ACTIVE",
        reason_reference="REF-LEGAL-99",
    )
    db_session.add_all([pol, hold])
    db_session.commit()

    try:
        engine = PolicyEngineService()
        decision = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)

        assert decision.decision == PolicyDecisionEnum.BLOCKED.value
        assert decision.retention_state == RetentionStateEnum.EXPIRED.value
        assert decision.legal_hold_active is True
    finally:
        db_session.delete(hold)
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_4_retention_active_active_legal_hold(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/test4_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=5),
        last_modified_at=ref_time - timedelta(days=5),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name=f"Obj Active Policy 30d {uuid4().hex[:8]}",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=5),
        status="ACTIVE",
    )
    hold = LegalHold(
        organization_id=demo_org.id,
        object_id=obj.id,
        status="ACTIVE",
        reason_reference="REF-LEGAL-100",
    )
    db_session.add_all([pol, hold])
    db_session.commit()

    try:
        engine = PolicyEngineService()
        decision = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)

        assert decision.decision == PolicyDecisionEnum.BLOCKED.value
        assert decision.legal_hold_active is True
    finally:
        db_session.delete(hold)
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_5_no_retention_policy_fail_safe(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/test5_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        engine = PolicyEngineService()
        decision = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE")

        # Fail-safe design: NO_POLICY -> REQUIRES_REVIEW for DELETE
        assert decision.decision == PolicyDecisionEnum.REQUIRES_REVIEW.value
        assert decision.retention_state == RetentionStateEnum.NO_POLICY.value
    finally:
        db_session.delete(obj)
        db_session.commit()


def test_6_conflicting_retention_policies_fail_safe(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/test6_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
    )
    db_session.add(obj)
    db_session.commit()

    # Conflicting policies at object level with same priority
    pol1 = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name=f"Conflict 1 {uuid4().hex[:8]}",
        retention_duration_days=30,
        priority=100,
        status="ACTIVE",
    )
    pol2 = RetentionPolicy(
        organization_id=demo_org.id,
        object_id=obj.id,
        name=f"Conflict 2 {uuid4().hex[:8]}",
        retention_duration_days=365,
        priority=100,
        status="ACTIVE",
    )
    db_session.add_all([pol1, pol2])
    db_session.commit()

    try:
        engine = PolicyEngineService()
        decision = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE")

        assert decision.decision == PolicyDecisionEnum.REQUIRES_REVIEW.value
        assert decision.retention_state == RetentionStateEnum.UNKNOWN.value
    finally:
        db_session.delete(pol1)
        db_session.delete(pol2)
        db_session.delete(obj)
        db_session.commit()


def test_7_8_9_precedence_hierarchy(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    env = db_session.query(Environment).filter_by(organization_id=demo_org.id).first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        environment_id=env.id,
        object_key=f"policy/hierarchy_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=40),
        last_modified_at=ref_time - timedelta(days=40),
    )
    db_session.add(obj)
    db_session.commit()

    # Create policies at Org, Env, Location, Object levels
    p_org = RetentionPolicy(organization_id=demo_org.id, name=f"P_Org_{uuid4().hex[:8]}", retention_duration_days=10, effective_date=ref_time - timedelta(days=40), status="ACTIVE")
    p_env = RetentionPolicy(organization_id=demo_org.id, environment_id=env.id, name=f"P_Env_{uuid4().hex[:8]}", retention_duration_days=20, effective_date=ref_time - timedelta(days=40), status="ACTIVE")
    p_loc = RetentionPolicy(organization_id=demo_org.id, storage_location_id=loc.id, name=f"P_Loc_{uuid4().hex[:8]}", retention_duration_days=30, effective_date=ref_time - timedelta(days=40), status="ACTIVE")
    p_obj = RetentionPolicy(organization_id=demo_org.id, object_id=obj.id, name=f"P_Obj_{uuid4().hex[:8]}", retention_duration_days=100, effective_date=ref_time - timedelta(days=40), status="ACTIVE")

    db_session.add_all([p_org, p_env, p_loc, p_obj])
    db_session.commit()

    engine = PolicyEngineService()

    try:
        # 1. Object level overrides everything (duration=100d, age=40d -> ACTIVE)
        d1 = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)
        assert d1.applicable_policy_id == str(p_obj.id)
        assert d1.retention_state == RetentionStateEnum.ACTIVE.value

        # 2. Delete object policy -> Location policy overrides Env/Org (duration=30d, age=40d -> EXPIRED)
        db_session.delete(p_obj)
        db_session.commit()

        d2 = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)
        assert d2.applicable_policy_id == str(p_loc.id)
        assert d2.retention_state == RetentionStateEnum.EXPIRED.value

        # 3. Delete location policy -> Env policy overrides Org (duration=20d, age=40d -> EXPIRED)
        db_session.delete(p_loc)
        db_session.commit()

        d3 = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)
        assert d3.applicable_policy_id == str(p_env.id)
    finally:
        for p in [p_org, p_env]:
            try:
                db_session.delete(p)
            except Exception:
                pass
        db_session.delete(obj)
        db_session.commit()


def test_10_11_12_actions_archive_infrequent_keep(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/actions_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=5),
        last_modified_at=ref_time - timedelta(days=5),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(organization_id=demo_org.id, object_id=obj.id, name=f"P_Active_{uuid4().hex[:8]}", retention_duration_days=30, status="ACTIVE")
    db_session.add(pol)
    db_session.commit()

    engine = PolicyEngineService()

    try:
        # KEEP -> ALLOWED
        d_keep = engine.evaluate_action(db_session, demo_org.id, obj.id, "KEEP", reference_time=ref_time)
        assert d_keep.decision == PolicyDecisionEnum.ALLOWED.value

        # MOVE_TO_INFREQUENT_ACCESS while retention active -> ALLOWED
        d_ia = engine.evaluate_action(db_session, demo_org.id, obj.id, "MOVE_TO_INFREQUENT_ACCESS", reference_time=ref_time)
        assert d_ia.decision == PolicyDecisionEnum.ALLOWED.value

        # ARCHIVE while retention active -> ALLOWED
        d_arch = engine.evaluate_action(db_session, demo_org.id, obj.id, "ARCHIVE", reference_time=ref_time)
        assert d_arch.decision == PolicyDecisionEnum.ALLOWED.value
    finally:
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_13_14_15_tenant_isolation_and_released_legal_holds(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    test_org = db_session.query(Organization).filter_by(slug="test-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()
    ref_time = datetime.now(timezone.utc)

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"policy/holds_{uuid4().hex[:8]}.dat",
        object_size_bytes=100,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=100),
        last_modified_at=ref_time - timedelta(days=100),
    )
    db_session.add(obj)
    db_session.commit()

    pol = RetentionPolicy(organization_id=demo_org.id, object_id=obj.id, name=f"P_Expired_{uuid4().hex[:8]}", retention_duration_days=30, effective_date=ref_time - timedelta(days=100), status="ACTIVE")

    # Inactive/Released hold
    released_hold = LegalHold(
        organization_id=demo_org.id,
        object_id=obj.id,
        status="RELEASED",
        reason_reference="REF-RELEASED",
        released_at=ref_time - timedelta(days=1),
    )
    db_session.add_all([pol, released_hold])
    db_session.commit()

    engine = PolicyEngineService()

    try:
        # TEST 14: Released hold does NOT block deletion
        d_released = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)
        assert d_released.decision == PolicyDecisionEnum.ALLOWED.value
        assert d_released.legal_hold_active is False

        # TEST 15: Multiple active legal holds
        active_hold1 = LegalHold(organization_id=demo_org.id, object_id=obj.id, status="ACTIVE", reason_reference="HOLD-1")
        active_hold2 = LegalHold(organization_id=demo_org.id, object_id=obj.id, status="ACTIVE", reason_reference="HOLD-2")
        db_session.add_all([active_hold1, active_hold2])
        db_session.commit()

        d_multi = engine.evaluate_action(db_session, demo_org.id, obj.id, "DELETE", reference_time=ref_time)
        assert d_multi.decision == PolicyDecisionEnum.BLOCKED.value
        assert d_multi.legal_hold_active is True

        # TEST 13: Tenant Isolation Mismatch
        with pytest.raises(PermissionError):
            engine.evaluate_action(db_session, test_org.id, obj.id, "DELETE")
    finally:
        db_session.delete(released_hold)
        db_session.delete(pol)
        db_session.delete(obj)
        db_session.commit()


def test_policy_evaluation_api_endpoint(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    loc = db_session.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

    obj = StorageObject(
        organization_id=demo_org.id,
        storage_location_id=loc.id,
        object_key=f"api/policy_test_{uuid4().hex[:8]}.dat",
        object_size_bytes=500,
        storage_class="STANDARD",
        created_at=datetime.now(timezone.utc),
        last_modified_at=datetime.now(timezone.utc),
    )
    db_session.add(obj)
    db_session.commit()

    try:
        response = client.post(
            f"/api/v1/objects/{obj.id}/policy-evaluation?organization_id={demo_org.id}",
            json={"action": "DELETE"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["object_id"] == str(obj.id)
        assert data["decision"] in ("BLOCKED", "ALLOWED", "REQUIRES_REVIEW")
        assert "reasons" in data
    finally:
        db_session.delete(obj)
        db_session.commit()
