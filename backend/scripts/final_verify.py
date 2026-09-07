"""
Final Release Verification Script for Storage Lifecycle Optimizer.
Executes 10-point health and release verification suite without requiring external cloud accounts.
"""

import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app
from app.core.config import get_storage_settings, get_app_config
from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageLocation,
    StorageObject,
    RetentionPolicy,
    Recommendation,
    RecommendationTypeEnum,
)
from app.services.recommendation_engine import RecommendationService
from app.services.approval_execution import ApprovalExecutionService
from app.services.cost_estimation import CostEstimationService
from sqlalchemy import text


def run_final_verification():
    print("=" * 70)
    print("    STORAGE LIFECYCLE OPTIMIZER — FINAL RELEASE VERIFICATION")
    print("=" * 70)

    client = TestClient(app)

    # Check 1: App Configuration Loading
    app_cfg = get_app_config()
    print(f"[1/10] App Configuration: PASSED (Env: {app_cfg.app_env})")

    # Check 2: Database Connection
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        print("[2/10] PostgreSQL Database Connection: PASSED")
    except Exception as err:
        print(f"[FAIL] Database Connection: FAILED ({err})")
        sys.exit(1)

    # Check 3: Demo Storage Mode Config
    storage_cfg = get_storage_settings()
    assert storage_cfg.provider == "LOCAL_S3_COMPATIBLE", "Storage provider is not LOCAL_S3_COMPATIBLE"
    print(f"[3/10] Demo Storage Configuration: PASSED (Provider: {storage_cfg.provider})")

    # Check 4: Liveness & Readiness Endpoints
    r_live = client.get("/health/liveness")
    r_ready = client.get("/health/readiness")
    assert r_live.status_code == 200 and r_ready.status_code == 200, "Health endpoints failed!"
    print("[4/10] API Liveness & Readiness Endpoints: PASSED")

    # Check 5: Resolve Demo Organization & Location
    org = db.query(Organization).filter_by(slug="demo-organization").first()
    loc = db.query(StorageLocation).filter_by(organization_id=org.id).first()
    assert org is not None and loc is not None, "Demo organization/location missing!"
    print(f"[5/10] Tenant Organization Resolution: PASSED (Org: '{org.name}')")

    # Check 6: Recommendation Engine Evaluation
    ref_time = datetime.now(timezone.utc)
    test_obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"verify/test_{uuid4().hex[:6]}.dat",
        object_size_bytes=10 * 1024 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db.add(test_obj)
    db.commit()

    rec_service = RecommendationService()
    rec = rec_service.generate_and_save_recommendation(db, org.id, test_obj.id, reference_time=ref_time)
    assert rec is not None and rec.recommendation_type == RecommendationTypeEnum.ARCHIVE, "Recommendation engine failed!"
    print(f"[6/10] Explainable Recommendation Engine: PASSED (Action: {rec.recommendation_type.value})")

    # Check 7: Approval Workflow Processing
    exec_service = ApprovalExecutionService()
    appr = exec_service.process_approval_decision(db, org.id, rec.id, decision="APPROVE", reason="Verification run")
    assert appr.status == "APPROVED", "Approval workflow failed!"
    print("[7/10] Human Approval Workflow Engine: PASSED")

    # Check 8: Migration Execution & Rollback Pipeline
    exec_res = exec_service.execute_recommendation(db, org.id, rec.id)
    assert exec_res.status == "SUCCESS", "Migration execution failed!"
    db.refresh(test_obj)
    assert test_obj.storage_class == "ARCHIVE", "Object class was not updated to ARCHIVE!"

    rb_res = exec_service.rollback_migration(db, org.id, exec_res.migration_id, reason="Verification rollback")
    assert rb_res.status == "SUCCESS", "Rollback execution failed!"
    db.refresh(test_obj)
    assert test_obj.storage_class == "STANDARD", "Object class was not restored to STANDARD!"
    print("[8/10] Safe Storage Migration & Rollback Pipeline: PASSED")

    # Check 9: Cost & Savings Estimation
    cost_service = CostEstimationService()
    est = cost_service.calculate_savings(test_obj.object_size_bytes, "STANDARD", "ARCHIVE")
    assert est.current_monthly_cost_usd > 0 and est.estimated_monthly_savings_usd > 0, "Cost estimation failed!"
    print(f"[9/10] Cost & Savings Engine: PASSED (Current: ${est.current_monthly_cost_usd:.2f}/mo, Savings: ${est.estimated_monthly_savings_usd:.2f}/mo)")

    # Check 10: Delete Candidate Simulation Safety Assurance
    rec_del = Recommendation(
        organization_id=org.id,
        object_id=test_obj.id,
        recommendation_type=RecommendationTypeEnum.DELETE_CANDIDATE,
        current_storage_class="STANDARD",
        recommended_storage_class="DELETE_CANDIDATE",
        reason="Verification delete safety check",
        risk_level="HIGH",
        status="APPROVED",
    )
    db.add(rec_del)
    db.commit()

    pol = RetentionPolicy(
        organization_id=org.id,
        object_id=test_obj.id,
        name="Expired Retention Policy for Verification",
        retention_duration_days=30,
        effective_date=ref_time - timedelta(days=400),
        status="ACTIVE",
    )
    db.add(pol)
    db.commit()

    appr_del = exec_service.create_or_get_approval_request(db, org.id, rec_del.id)
    appr_del.status = "APPROVED"
    db.commit()

    try:
        res_del = exec_service.execute_recommendation(db, org.id, rec_del.id)
        assert res_del.status == "DELETE_SIMULATION_SUCCESS", f"Expected DELETE_SIMULATION_SUCCESS but got {res_del.status}"
        print("[10/10] Delete Candidate Safety Mode Assurance: PASSED (Physical payload protected)")
    finally:
        db.delete(pol)
        db.delete(rec_del)
        db.delete(rec)
        db.delete(test_obj)
        db.commit()
        db.close()

    print("=" * 70)
    print("    [SUCCESS] ALL 10 RELEASE VERIFICATION CHECKS PASSED CLEANLY")
    print("=" * 70)


if __name__ == "__main__":
    run_final_verification()
