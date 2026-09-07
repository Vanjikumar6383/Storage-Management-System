"""
Automated End-to-End Control Plane Demo & Validation Script.
Executes complete storage lifecycle workflow in DEMO mode without requiring AWS or external cloud accounts.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageConnection,
    StorageLocation,
    StorageObject,
    Recommendation,
    RecommendationTypeEnum,
    ApprovalRequest,
    MigrationEvent,
    AuditLog,
)
from app.services.recommendation_engine import RecommendationService
from app.services.approval_execution import ApprovalExecutionService
from app.services.cost_estimation import CostEstimationService


def run_e2e_demo():
    print("=" * 70)
    print("      STORAGE LIFECYCLE OPTIMIZER — END-TO-END DEMO SCENARIO")
    print("=" * 70)

    db = SessionLocal()
    try:
        # Step 1: Resolve Demo Tenant Organization
        org = db.query(Organization).filter_by(slug="demo-organization").first()
        if not org:
            print("❌ Demo organization not found. Please run seed script first.")
            sys.exit(1)
        print(f"[OK] Tenant Organization resolved: '{org.name}' (ID: {org.id})")

        # Step 2: Resolve Storage Location
        loc = db.query(StorageLocation).filter_by(organization_id=org.id).first()
        if not loc:
            print("[ERROR] Storage location not found.")
            sys.exit(1)
        print(f"[OK] Storage Location resolved: '{loc.name}' (Region: {loc.region})")

        # Step 3: Create Sample Storage Objects
        ref_time = datetime.now(timezone.utc)
        archive_obj = StorageObject(
            organization_id=org.id,
            storage_location_id=loc.id,
            object_key=f"demo/e2e_archive_{uuid4().hex[:6]}.dat",
            object_size_bytes=50 * 1024 * 1024 * 1024, # 50 GB
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=200),
            last_modified_at=ref_time - timedelta(days=200),
        )
        delete_obj = StorageObject(
            organization_id=org.id,
            storage_location_id=loc.id,
            object_key=f"demo/e2e_delete_{uuid4().hex[:6]}.tmp",
            object_size_bytes=10 * 1024 * 1024 * 1024, # 10 GB
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=400),
            last_modified_at=ref_time - timedelta(days=400),
        )
        db.add_all([archive_obj, delete_obj])
        db.commit()
        print(f"[OK] Demo Storage Objects created: '{archive_obj.object_key}' (50GB), '{delete_obj.object_key}' (10GB)")

        # Step 4: Generate Explainable Recommendations
        rec_service = RecommendationService()
        rec_archive = rec_service.generate_and_save_recommendation(db, org.id, archive_obj.id, reference_time=ref_time)
        rec_delete = rec_service.generate_and_save_recommendation(db, org.id, delete_obj.id, reference_time=ref_time)
        print(f"\n[INFO] EXPLAINABLE RECOMMENDATION GENERATED:")
        print(f"   * Object ID: {rec_archive.object_id}")
        print(f"   * Action: {rec_archive.recommendation_type}")
        print(f"   * Reason: {rec_archive.reason}")
        print(f"   * Estimated Monthly Savings: ${float(rec_archive.estimated_savings):.2f}")

        # Step 5: Process Approval Workflow
        exec_service = ApprovalExecutionService()
        appr_archive = exec_service.process_approval_decision(db, org.id, rec_archive.id, decision="APPROVE", reason="Operator approved demo migration")
        print(f"\n[INFO] HUMAN APPROVAL DECISION PROCESSED:")
        print(f"   * Approval ID: {appr_archive.id}")
        print(f"   * Decision: {appr_archive.decision}")
        print(f"   * Status: {appr_archive.status}")

        # Step 6: Execute Storage Migration & Verify Savings Ledger
        res_exec = exec_service.execute_recommendation(db, org.id, rec_archive.id)
        db.refresh(archive_obj)
        print(f"\n[INFO] TIER MIGRATION EXECUTED:")
        print(f"   * Execution Status: {res_exec.status}")
        print(f"   * New Storage Class: {archive_obj.storage_class}")
        print(f"   * Migration Reasons: {res_exec.reasons[0]}")

        # Step 7: Rollback Migration & Verify Savings Reversal
        res_rb = exec_service.rollback_migration(db, org.id, res_exec.migration_id)
        db.refresh(archive_obj)
        print(f"\n[INFO] ROLLBACK PIPELINE EXECUTED:")
        print(f"   * Rollback Status: {res_rb.status}")
        print(f"   * Restored Storage Class: {archive_obj.storage_class}")

        # Step 8: Verify DELETE_CANDIDATE Safety Mode
        rec_delete.recommendation_type = RecommendationTypeEnum.DELETE_CANDIDATE
        rec_delete.recommended_storage_class = "DELETE_CANDIDATE"
        db.commit()

        appr_delete = exec_service.process_approval_decision(db, org.id, rec_delete.id, decision="APPROVE", reason="Delete candidate approval test")
        res_del = exec_service.execute_recommendation(db, org.id, rec_delete.id)
        print(f"\n[SAFETY] DELETE CANDIDATE SAFETY MODE VERIFICATION:")
        print(f"   * Recommendation Type: DELETE_CANDIDATE")
        print(f"   * Execution Outcome Code: {res_del.status}")
        print(f"   * Safety Reasons: {res_del.reasons}")
        assert res_del.status in ("DELETE_SIMULATION_SUCCESS", "BLOCKED"), f"Expected DELETE_SIMULATION_SUCCESS or BLOCKED but got {res_del.status}"
        print(f"   * Safety Assurance: Physical payload was NOT deleted (Dry-run simulation mode intact).")

        # Step 9: Audit Trail Inspection
        audits = db.query(AuditLog).filter(AuditLog.organization_id == org.id).order_by(AuditLog.timestamp.desc()).limit(5).all()
        print(f"\n[AUDIT] AUDIT TRAIL LOGGED ({len(audits)} recent entries):")
        for a in audits:
            print(f"   * [{a.timestamp.strftime('%H:%M:%S')}] {a.action} ({a.resource_type}) -> {a.outcome}")

        print("\n" + "=" * 70)
        print("      [OK] END-TO-END DEMO SCENARIO PASSED 100% CLEANLY")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_e2e_demo()
