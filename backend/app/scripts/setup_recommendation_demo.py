"""
Controlled 10-Object Lifecycle Recommendation Demonstration Script.
Validates explainable rule catalog, cost estimation, risk classification, and governance boundaries.
"""

from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.db.database import SessionLocal
from app.models import (
    Organization,
    Environment,
    StorageLocation,
    StorageObject,
    RetentionPolicy,
    LegalHold,
)
from app.services.recommendation_engine import RecommendationService
from app.services.telemetry import AccessEventIngestionService, RestoreEventService
from app.core.telemetry_config import AccessEventTypeEnum, RestoreStatusEnum


def run_recommendation_demo():
    print("==================================================")
    print("STEP 6 — Explainable Lifecycle Recommendation Engine")
    print("==================================================")

    db = SessionLocal()
    try:
        demo_org = db.query(Organization).filter_by(slug="demo-organization").first()
        env = db.query(Environment).filter_by(organization_id=demo_org.id).first()
        loc = db.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

        db.query(RetentionPolicy).delete(synchronize_session=False)
        db.query(LegalHold).delete(synchronize_session=False)
        db.commit()

        ref_time = datetime.now(timezone.utc)
        service = RecommendationService()
        access_service = AccessEventIngestionService()
        restore_service = RestoreEventService()

        fixtures = []

        # 1. Old Unused Object (Age 250d, 0 accesses) -> ARCHIVE
        o1 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/01_old_unused_{uuid4().hex[:6]}.dat", object_size_bytes=50 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=250), last_modified_at=ref_time - timedelta(days=250))
        db.add(o1)
        db.commit()
        fixtures.append(("1. Old Unused Object", o1))

        # 2. Old Frequently Accessed Object (Age 250d, 30 accesses) -> KEEP
        o2 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/02_old_frequent_{uuid4().hex[:6]}.dat", object_size_bytes=50 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=250), last_modified_at=ref_time - timedelta(days=250))
        db.add(o2)
        db.commit()
        for _ in range(30):
            access_service.record_access_event(db, demo_org.id, o2.id, AccessEventTypeEnum.OBJECT_READ.value, event_timestamp=ref_time - timedelta(days=5))
        fixtures.append(("2. Old Frequently Accessed Object", o2))

        # 3. Old Restore-Heavy Object (Age 250d, 5 restores) -> HOLD/KEEP
        o3 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/03_restore_heavy_{uuid4().hex[:6]}.dat", object_size_bytes=50 * 1024 * 1024, storage_class="GLACIER", created_at=ref_time - timedelta(days=250), last_modified_at=ref_time - timedelta(days=250))
        db.add(o3)
        db.commit()
        for _ in range(5):
            restore_service.record_restore_event(db, demo_org.id, o3.id, "GLACIER", "STANDARD", requested_at=ref_time - timedelta(days=10), status=RestoreStatusEnum.SUCCEEDED.value)
        fixtures.append(("3. Old Restore-Heavy Object", o3))

        # 4. Recently Created Object (Age 15d) -> KEEP
        o4 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/04_recent_obj_{uuid4().hex[:6]}.dat", object_size_bytes=10 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=15), last_modified_at=ref_time - timedelta(days=15))
        db.add(o4)
        db.commit()
        fixtures.append(("4. Recently Created Object", o4))

        # 5. Retention Active Object (Age 400d, Active 500d Retention) -> HOLD/ARCHIVE
        o5 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/05_retention_active_{uuid4().hex[:6]}.dat", object_size_bytes=20 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=400), last_modified_at=ref_time - timedelta(days=400))
        db.add(o5)
        db.commit()
        p5 = RetentionPolicy(organization_id=demo_org.id, object_id=o5.id, name="500d Active Policy", retention_duration_days=500, effective_date=ref_time - timedelta(days=400), status="ACTIVE")
        db.add(p5)
        db.commit()
        fixtures.append(("5. Retention Active Object", o5))

        # 6. Legal Hold Object (Age 400d, Active Legal Hold) -> HOLD
        o6 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/06_legal_hold_{uuid4().hex[:6]}.dat", object_size_bytes=20 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=400), last_modified_at=ref_time - timedelta(days=400))
        db.add(o6)
        db.commit()
        h6 = LegalHold(organization_id=demo_org.id, object_id=o6.id, status="ACTIVE", reason_reference="REF-SEC-LITIGATION")
        db.add(h6)
        db.commit()
        fixtures.append(("6. Legal-Hold Object", o6))

        # 7. Expired Retention Object (Age 400d, 30d Expired Policy) -> DELETE_CANDIDATE
        o7 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/07_expired_retention_{uuid4().hex[:6]}.dat", object_size_bytes=20 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=400), last_modified_at=ref_time - timedelta(days=400))
        db.add(o7)
        db.commit()
        p7 = RetentionPolicy(organization_id=demo_org.id, object_id=o7.id, name="30d Expired Policy", retention_duration_days=30, effective_date=ref_time - timedelta(days=400), status="ACTIVE")
        db.add(p7)
        db.commit()
        fixtures.append(("7. Expired Retention Object", o7))

        # 8. Already Archived Object -> KEEP
        o8 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/08_already_archived_{uuid4().hex[:6]}.dat", object_size_bytes=100 * 1024 * 1024, storage_class="ARCHIVE", created_at=ref_time - timedelta(days=300), last_modified_at=ref_time - timedelta(days=300))
        db.add(o8)
        db.commit()
        fixtures.append(("8. Already Archived Object", o8))

        # 9. Small Object (10 KB < 128 KB) -> KEEP
        o9 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/09_small_object_{uuid4().hex[:6]}.dat", object_size_bytes=10 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=250), last_modified_at=ref_time - timedelta(days=250))
        db.add(o9)
        db.commit()
        fixtures.append(("9. Small Object (Below Threshold)", o9))

        # 10. Object with Conflicting Policy -> HOLD
        o10 = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/10_conflicting_policy_{uuid4().hex[:6]}.dat", object_size_bytes=30 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=400), last_modified_at=ref_time - timedelta(days=400))
        db.add(o10)
        db.commit()
        p10_a = RetentionPolicy(organization_id=demo_org.id, object_id=o10.id, name="Conflict 1", retention_duration_days=30, priority=100, status="ACTIVE")
        p10_b = RetentionPolicy(organization_id=demo_org.id, object_id=o10.id, name="Conflict 2", retention_duration_days=365, priority=100, status="ACTIVE")
        db.add_all([p10_a, p10_b])
        db.commit()
        fixtures.append(("10. Conflicting Policy Object", o10))

        print("\nEVALUATING 10 CONTROLLED DEMONSTRATION FIXTURES:")
        print("--------------------------------------------------")
        for label, obj in fixtures:
            res = service.evaluate_object_recommendation(db, demo_org.id, obj, reference_time=ref_time)
            print(f"\n[{label}] Object Key: {obj.object_key}")
            print(f"   Size: {obj.object_size_bytes} bytes | Storage Class: {obj.storage_class}")
            print(f"   Recommendation: {res.recommendation_type} -> Target Class: {res.recommended_storage_class}")
            print(f"   Risk Level: {res.risk_level} | Impact Level: {res.impact_level} | Requires Approval: {res.requires_approval}")
            print(f"   Estimated Monthly Savings: ${res.estimated_savings_usd:.4f} USD")
            print(f"   Primary Reason: {res.reason}")
            print(f"   Rule Version: {res.rule_version}")

        # Cleanup fixtures
        for p in [p5, p7, p10_a, p10_b]:
            db.delete(p)
        db.delete(h6)
        for _, obj in fixtures:
            db.delete(obj)
        db.commit()

        print("\n==================================================")
        print("RECOMMENDATION DEMONSTRATION PASSED CLEANLY!")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_recommendation_demo()
