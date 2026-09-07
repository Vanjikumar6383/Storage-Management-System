"""
Industry-Grade Synthetic Benchmark Dataset Generator for Storage Lifecycle Optimization.
Generates deterministic synthetic datasets without personal data, representing multi-tenant
software organizations, development environments, storage locations, 15 object categories,
ground truth labels, controlled scenarios A-J, and partition splits (DEVELOPMENT, VALIDATION, STRESS).
"""

import argparse
import random
import uuid
import sys
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Tuple

from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine
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
    StorageProviderEnum,
)
from app.services.pricing_provider import PricingProvider
from app.services.cost_engine import SnapshotService

ORG_PROFILES = [
    {"name": "SaaS Platform Corp", "profile_type": "SAAS", "churn": "HIGH", "avg_retention_days": 180},
    {"name": "FinTech Core Inc", "profile_type": "FINTECH", "churn": "LOW", "avg_retention_days": 365},
    {"name": "E-Commerce Digital", "profile_type": "ECOMMERCE", "churn": "MEDIUM", "avg_retention_days": 90},
    {"name": "AI Models Lab", "profile_type": "AI_COMPANY", "churn": "MEDIUM", "avg_retention_days": 180},
    {"name": "HealthCare Software Ltd", "profile_type": "HEALTHCARE", "churn": "LOW", "avg_retention_days": 730},
    {"name": "DevTools Infrastructure", "profile_type": "DEVTOOLS", "churn": "HIGH", "avg_retention_days": 30},
]

ENV_TYPES = [
    "DEVELOPMENT",
    "TEST",
    "QA",
    "STAGING",
    "CI_BUILD",
    "DATA_ANALYTICS",
    "ML_TRAINING",
    "TEMPORARY",
]

ENV_STATUSES = ["ACTIVE", "EXPIRED", "SUSPENDED", "ARCHIVED"]

OBJECT_CATEGORIES = [
    "BUILD_ARTIFACT",
    "BUILD_CACHE",
    "DEPENDENCY_CACHE",
    "LOG_FILE",
    "TEST_ARTIFACT",
    "DATABASE_BACKUP",
    "ML_CHECKPOINT",
    "MODEL_ARTIFACT",
    "ANALYTICS_EXPORT",
    "TEMPORARY_DATA",
    "SOURCE_ARCHIVE",
    "PACKAGE_CACHE",
    "CI_WORKSPACE",
    "DEBUG_DUMP",
    "RELEASE_ARTIFACT",
]

STORAGE_CLASSES = ["STANDARD", "INFREQUENT_ACCESS", "ARCHIVE"]


def generate_size_for_category(category: str) -> int:
    """Generate realistic non-uniform object size based on category."""
    if category in ("LOG_FILE", "BUILD_CACHE", "PACKAGE_CACHE", "DEPENDENCY_CACHE"):
        # Small (1 KB - 1 MB) or Medium (1 MB - 100 MB)
        if random.random() < 0.6:
            return random.randint(1024, 1024 * 1024)
        return random.randint(1024 * 1024, 100 * 1024 * 1024)
    elif category in ("BUILD_ARTIFACT", "TEST_ARTIFACT", "ANALYTICS_EXPORT", "RELEASE_ARTIFACT", "SOURCE_ARCHIVE"):
        # Medium (1 MB - 100 MB) or Large (100 MB - 10 GB)
        if random.random() < 0.5:
            return random.randint(1024 * 1024, 100 * 1024 * 1024)
        return random.randint(100 * 1024 * 1024, 10 * 1024 * 1024 * 1024)
    elif category in ("ML_CHECKPOINT", "MODEL_ARTIFACT", "DATABASE_BACKUP", "DEBUG_DUMP"):
        # Large (100 MB - 10 GB) or Very Large (10 GB - 500 GB)
        if random.random() < 0.7:
            return random.randint(100 * 1024 * 1024, 10 * 1024 * 1024 * 1024)
        return random.randint(10 * 1024 * 1024 * 1024, 500 * 1024 * 1024 * 1024)
    else:
        # Default medium size
        return random.randint(100 * 1024, 50 * 1024 * 1024)


