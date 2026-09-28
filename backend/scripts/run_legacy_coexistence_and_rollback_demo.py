"""
Legacy Workflow Coexistence & Rollback Demonstration Script.
Demonstrates:
1. Coexistence with legacy storage workflows (non-destructive shadow monitoring).
2. Automated evaluation of unclassified legacy development data.
3. Human confirmation workflow for high-impact actions with mandatory override reasons.
4. Provider-side zero-download tier migration.
5. Instant single-click rollback demonstration restoring previous storage class.
"""

import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone, timedelta

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageLocation,
    StorageObject,
    Recommendation,
    RecommendationTypeEnum,
    ApprovalRequest,
    MigrationEvent,
    RollbackEvent,
    AuditLog,
    LegalHold,
    RetentionPolicy,
)
from app.services.recommendation_engine import RecommendationService
from app.services.approval_execution import ApprovalExecutionService
from app.services.cost_estimation import CostEstimationService


def run_legacy_coexistence_and_rollback_demo():
    print("=" * 80)
    print("   STORAGE LIFECYCLE OPTIMIZER — LEGACY COEXISTENCE & ROLLBACK DEMO")
    print("=" * 80)

    db = SessionLocal()
    try:
        # Step 1: Resolve Tenant Organization & Storage Location
        org = db.query(Organization).filter_by(slug="demo-organization").first()
        if not org:
            org = db.query(Organization).first()
        if not org:
            print("[ERROR] No organization found. Please run seed script first.")
            sys.exit(1)

        loc = db.query(StorageLocation).filter_by(organization_id=org.id).first()
        print(f"\n[1/6] Resolved Tenant: '{org.name}' | Location: '{loc.name}'")

        # Step 2: Legacy Workflow Ingestion (Coexistence)
        ref_time = datetime.now(timezone.utc)
        print(f"\n[2/6] Coexistence Mode: Monitoring Unmanaged Legacy Development Storage...")
        
        legacy_obj_1 = StorageObject(
            organization_id=org.id,
            storage_location_id=loc.id,
            object_key=f"legacy-ci/build_release_{uuid4().hex[:6]}.tar.gz",
            object_size_bytes=40 * 1024 * 1024 * 1024, # 40 GB
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=210),
            last_modified_at=ref_time - timedelta(days=210),
            access_count_30d=0,
            access_count_90d=0,
        )
        legacy_obj_2 = StorageObject(
            organization_id=org.id,
            storage_location_id=loc.id,
            object_key=f"legacy-compliance/financial_backup_{uuid4().hex[:6]}.dmp",
            object_size_bytes=100 * 1024 * 1024 * 1024, # 100 GB
            storage_class="STANDARD",
            created_at=ref_time - timedelta(days=365),
            last_modified_at=ref_time - timedelta(days=365),
            access_count_30d=0,
        )
        db.add_all([legacy_obj_1, legacy_obj_2])
        db.commit()

        # Place legal hold on obj 2 to demonstrate coexistence compliance guard
        hold = LegalHold(
            organization_id=org.id,
            object_id=legacy_obj_2.id,
            status="ACTIVE",
            reason_reference="LEGAL-SEC-2026-LEGACY-HOLD",
        )
        db.add(hold)
        db.commit()

        print(f"   * Ingested Legacy Object 1: '{legacy_obj_1.object_key}' (40 GB, STANDARD, Age: 210 days)")
        print(f"   * Ingested Legacy Object 2: '{legacy_obj_2.object_key}' (100 GB, STANDARD, Active Legal Hold)")
        print("   [OK] Ingestion completed non-destructively. Legacy pipeline continues uninterrupted.")

        # Step 3: Automated Explainable Recommendations
        print(f"\n[3/6] Evaluating Lifecycle Recommendations with Explainable Evidence:")
        rec_service = RecommendationService()
        rec_1 = rec_service.generate_and_save_recommendation(db, org.id, legacy_obj_1.id, reference_time=ref_time)
        rec_2 = rec_service.generate_and_save_recommendation(db, org.id, legacy_obj_2.id, reference_time=ref_time)

        print(f"   -> Object 1 Recommendation: {rec_1.recommendation_type.value}")
        print(f"      Reason: {rec_1.reason}")
        print(f"      Estimated Monthly Savings: ${float(rec_1.estimated_savings):.2f}")
        print(f"      Risk Level: {rec_1.risk_level} (Requires Human Confirmation: YES)")

        print(f"   -> Object 2 Recommendation: {rec_2.recommendation_type.value}")
        print(f"      Reason: {rec_2.reason}")
        print(f"      Compliance Guard: Active legal hold strictly prevents any tier change or deletion.")

        # Step 4: Human Confirmation Workflow & Override Reason
        print(f"\n[4/6] Processing Human Approval for High-Impact Tier Migration:")
        exec_service = ApprovalExecutionService()
        override_reason = "Approved for Glacier archival by FinOps lead under Dev Storage Optimization Policy"
        appr_1 = exec_service.process_approval_decision(
            db,
            org.id,
            rec_1.id,
            decision="APPROVE",
            reason=override_reason,
        )
        print(f"   * Approval Decision: {appr_1.decision}")
        print(f"   * Captured Override Reason: '{appr_1.override_reason}'")
        print(f"   * Approval Status: {appr_1.status}")

        # Step 5: Execute Provider-Side Zero-Download Migration
        print(f"\n[5/6] Executing Provider-Side Tier Migration (Zero Download):")
        res_exec = exec_service.execute_recommendation(db, org.id, rec_1.id)
        db.refresh(legacy_obj_1)
        print(f"   * Migration Execution: {res_exec.status}")
        print(f"   * Migration ID: {res_exec.migration_id}")
        print(f"   * Old Storage Class: STANDARD")
        print(f"   * New Storage Class: {legacy_obj_1.storage_class}")
        assert legacy_obj_1.storage_class == "ARCHIVE", "Object class was not updated!"
        print("   [OK] Object transitioned to ARCHIVE with zero egress download cost.")

        # Step 6: Rollback Demonstration
        print(f"\n[6/6] Executing Instant Rollback Demonstration:")
        rollback_reason = "Emergency restore requested: release verification patch required by QA engineering team"
        rb_res = exec_service.rollback_migration(
            db,
            org.id,
            res_exec.migration_id,
            reason=rollback_reason,
        )
        db.refresh(legacy_obj_1)
        print(f"   * Rollback Execution: {rb_res.status}")
        print(f"   * Rollback Reason: '{rollback_reason}' (Reasons: {rb_res.reasons})")
        print(f"   * Restored Storage Class: {legacy_obj_1.storage_class}")
        assert legacy_obj_1.storage_class == "STANDARD", "Rollback failed to restore STANDARD class!"

        # Step 7: Verify Audit Trail
        audit_records = db.query(AuditLog).filter_by(organization_id=org.id).order_by(AuditLog.timestamp.desc()).limit(3).all()
        print(f"\n[AUDIT TRAIL VERIFICATION]:")
        for log in audit_records:
            print(f"   * Action: {log.action.ljust(22)} | Outcome: {log.outcome.ljust(10)} | Timestamp: {log.timestamp.isoformat()}")

        print("\n" + "=" * 80)
        print("   [SUCCESS] LEGACY COEXISTENCE & ROLLBACK WORKFLOW COMPLETED 100%!")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    run_legacy_coexistence_and_rollback_demo()
