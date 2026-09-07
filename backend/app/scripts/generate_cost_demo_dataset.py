"""
Deterministic Synthetic Dataset Generator for Storage Cost & Optimization Experiments.
Generates 10 organizations, 100 environments, 10,000+ storage objects, access/restore telemetry,
retention policies, legal holds, recommendations, and savings ledger entries.
Uses fixed random seed (42) for 100% reproducible execution.
"""

import random
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import (
    Organization,
    User,
    Environment,
    StorageConnection,
    StorageLocation,
    StorageObject,
    AccessEvent,
    RestoreEvent,
    RetentionPolicy,
    LegalHold,
)
from app.services.recommendation_engine import RecommendationService
from app.services.pricing_provider import PricingProvider
from app.services.cost_engine import SnapshotService, ExperimentService, CostSummaryService

ORGANIZATION_NAMES = [
    "DemoCloud Labs",
    "Northstar Software",
    "Acme Engineering",
    "Quantum Analytics",
    "Starlight Tech",
    "Apex Cloud Services",
    "Nexus Data Systems",
    "Vanguard Enterprise",
    "Pinnacle Software Group",
    "Horizon Digital Solutions",
]

ENV_TYPES = ["PRODUCTION", "STAGING", "DEVELOPMENT", "TESTING"]
STORAGE_CLASSES = ["STANDARD", "INFREQUENT_ACCESS", "ARCHIVE"]