def compute_ground_truth_label(
    age_days: int,
    accesses_30d: int,
    accesses_90d: int,
    restores_90d: int,
    storage_class: str,
    retention_active: bool,
    retention_expired: bool,
    legal_hold_active: bool,
    policy_conflict: bool,
    min_duration_satisfied: bool,
) -> Tuple[str, str]:
    """
    Independent domain-rule Ground Truth calculator.
    Determines ground_truth_action and ground_truth_reason completely separately from RecommendationEngine.
    """
    if legal_hold_active:
        return "HOLD", "Active legal hold overrides all lifecycle state transitions."
    if policy_conflict:
        return "REQUIRES_REVIEW", "Conflicting retention policy rules detected at scope hierarchy."
    if retention_expired and not legal_hold_active:
        return "DELETE_CANDIDATE", "Retention policy duration expired and no active legal hold."
    if retention_active:
        return "HOLD", "Active retention policy protects object from deletion."
    if restores_90d >= 3:
        return "KEEP", "High recent restore frequency indicates high retrieval cost risk."
    if age_days >= 180 and accesses_30d == 0 and restores_90d == 0 and storage_class not in ("ARCHIVE", "GLACIER"):
        if not min_duration_satisfied:
            return "HOLD", "Minimum storage duration for current tier not satisfied."
        return "ARCHIVE", "Cold object (>180d age, 0 accesses in 30d, 0 restores) eligible for archival."
    if age_days >= 90 and accesses_30d == 0 and storage_class == "STANDARD":
        return "INFREQUENT_ACCESS", "Aging object (>90d age, 0 accesses in 30d) eligible for Infrequent Access."
    
    return "KEEP", "Object is active, recent, or already in optimal storage class."


