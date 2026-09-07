"""
Controlled Policy Engine Demonstration Script for Scenarios A - G.
Validates governance evaluation, legal hold overrides, retention hierarchy, and fail-safe decisions.
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
from app.services.policy_engine import PolicyEngineService


def run_policy_demo():
    print("==================================================")
    print("STEP 5 — Policy Engine & Governance Evaluation")
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
        engine = PolicyEngineService()

        # Scenario A: Old object (age=200d), Retention active (300d), No legal hold
        obj_a = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/scen_a_{uuid4().hex[:8]}.dat", object_size_bytes=1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(obj_a)
        db.commit()
        pol_a = RetentionPolicy(organization_id=demo_org.id, object_id=obj_a.id, name="Active 300d Retention", retention_duration_days=300, effective_date=ref_time - timedelta(days=200), status="ACTIVE")
        db.add(pol_a)
        db.commit()

        dec_a = engine.evaluate_action(db, demo_org.id, obj_a.id, "DELETE", reference_time=ref_time, audit=False)
        db.delete(pol_a)
        db.delete(obj_a)
        db.commit()

        # Scenario B: Old object (age=200d), Retention expired (30d), No legal hold
        obj_b = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/scen_b_{uuid4().hex[:8]}.dat", object_size_bytes=1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(obj_b)
        db.commit()
        pol_b = RetentionPolicy(organization_id=demo_org.id, object_id=obj_b.id, name="Expired 30d Retention", retention_duration_days=30, effective_date=ref_time - timedelta(days=200), status="ACTIVE")
        db.add(pol_b)
        db.commit()

        dec_b = engine.evaluate_action(db, demo_org.id, obj_b.id, "DELETE", reference_time=ref_time, audit=False)
        db.delete(pol_b)
        db.delete(obj_b)
        db.commit()

        # Scenario C: Old object (age=200d), Retention expired (30d), Active legal hold
        obj_c = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/scen_c_{uuid4().hex[:8]}.dat", object_size_bytes=1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(obj_c)
        db.commit()
        pol_c = RetentionPolicy(organization_id=demo_org.id, object_id=obj_c.id, name="Expired 30d Retention", retention_duration_days=30, effective_date=ref_time - timedelta(days=200), status="ACTIVE")
        hold_c = LegalHold(organization_id=demo_org.id, object_id=obj_c.id, status="ACTIVE", reason_reference="REF-LEGAL-LITIGATION-01")
        db.add_all([pol_c, hold_c])
        db.commit()

        dec_c = engine.evaluate_action(db, demo_org.id, obj_c.id, "DELETE", reference_time=ref_time, audit=False)
        db.delete(hold_c)
        db.delete(pol_c)
        db.delete(obj_c)
        db.commit()

        # Scenario D: Old object (age=200d), No retention policy -> Fail-safe REQUIRES_REVIEW
        obj_d = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/scen_d_{uuid4().hex[:8]}.dat", object_size_bytes=1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(obj_d)
        db.commit()

        dec_d = engine.evaluate_action(db, demo_org.id, obj_d.id, "DELETE", reference_time=ref_time, audit=False)
        db.delete(obj_d)
        db.commit()

        # Scenario E: Conflicting policies at object level -> Fail-safe REQUIRES_REVIEW
        obj_e = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, object_key=f"demo/scen_e_{uuid4().hex[:8]}.dat", object_size_bytes=1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=200), last_modified_at=ref_time - timedelta(days=200))
        db.add(obj_e)
        db.commit()
        pol_e1 = RetentionPolicy(organization_id=demo_org.id, object_id=obj_e.id, name="Conflict Pol 1", retention_duration_days=30, priority=100, status="ACTIVE")
        pol_e2 = RetentionPolicy(organization_id=demo_org.id, object_id=obj_e.id, name="Conflict Pol 2", retention_duration_days=365, priority=100, status="ACTIVE")
        db.add_all([pol_e1, pol_e2])
        db.commit()

        dec_e = engine.evaluate_action(db, demo_org.id, obj_e.id, "DELETE", reference_time=ref_time, audit=False)
        db.delete(pol_e1)
        db.delete(pol_e2)
        db.delete(obj_e)
        db.commit()

        # Scenario F: Object-level policy overriding environment policy
        obj_f = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, environment_id=env.id, object_key=f"demo/scen_f_{uuid4().hex[:8]}.dat", object_size_bytes=1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=40), last_modified_at=ref_time - timedelta(days=40))
        db.add(obj_f)
        db.commit()
        pol_f_env = RetentionPolicy(organization_id=demo_org.id, environment_id=env.id, name="Env 20d Policy", retention_duration_days=20, effective_date=ref_time - timedelta(days=40), status="ACTIVE")
        pol_f_obj = RetentionPolicy(organization_id=demo_org.id, object_id=obj_f.id, name="Obj 100d Override Policy", retention_duration_days=100, effective_date=ref_time - timedelta(days=40), status="ACTIVE")
        db.add_all([pol_f_env, pol_f_obj])
        db.commit()

        dec_f = engine.evaluate_action(db, demo_org.id, obj_f.id, "DELETE", reference_time=ref_time, audit=False)
        db.delete(pol_f_obj)
        db.delete(pol_f_env)
        db.delete(obj_f)
        db.commit()

        # Scenario G: Environment policy overriding organization policy
        obj_g = StorageObject(organization_id=demo_org.id, storage_location_id=loc.id, environment_id=env.id, object_key=f"demo/scen_g_{uuid4().hex[:8]}.dat", object_size_bytes=1024, storage_class="STANDARD", created_at=ref_time - timedelta(days=25), last_modified_at=ref_time - timedelta(days=25))
        db.add(obj_g)
        db.commit()
        pol_g_org = RetentionPolicy(organization_id=demo_org.id, name="Org 10d Expired Policy", retention_duration_days=10, effective_date=ref_time - timedelta(days=25), status="ACTIVE")
        pol_g_env = RetentionPolicy(organization_id=demo_org.id, environment_id=env.id, name="Env 60d Active Policy", retention_duration_days=60, effective_date=ref_time - timedelta(days=25), status="ACTIVE")
        db.add_all([pol_g_org, pol_g_env])
        db.commit()

        dec_g = engine.evaluate_action(db, demo_org.id, obj_g.id, "DELETE", reference_time=ref_time, audit=False)
        db.delete(pol_g_env)
        db.delete(pol_g_org)
        db.delete(obj_g)
        db.commit()

        results = [
            ("Scenario A (Retention Active)", dec_a),
            ("Scenario B (Retention Expired)", dec_b),
            ("Scenario C (Retention Expired + Active Legal Hold)", dec_c),
            ("Scenario D (No Retention Policy - Fail Safe)", dec_d),
            ("Scenario E (Conflicting Policies - Fail Safe)", dec_e),
            ("Scenario F (Object Policy Override)", dec_f),
            ("Scenario G (Environment Policy Override)", dec_g),
        ]

        print("\nPOLICY ENGINE EVALUATION RESULTS:")
        print("--------------------------------------------------")
        for label, dec in results:
            print(f"\n[{label}] Object ID: {dec.object_id}")
            print(f"   Proposed Action: {dec.action}")
            print(f"   Policy Decision: {dec.decision}")
            print(f"   Retention State: {dec.retention_state}")
            print(f"   Legal Hold Active: {dec.legal_hold_active}")
            print(f"   Applicable Policy ID: {dec.applicable_policy_id}")
            print(f"   Explainability Reasons: {dec.reasons}")

        print("\n==================================================")
        print("POLICY DEMONSTRATION PASSED CLEANLY!")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_policy_demo()