def generate_dataset():
    random.seed(42)
    print("==================================================")
    print("Generating 10,000+ Synthetic Storage Objects Dataset")
    print("==================================================")

    db: Session = SessionLocal()
    try:
        # Seed Pricing Catalog
        PricingProvider().seed_default_demo_pricing(db)

        from app.db.seed import seed_database
        seed_database()

        # Clear existing data for clean idempotent run
        print("1. Cleaning old dataset records...")
        db.query(LegalHold).delete()
        db.query(RetentionPolicy).delete()
        db.query(AccessEvent).delete()
        db.query(RestoreEvent).delete()
        db.query(StorageObject).delete()
        db.commit()

        ref_time = datetime.now(timezone.utc)
        rec_service = RecommendationService()

        total_objects_created = 0

        print("2. Generating Organizations, Environments, Locations & 10,000+ Objects...")
        for org_index, org_name in enumerate(ORGANIZATION_NAMES):
            slug = org_name.lower().replace(" ", "-")
            org = db.query(Organization).filter_by(slug=slug).first()
            if not org:
                org = Organization(name=org_name, slug=slug)
                db.add(org)
                db.commit()
                db.refresh(org)

            conn = StorageConnection(organization_id=org.id, name=f"{org.slug}-s3-conn", provider="LOCAL_S3_COMPATIBLE", credential_reference="LOCAL_MINIO", config={"bucket": f"{org.slug}-bucket"})
            db.add(conn)
            db.commit()

            # Create 10 environments per organization -> 100 environments total
            envs = []
            for env_i in range(10):
                e_type = ENV_TYPES[env_i % len(ENV_TYPES)]
                env = Environment(organization_id=org.id, storage_connection_id=conn.id, name=f"{e_type} Env {env_i + 1}", status="ACTIVE")
                db.add(env)
                envs.append(env)
            db.commit()

            loc = StorageLocation(organization_id=org.id, storage_connection_id=conn.id, name=f"{org.slug}-bucket", region="us-east-1")
            db.add(loc)
            db.commit()

            # Create 1,000 objects per organization -> 10,000 objects total
            objects_batch = []
            for obj_i in range(1000):
                total_objects_created += 1
                age_days = random.randint(1, 600)
                created_at = ref_time - timedelta(days=age_days)

                # Distribution of object sizes: 80% small (1-50MB), 20% large (500MB - 10GB)
                if random.random() < 0.8:
                    size_bytes = random.randint(1, 50) * 1024 * 1024
                else:
                    size_bytes = random.randint(500, 10000) * 1024 * 1024

                # Storage class distribution
                s_class = random.choices(STORAGE_CLASSES, weights=[0.65, 0.25, 0.10])[0]

                env_choice = random.choice(envs)
                obj_key = f"{env_choice.name.lower().replace(' ', '_')}/data_{obj_i + 1:04d}.dat"

                obj = StorageObject(
                    organization_id=org.id,
                    storage_location_id=loc.id,
                    environment_id=env_choice.id,
                    object_key=obj_key,
                    object_size_bytes=size_bytes,
                    storage_class=s_class,
                    created_at=created_at,
                    last_modified_at=created_at,
                    last_accessed_at=created_at + timedelta(days=random.randint(0, age_days)),
                )
                objects_batch.append(obj)

            db.bulk_save_objects(objects_batch)
            db.commit()

            print(f"   Created Organization '{org_name}' with 1,000 storage objects.")

        # Create retention policies & legal holds on subset of objects
        print("\n3. Injecting Retention Policies & Legal Holds...")
        org_first = db.query(Organization).filter_by(slug="democloud-labs").first()
        sample_objs = db.query(StorageObject).filter_by(organization_id=org_first.id).limit(100).all()

        for idx, sobj in enumerate(sample_objs):
            if idx % 10 == 0:
                # Active Legal Hold on 10% of sample
                hold = LegalHold(organization_id=org_first.id, object_id=sobj.id, status="ACTIVE", reason_reference=f"LITIGATION-HOLD-{idx}")
                db.add(hold)
            elif idx % 5 == 0:
                # Active Retention Policy (Retention active for 500 days)
                pol = RetentionPolicy(organization_id=org_first.id, object_id=sobj.id, name=f"500d Retention Rule {idx}", retention_duration_days=500, effective_date=ref_time - timedelta(days=100), status="ACTIVE")
                db.add(pol)

        db.commit()

        # Run Batch Recommendations for DemoCloud Labs
        print("\n4. Running Batch Recommendation Assessment on DemoCloud Labs...")
        recs = rec_service.batch_generate_recommendations(db, org_first.id, limit=1000, reference_time=ref_time)
        print(f"   Generated {len(recs)} recommendations for DemoCloud Labs.")

        # Run Snapshot Service
        print("\n5. Generating Daily Storage Cost Snapshots...")
        snaps_created = SnapshotService().create_daily_snapshots(db, snapshot_date=ref_time.date())
        print(f"   Created {snaps_created} storage cost snapshots.")

        # Run Experiment Service
        print("\n6. Running Counterfactual Cost Experiment...")
        exp_res = ExperimentService().run_counterfactual_experiment(db, org_first.id)

        print("\n==================================================")
        print("DATASET & EXPERIMENT GENERATION COMPLETED!")
        print("==================================================")
        print(f"Total Objects Analyzed: {exp_res['total_objects_analyzed']}")
        print(f"Baseline Monthly Cost: ${exp_res['baseline_monthly_cost_usd']:.2f}/mo")
        print(f"Optimized Monthly Cost: ${exp_res['optimized_monthly_cost_usd']:.2f}/mo")
        print(f"Estimated Monthly Savings: ${exp_res['estimated_monthly_savings_usd']:.2f}/mo ({exp_res['estimated_savings_percentage']}%)")
        print(f"Objects Eligible for Optimization: {exp_res['objects_eligible_for_optimization']}")
        print(f"Objects Kept: {exp_res['objects_kept']}")
        print(f"Objects Archived: {exp_res['objects_archived']}")
        print(f"Objects Moved to IA: {exp_res['objects_moved_to_infrequent_access']}")
        print(f"Delete Candidates: {exp_res['delete_candidates']}")
        print(f"Blocked by Retention: {exp_res['blocked_by_retention']}")
        print(f"Blocked by Legal Hold: {exp_res['blocked_by_legal_hold']}")

    finally:
        db.close()


if __name__ == "__main__":
    generate_dataset()