def generate_industry_dataset(
    num_orgs: int = 20,
    num_envs: int = 500,
    num_objects: int = 50000,
    seed: int = 42,
):
    start_time = time.time()
    random.seed(seed)

    print("======================================================================")
    print(f"Generating Industry-Grade Benchmark Dataset (Seed {seed})")
    print(f"Target: {num_orgs} Orgs | {num_envs} Envs | {num_objects:,} Objects")
    print("======================================================================")

    db: Session = SessionLocal()
    try:
        # Seed Pricing Catalog
        PricingProvider().seed_default_demo_pricing(db)

        print("1. Cleaning old synthetic objects dataset records...")
        db.query(LegalHold).delete()
        db.query(RetentionPolicy).delete()
        db.query(AccessEvent).delete()
        db.query(RestoreEvent).delete()
        db.query(StorageObject).delete()
        db.commit()

        ref_time = datetime.now(timezone.utc)

        # 1. Create Organizations
        print(f"2. Generating {num_orgs} synthetic software organizations...")
        orgs = []
        for i in range(num_orgs):
            profile = ORG_PROFILES[i % len(ORG_PROFILES)]
            org_slug = f"org_{i+1:03d}_{profile['profile_type'].lower()}"
            org_name = f"{profile['name']} ({i+1:03d})"
            
            org = db.query(Organization).filter_by(slug=org_slug).first()
            if not org:
                org = Organization(name=org_name, slug=org_slug)
                db.add(org)
                db.flush()
            orgs.append(org)
        db.commit()

        # 2. Create Environments & Storage Locations
        print(f"3. Generating {num_envs} development environments & storage locations...")
        envs = []
        locations = []
        
        envs_per_org = max(1, num_envs // num_orgs)
        for org_idx, org in enumerate(orgs):
            # Connections & Locations
            conn = StorageConnection(
                organization_id=org.id,
                name=f"conn_{org.slug}",
                provider="LOCAL_S3_COMPATIBLE",
                credential_reference="LOCAL_MINIO",
                config={"bucket": f"bucket-{org.slug}"},
            )
            db.add(conn)
            db.flush()

            loc = StorageLocation(
                organization_id=org.id,
                storage_connection_id=conn.id,
                name=f"bucket-{org.slug}",
                region="us-east-1",
            )
            db.add(loc)
            db.flush()
            locations.append(loc)

            for e_idx in range(envs_per_org):
                e_type = ENV_TYPES[e_idx % len(ENV_TYPES)]
                e_status = random.choices(ENV_STATUSES, weights=[0.7, 0.15, 0.1, 0.05])[0]
                env = Environment(
                    organization_id=org.id,
                    storage_connection_id=conn.id,
                    name=f"env_{e_type.lower()}_{e_idx+1:03d}",
                    environment_type=e_type,
                    status=e_status,
                    expected_lifetime_days=random.choice([30, 60, 90, 180, 365]),
                )
                db.add(env)
                envs.append(env)
        db.commit()

        print(f"   Created {len(envs)} environments and {len(locations)} storage locations.")

        # 3. Generate Objects in Bulk with Scenarios A-J and Partition Splits
        print(f"4. Generating {num_objects:,} storage objects with Ground Truth & Scenarios A-J...")

        partitions = ["DEVELOPMENT"] * 70 + ["VALIDATION"] * 15 + ["STRESS"] * 15
        scenarios = ["SCENARIO_A", "SCENARIO_B", "SCENARIO_C", "SCENARIO_D", "SCENARIO_E", "SCENARIO_F", "SCENARIO_G", "SCENARIO_H", "SCENARIO_I", "SCENARIO_J", None]
        scenario_weights = [0.15, 0.10, 0.05, 0.08, 0.05, 0.03, 0.20, 0.04, 0.04, 0.02, 0.24]

        batch_size = 5000
        objects_created = 0
        held_count = 0
        policy_count = 0

        for b_start in range(0, num_objects, batch_size):
            b_count = min(batch_size, num_objects - b_start)
            obj_batch = []
            
            for i in range(b_count):
                obj_index = b_start + i
                org = orgs[obj_index % len(orgs)]
                org_envs = [e for e in envs if e.organization_id == org.id]
                env = random.choice(org_envs) if org_envs else random.choice(envs)
                loc = next(l for l in locations if l.organization_id == org.id)

                category = random.choice(OBJECT_CATEGORIES)
                size_bytes = generate_size_for_category(category)
                scen = random.choices(scenarios, weights=scenario_weights)[0]
                partition = random.choice(partitions)

                # Assign realistic ages and telemetry based on scenario
                if scen == "SCENARIO_A":
                    # Old + unused + STANDARD -> ARCHIVE candidate
                    age_days = random.randint(200, 500)
                    acc_30d = 0
                    acc_90d = 0
                    restores_90d = 0
                    s_class = "STANDARD"
                    ret_active = False
                    ret_exp = False
                    lh_active = False
                    conflict = False
                    min_sat = True
                elif scen == "SCENARIO_B":
                    # Old + frequently accessed -> KEEP (Counterexample)
                    age_days = random.randint(200, 500)
                    acc_30d = random.randint(15, 100)
                    acc_90d = acc_30d + random.randint(10, 200)
                    restores_90d = 0
                    s_class = "STANDARD"
                    ret_active = False
                    ret_exp = False
                    lh_active = False
                    conflict = False
                    min_sat = True
                elif scen == "SCENARIO_C":
                    # Old + high restore frequency -> KEEP / HOLD
                    age_days = random.randint(200, 500)
                    acc_30d = 0
                    acc_90d = 0
                    restores_90d = random.randint(4, 15)
                    s_class = "STANDARD"
                    ret_active = False
                    ret_exp = False
                    lh_active = False
                    conflict = False
                    min_sat = True
                elif scen == "SCENARIO_D":
                    # Expired retention + no legal hold -> DELETE candidate
                    age_days = random.randint(400, 700)
                    acc_30d = 0
                    acc_90d = 0
                    restores_90d = 0
                    s_class = "STANDARD"
                    ret_active = False
                    ret_exp = True
                    lh_active = False
                    conflict = False
                    min_sat = True
                elif scen == "SCENARIO_E":
                    # Expired retention + active legal hold -> DELETE BLOCKED (HOLD)
                    age_days = random.randint(400, 700)
                    acc_30d = 0
                    acc_90d = 0
                    restores_90d = 0
                    s_class = "STANDARD"
                    ret_active = False
                    ret_exp = True
                    lh_active = True
                    conflict = False
                    min_sat = True
                elif scen == "SCENARIO_F":
                    # Conflicting policies -> REQUIRES_REVIEW
                    age_days = random.randint(200, 500)
                    acc_30d = 0
                    acc_90d = 0
                    restores_90d = 0
                    s_class = "STANDARD"
                    ret_active = False
                    ret_exp = False
                    lh_active = False
                    conflict = True
                    min_sat = True
                elif scen == "SCENARIO_G":
                    # Fresh object -> KEEP
                    age_days = random.randint(1, 25)
                    acc_30d = random.randint(1, 10)
                    acc_90d = acc_30d
                    restores_90d = 0
                    s_class = "STANDARD"
                    ret_active = False
                    ret_exp = False
                    lh_active = False
                    conflict = False
                    min_sat = True
                elif scen == "SCENARIO_I":
                    # Minimum storage duration not satisfied -> HOLD
                    age_days = random.randint(200, 400)
                    acc_30d = 0
                    acc_90d = 0
                    restores_90d = 0
                    s_class = "INFREQUENT_ACCESS"  # Min duration 30d
                    ret_active = False
                    ret_exp = False
                    lh_active = False
                    conflict = False
                    min_sat = False
                else:
                    # General population
                    age_days = random.randint(1, 600)
                    acc_30d = random.choice([0, 0, 0, 1, 5, 20])
                    acc_90d = acc_30d + random.randint(0, 30)
                    restores_90d = random.choice([0, 0, 0, 0, 1, 3])
                    s_class = random.choices(STORAGE_CLASSES, weights=[0.65, 0.25, 0.10])[0]
                    ret_active = random.random() < 0.05
                    ret_exp = random.random() < 0.03 if not ret_active else False
                    lh_active = random.random() < 0.015
                    conflict = False
                    min_sat = True

                created_at = ref_time - timedelta(days=age_days)
                last_accessed = created_at + timedelta(days=random.randint(0, age_days)) if acc_30d > 0 else None
                obj_key = f"{category.lower()}/{partition.lower()}/obj_{obj_index+1:06d}.bin"

                # Ground Truth Computation
                gt_action, gt_reason = compute_ground_truth_label(
                    age_days=age_days,
                    accesses_30d=acc_30d,
                    accesses_90d=acc_90d,
                    restores_90d=restores_90d,
                    storage_class=s_class,
                    retention_active=ret_active,
                    retention_expired=ret_exp,
                    legal_hold_active=lh_active,
                    policy_conflict=conflict,
                    min_duration_satisfied=min_sat,
                )

                sobj = StorageObject(
                    organization_id=org.id,
                    storage_location_id=loc.id,
                    environment_id=env.id,
                    object_key=obj_key,
                    object_size_bytes=size_bytes,
                    category=category,
                    storage_class=s_class,
                    current_state="ACTIVE",
                    dataset_partition=partition,
                    scenario_tag=scen,
                    ground_truth_action=gt_action,
                    ground_truth_reason=gt_reason,
                    created_at=created_at,
                    last_modified_at=created_at,
                    last_accessed_at=last_accessed,
                    access_count_30d=acc_30d,
                    access_count_90d=acc_90d,
                )
                db.add(sobj)
                db.flush()

                # Add Legal Hold if active
                if lh_active:
                    held_count += 1
                    hold = LegalHold(
                        organization_id=org.id,
                        object_id=sobj.id,
                        status="ACTIVE",
                        reason_reference=f"reason_ref_litigation_{held_count:04d}",
                    )
                    db.add(hold)

                # Add Retention Policy if active/expired
                if ret_active or ret_exp:
                    policy_count += 1
                    pol_dur = 360 if ret_exp else 500
                    eff_date = ref_time - timedelta(days=400) if ret_exp else ref_time - timedelta(days=100)
                    policy = RetentionPolicy(
                        organization_id=org.id,
                        object_id=sobj.id,
                        name=f"Retention Policy {policy_count}",
                        retention_duration_days=pol_dur,
                        effective_date=eff_date,
                        status="ACTIVE",
                    )
                    db.add(policy)

            db.commit()
            objects_created += b_count
            print(f"   Saved batch {objects_created:,} / {num_objects:,} objects...")

        # 5. Generate Snapshots
        print("5. Generating Storage Cost Snapshots...")
        SnapshotService().create_daily_snapshots(db, snapshot_date=ref_time.date())

        elapsed = time.time() - start_time
        print("\n======================================================================")
        print("SYNTHETIC BENCHMARK DATASET GENERATION COMPLETE")
        print("======================================================================")
        print(f"Total Objects Created: {objects_created:,}")
        print(f"Active Legal Holds: {held_count}")
        print(f"Retention Policies: {policy_count}")
        print(f"Execution Time: {elapsed:.2f} seconds")
        print("======================================================================")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Generate Industry-Grade Synthetic Benchmark Dataset")
    parser.add_argument("--organizations", type=int, default=20, help="Number of synthetic organizations (default: 20)")
    parser.add_argument("--environments", type=int, default=500, help="Number of synthetic environments (default: 500)")
    parser.add_argument("--objects", type=int, default=50000, help="Number of synthetic storage objects (default: 50000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation (default: 42)")

    args = parser.parse_args()
    generate_industry_dataset(
        num_orgs=args.organizations,
        num_envs=args.environments,
        num_objects=args.objects,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
