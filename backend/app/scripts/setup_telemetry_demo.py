"""
Controlled Telemetry Demonstration Script for Scenarios A, B, C, D, E.
Populates test evidence profiles without real-world personal data.
"""

from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.models import Organization, StorageLocation, StorageObject
from app.services.telemetry import (
    AccessEventIngestionService,
    RestoreEventService,
    ObjectUsageProfileService,
)
from app.core.telemetry_config import AccessEventTypeEnum, RestoreStatusEnum


def run_telemetry_demo():
    print("==================================================")
    print("STEP 4 — Telemetry & Object Usage Profile Validation")
    print("==================================================")

    db = SessionLocal()
    try:
        demo_org = db.query(Organization).filter_by(slug="demo-organization").first()
        loc = db.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

        ref_time = datetime.now(timezone.utc)
        access_service = AccessEventIngestionService()
        restore_service = RestoreEventService()
        profile_service = ObjectUsageProfileService()

        # Scenario A: Age=200d, Accesses 90d=0, Restores 90d=0
        obj_a = StorageObject(
            organization_id=demo_org.id,
            storage_location_id=loc.id,
            object_key="demo/scenario_a_old_unused.dat",
            object_size_bytes=1048576,
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=200),
            last_modified_at=ref_time - timedelta(days=200),
        )
        db.add(obj_a)
        db.commit()

        # Scenario B: Age=200d, Accesses 90d=25 (all in last 30d)
        obj_b = StorageObject(
            organization_id=demo_org.id,
            storage_location_id=loc.id,
            object_key="demo/scenario_b_old_frequent.dat",
            object_size_bytes=2048576,
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=200),
            last_modified_at=ref_time - timedelta(days=200),
        )
        db.add(obj_b)
        db.commit()
        for i in range(25):
            access_service.record_access_event(
                db, demo_org.id, obj_b.id, AccessEventTypeEnum.OBJECT_READ.value, ref_time - timedelta(days=5)
            )

        # Scenario C: Age=200d, Accesses 90d=0, Restores 90d=5 (high restore risk)
        obj_c = StorageObject(
            organization_id=demo_org.id,
            storage_location_id=loc.id,
            object_key="demo/scenario_c_restore_heavy.dat",
            object_size_bytes=5242880,
            storage_class="GLACIER",
            created_at=ref_time - timedelta(days=200),
            last_modified_at=ref_time - timedelta(days=200),
        )
        db.add(obj_c)
        db.commit()
        for i in range(5):
            restore_service.record_restore_event(
                db, demo_org.id, obj_c.id, "GLACIER", "STANDARD", ref_time - timedelta(days=10), status=RestoreStatusEnum.SUCCEEDED.value
            )

        # Scenario D: Age=20d, Accesses 30d=10
        obj_d = StorageObject(
            organization_id=demo_org.id,
            storage_location_id=loc.id,
            object_key="demo/scenario_d_recent_medium.dat",
            object_size_bytes=4096,
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=20),
            last_modified_at=ref_time - timedelta(days=20),
        )
        db.add(obj_d)
        db.commit()
        for i in range(10):
            access_service.record_access_event(
                db, demo_org.id, obj_d.id, AccessEventTypeEnum.OBJECT_READ.value, ref_time - timedelta(days=2)
            )

        # Scenario E: Age=300d, No access events, No restore events
        obj_e = StorageObject(
            organization_id=demo_org.id,
            storage_location_id=loc.id,
            object_key="demo/scenario_e_cold_orphan.dat",
            object_size_bytes=10485760,
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=300),
            last_modified_at=ref_time - timedelta(days=300),
        )
        db.add(obj_e)
        db.commit()

        # Build Profiles
        scenarios = [("Scenario A", obj_a), ("Scenario B", obj_b), ("Scenario C", obj_c), ("Scenario D", obj_d), ("Scenario E", obj_e)]

        print("\nGENERATED EVIDENCE USAGE PROFILES:")
        print("--------------------------------------------------")
        for label, obj in scenarios:
            prof = profile_service.build_usage_profile(db, demo_org.id, obj.id, reference_time=ref_time)
            print(f"\n[{label}] Object Key: {prof.object_key}")
            print(f"   Age: {prof.age_days} days | Size: {prof.object_size_bytes} bytes | Storage Class: {prof.storage_class}")
            print(f"   Accesses (30d/90d/180d): {prof.accesses_30d} / {prof.accesses_90d} / {prof.accesses_180d}")
            print(f"   Access Frequency Category: {prof.access_frequency}")
            print(f"   Restores (30d/90d/180d): {prof.restores_30d} / {prof.restores_90d} / {prof.restores_180d}")
            print(f"   Restore Success Rate: {prof.restore_success_rate * 100:.0f}%")
            print(f"   Restore Risk Category: {prof.restore_risk}")
            print(f"   Explainability Evidence: {prof.risk_explainability}")

        # Cleanup demo objects
        for _, obj in scenarios:
            db.delete(obj)
        db.commit()

        print("\n==================================================")
        print("TELEMETRY DEMONSTRATION PASSED CLEANLY!")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_telemetry_demo()
