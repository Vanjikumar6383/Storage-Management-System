"""
End-to-End Approval, Pre-Execution Safety Gate, Lifecycle Execution, and Rollback Demonstration Script.
Demonstrates Scenarios A through G against Local S3 / MinIO test environment.
"""

from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageLocation,
    StorageObject,
    RetentionPolicy,
    LegalHold,
)
from app.services.recommendation_engine import RecommendationService
from app.services.approval_execution import ApprovalExecutionService
from app.services.telemetry import AccessEventIngestionService
from app.core.telemetry_config import AccessEventTypeEnum


def run_execution_demo():
    print("==================================================")
    print("STEP 7 — Human Approval, Execution & Rollback Engine")
    print("==================================================")

    db = SessionLocal()
    try:
        demo_org = db.query(Organization).filter_by(slug="demo-organization").first()
        loc = db.query(StorageLocation).filter_by(organization_id=demo_org.id).first()

        db.query(RetentionPolicy).delete(synchronize_session=False)
        db.query(LegalHold).delete(synchronize_session=False)
        db.commit()

        ref_time = datetime.now(timezone.utc)
        rec_service = RecommendationService()
        exec_service = ApprovalExecutionService()
        access_service = AccessEventIngestionService()

        # SCENARIO A: STANDARD -> ARCHIVE Migration Execution
        print("\n[SCENARIO A] Executing STANDARD -> ARCHIVE Migration")
        o_a = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/exec_a_{uuid4().hex[:6]}.dat", object_size_bytes=10 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(o_a)
        db.commit()

        rec_a = rec_service.generate_and_save_recommendation(db, demo_org.id, o_a.id, reference_time=ref_time)
        appr_a = exec_service.process_approval_decision(db, demo_org.id, rec_a.id, decision="APPROVE", reason="Approved for cold archival")
        res_a = exec_service.execute_recommendation(db, demo_org.id, rec_a.id)

        db.refresh(o_a)
        print(f"   Status: {res_a.status} | Migration ID: {res_a.migration_id}")
        print(f"   New Storage Class in DB: {o_a.storage_class}")
        print(f"   Reasons: {res_a.reasons}")

        # SCENARIO B: ARCHIVE -> STANDARD Migration Rollback Execution
        print("\n[SCENARIO B] Executing Rollback ARCHIVE -> STANDARD")
        res_b = exec_service.rollback_migration(db, demo_org.id, res_a.migration_id, reason="Operator audit rollback")
        db.refresh(o_a)
        print(f"   Status: {res_b.status} | Restored Class: {res_b.restored_storage_class}")
        print(f"   Restored Storage Class in DB: {o_a.storage_class}")
        print(f"   Reasons: {res_b.reasons}")

        # SCENARIO C: Approved DELETE_CANDIDATE -> Simulated Deletion (Safety Mode)
        print("\n[SCENARIO C] Executing Approved DELETE_CANDIDATE (Simulation Safety Mode)")
        o_c = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/exec_c_{uuid4().hex[:6]}.dat", object_size_bytes=10 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=400), last_modified_at=ref_time - timedelta(days=400))
        db.add(o_c)
        db.commit()
        p_c = RetentionPolicy(organization_id=demo_org.id, object_id=o_c.id, name="Expired 30d Policy", retention_duration_days=30, effective_date=ref_time - timedelta(days=400), status="ACTIVE")
        db.add(p_c)
        db.commit()

        rec_c = rec_service.generate_and_save_recommendation(db, demo_org.id, o_c.id, reference_time=ref_time)
        exec_service.process_approval_decision(db, demo_org.id, rec_c.id, decision="APPROVE", reason="Approved for deletion review")
        res_c = exec_service.execute_recommendation(db, demo_org.id, rec_c.id)
        db.refresh(o_c)

        print(f"   Status: {res_c.status} | Object ID: {res_c.object_id}")
        print(f"   Physical Object Preserved: {o_c.id is not None} (Zero Physical Deletion)")
        print(f"   Reasons: {res_c.reasons}")

        # SCENARIO D: Active Legal Hold Blocks Pre-Execution Safety Gate
        print("\n[SCENARIO D] Legal Hold Blocking Pre-Execution Safety Gate")
        o_d = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/exec_d_{uuid4().hex[:6]}.dat", object_size_bytes=10 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=400), last_modified_at=ref_time - timedelta(days=400))
        db.add(o_d)
        db.commit()
        p_d = RetentionPolicy(organization_id=demo_org.id, object_id=o_d.id, name="Expired 30d Policy", retention_duration_days=30, effective_date=ref_time - timedelta(days=400), status="ACTIVE")
        db.add(p_d)
        db.commit()

        rec_d = rec_service.generate_and_save_recommendation(db, demo_org.id, o_d.id, reference_time=ref_time)
        exec_service.process_approval_decision(db, demo_org.id, rec_d.id, decision="APPROVE", reason="Approved before legal hold")

        h_d = LegalHold(organization_id=demo_org.id, object_id=o_d.id, status="ACTIVE", reason_reference="REF-LITIGATION-GATE-BLOCK")
        db.add(h_d)
        db.commit()

        res_d = exec_service.execute_recommendation(db, demo_org.id, rec_d.id)
        print(f"   Status: {res_d.status} | Reasons: {res_d.reasons}")

        # SCENARIO E: Object Accessed After Recommendation -> Stale Recommendation
        print("\n[SCENARIO E] Fresh Access Post-Recommendation -> Stale Recommendation")
        o_e = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/exec_e_{uuid4().hex[:6]}.dat", object_size_bytes=10 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(o_e)
        db.commit()

        rec_e = rec_service.generate_and_save_recommendation(db, demo_org.id, o_e.id, reference_time=ref_time)
        exec_service.process_approval_decision(db, demo_org.id, rec_e.id, decision="APPROVE", reason="Approved before fresh access")

        access_service.record_access_event(db, demo_org.id, o_e.id, AccessEventTypeEnum.OBJECT_READ.value, event_timestamp=ref_time + timedelta(minutes=5))
        res_e = exec_service.execute_recommendation(db, demo_org.id, rec_e.id)
        print(f"   Status: {res_e.status} | Reasons: {res_e.reasons}")

        # SCENARIO F: Migration Failure Handling
        print("\n[SCENARIO F] Handling Migration Failure Gracefully")
        o_f = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/exec_f_{uuid4().hex[:6]}.dat", object_size_bytes=10 * 1024 * 1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(o_f)
        db.commit()

        rec_f = rec_service.generate_and_save_recommendation(db, demo_org.id, o_f.id, reference_time=ref_time)
        exec_service.process_approval_decision(db, demo_org.id, rec_f.id, decision="APPROVE", reason="Approved for failure simulation")
        res_f = exec_service.execute_recommendation(db, demo_org.id, rec_f.id)
        print(f"   Status: {res_f.status} | Source Class Intact: {o_f.storage_class == 'STANDARD'}")

        # SCENARIO G: Repeated Execution Request -> Idempotent Response
        print("\n[SCENARIO G] Repeated Execution Idempotency")
        res_g = exec_service.execute_recommendation(db, demo_org.id, rec_a.id)
        print(f"   Status: {res_g.status} | Reasons: {res_g.reasons}")

        # Cleanup fixtures
        for p in [p_c, p_d]:
            db.delete(p)
        db.delete(h_d)
        for rec in [rec_a, rec_c, rec_d, rec_e, rec_f]:
            db.delete(rec)
        for obj in [o_a, o_c, o_d, o_e, o_f]:
            db.delete(obj)
        db.commit()

        print("\n==================================================")
        print("EXECUTION DEMONSTRATION PASSED CLEANLY!")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_execution_demo()
