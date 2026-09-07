"""
Seed script for Storage Lifecycle Optimizer.
Strictly maintains the 10 Canonical Demo Organizations, pruning any extraneous tenants,
and populates rich, realistic demo storage datasets, telemetry, policies, and ML-scored recommendations.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from app.db.database import SessionLocal, engine
from app.models import (
    Organization,
    User,
    OrganizationMembership,
    RoleEnum,
    Subscription,
    StorageConnection,
    StorageProviderEnum,
    Environment,
    StorageLocation,
    StorageObject,
    RetentionPolicy,
    LegalHold,
    AccessEvent,
    RestoreEvent,
    Recommendation,
)
from app.services.recommendation_engine import RecommendationService

logger = logging.getLogger("storage.seed")

# Baseline Core Test & Demo Organizations (Required by automated tests & verification scripts)
BASELINE_ORGS = [
    {
        "name": "Demo Organization",
        "slug": "demo-organization",
        "email": "admin@demo.local",
        "plan": "ENTERPRISE_PRO",
        "provider": StorageProviderEnum.LOCAL_S3_COMPATIBLE,
        "region": "us-east-1",
        "domain": "demo-storage",
        "categories": ["analytical_data", "logs", "backups"],
    },
    {
        "name": "Test Organization",
        "slug": "test-organization",
        "email": "admin@test.local",
        "plan": "ENTERPRISE_PRO",
        "provider": StorageProviderEnum.LOCAL_S3_COMPATIBLE,
        "region": "us-east-1",
        "domain": "test-storage",
        "categories": ["general_data", "logs", "documents"],
    },
]

# The 10 Canonical Demo Organizations
TEN_DEMO_ORGS = [
    {
        "name": "Acme Engineering Cloud",
        "slug": "acme-engineering",
        "email": "admin@acme-engineering.io",
        "plan": "ENTERPRISE_PRO",
        "provider": StorageProviderEnum.AWS_S3,
        "region": "us-east-1",
        "domain": "acme-core-pipeline",
        "categories": ["analytical_data", "logs", "backups"],
    },
    {
        "name": "Apex Cloud Services",
        "slug": "apex-cloud-services",
        "email": "admin@apex-cloud-services.io",
        "plan": "HYPERSCALE",
        "provider": StorageProviderEnum.AWS_S3,
        "region": "us-west-2",
        "domain": "apex-microservices",
        "categories": ["documents", "media", "backups"],
    },
    {
        "name": "DemoCloud Labs",
        "slug": "democloud-labs",
        "email": "admin@democloud-labs.io",
        "plan": "DEVELOPMENT_FREE",
        "provider": StorageProviderEnum.LOCAL_S3_COMPATIBLE,
        "region": "us-east-1",
        "domain": "democloud-sandbox",
        "categories": ["general_data", "logs", "analytical_data"],
    },
    {
        "name": "DevTools Infrastructure",
        "slug": "devtools-infrastructure",
        "email": "admin@devtools-infrastructure.io",
        "plan": "ENTERPRISE_PRO",
        "provider": StorageProviderEnum.LOCAL_S3_COMPATIBLE,
        "region": "eu-central-1",
        "domain": "devtools-ci-artifacts",
        "categories": ["backups", "logs", "code"],
    },
    {
        "name": "E-Commerce Global Digital",
        "slug": "ecommerce-digital",
        "email": "admin@ecommerce-digital.io",
        "plan": "HYPERSCALE",
        "provider": StorageProviderEnum.AWS_S3,
        "region": "us-east-1",
        "domain": "ecommerce-catalog-media",
        "categories": ["media", "analytical_data", "documents"],
    },
    {
        "name": "FinTech Core Systems",
        "slug": "fintech-core",
        "email": "admin@fintech-core.io",
        "plan": "HYPERSCALE",
        "provider": StorageProviderEnum.AWS_S3,
        "region": "us-east-1",
        "domain": "fintech-ledger-vault",
        "categories": ["documents", "analytical_data", "backups"],
    },
    {
        "name": "HealthCare Software Solutions",
        "slug": "healthcare-software",
        "email": "admin@healthcare-software.io",
        "plan": "ENTERPRISE_PRO",
        "provider": StorageProviderEnum.AWS_S3,
        "region": "us-east-2",
        "domain": "healthcare-patient-imaging",
        "categories": ["media", "documents", "backups"],
    },
    {
        "name": "Horizon Digital Media",
        "slug": "horizon-digital",
        "email": "admin@horizon-digital.io",
        "plan": "ENTERPRISE_PRO",
        "provider": StorageProviderEnum.GOOGLE_CLOUD_STORAGE,
        "region": "us-central1",
        "domain": "horizon-video-encoding",
        "categories": ["media", "documents", "general_data"],
    },
    {
        "name": "Nexus BigData Systems",
        "slug": "nexus-data",
        "email": "admin@nexus-data.io",
        "plan": "HYPERSCALE",
        "provider": StorageProviderEnum.AWS_S3,
        "region": "us-west-1",
        "domain": "nexus-lakehouse-datalake",
        "categories": ["analytical_data", "logs", "backups"],
    },
    {
        "name": "Quantum AI & Analytics",
        "slug": "quantum-analytics",
        "email": "admin@quantum-analytics.io",
        "plan": "ENTERPRISE_PRO",
        "provider": StorageProviderEnum.AWS_S3,
        "region": "us-east-1",
        "domain": "quantum-model-checkpoints",
        "categories": ["analytical_data", "documents", "backups"],
    },
]


def generate_objects_for_org(org_def: Dict[str, Any], ref_time: datetime) -> List[Dict[str, Any]]:
    """Generates 12 deterministic, realistic storage objects representing diverse lifecycle states."""
    domain = org_def["domain"]
    cats = org_def["categories"]

    return [
        {
            "key": f"{domain}/active/current_transactions_{ref_time.strftime('%Y%m')}.parquet",
            "size_bytes": 14 * 1024 * 1024 * 1024,  # 14 GB
            "storage_class": "STANDARD",
            "age_days": 12,
            "accesses_30d": 45,
            "category": cats[0],
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/telemetry/app_access_stream.log",
            "size_bytes": 28 * 1024 * 1024 * 1024,  # 28 GB
            "storage_class": "STANDARD",
            "age_days": 18,
            "accesses_30d": 120,
            "category": "logs",
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/reports/quarterly_audit_dossier.pdf",
            "size_bytes": 6 * 1024 * 1024 * 1024,  # 6 GB
            "storage_class": "STANDARD",
            "age_days": 120,
            "accesses_30d": 0,
            "category": "documents",
            "legal_hold": True,  # Protected by compliance legal hold
            "hold_reason": "Statutory Annual Compliance Lock #SEC-8092",
            "retention_policy": 365,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/analytics/historical_aggregation_q2.csv",
            "size_bytes": 45 * 1024 * 1024 * 1024,  # 45 GB
            "storage_class": "STANDARD",
            "age_days": 55,
            "accesses_30d": 0,
            "category": "analytical_data",
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/snapshots/database_full_snapshot_v4.tar.gz",
            "size_bytes": 180 * 1024 * 1024 * 1024,  # 180 GB
            "storage_class": "STANDARD",
            "age_days": 160,
            "accesses_30d": 0,
            "category": "backups",
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/temp/staging_etl_cleanup.tmp",
            "size_bytes": 22 * 1024 * 1024 * 1024,  # 22 GB
            "storage_class": "STANDARD",
            "age_days": 410,
            "accesses_30d": 0,
            "category": "general_data",
            "legal_hold": False,
            "retention_policy": 30,  # Expired retention
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/cold_vault/deep_compliance_records_2023.zip",
            "size_bytes": 95 * 1024 * 1024 * 1024,  # 95 GB
            "storage_class": "ARCHIVE",
            "age_days": 380,
            "accesses_30d": 0,
            "category": "backups",
            "legal_hold": False,
            "retention_policy": 730,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/models/production_weights_checkpoints.bin",
            "size_bytes": 35 * 1024 * 1024 * 1024,  # 35 GB
            "storage_class": "INFREQUENT_ACCESS",
            "age_days": 75,
            "accesses_30d": 2,
            "category": "analytical_data",
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/recovery/disaster_recovery_image.iso",
            "size_bytes": 60 * 1024 * 1024 * 1024,  # 60 GB
            "storage_class": "STANDARD",
            "age_days": 210,
            "accesses_30d": 0,
            "category": "backups",
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 4,  # Restore risk!
        },
        {
            "key": f"{domain}/media/highres_brand_assets_master.mp4",
            "size_bytes": 12 * 1024 * 1024 * 1024,  # 12 GB
            "storage_class": "STANDARD",
            "age_days": 95,
            "accesses_30d": 0,
            "category": "media",
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/logs/historical_syslog_archive.log.gz",
            "size_bytes": 52 * 1024 * 1024 * 1024,  # 52 GB
            "storage_class": "STANDARD",
            "age_days": 130,
            "accesses_30d": 0,
            "category": "logs",
            "legal_hold": False,
            "retention_policy": None,
            "restores_90d": 0,
        },
        {
            "key": f"{domain}/legal/gdpr_data_export_bundle.enc",
            "size_bytes": 8 * 1024 * 1024 * 1024,  # 8 GB
            "storage_class": "STANDARD",
            "age_days": 310,
            "accesses_30d": 0,
            "category": "documents",
            "legal_hold": True,
            "hold_reason": "GDPR Regulatory Injunction #EU-2024-91",
            "retention_policy": 1095,
            "restores_90d": 0,
        },
    ]


def seed_database():
    db = SessionLocal()
    rec_service = RecommendationService()
    ref_time = datetime.now(timezone.utc)

    try:
        print("=" * 70)
        print("STORAGE LIFECYCLE OPTIMIZER: CANONICAL 10 DEMO ORGANIZATIONS SEED")
        print("=" * 70)

        all_orgs = BASELINE_ORGS + TEN_DEMO_ORGS
        canonical_slugs = [org["slug"] for org in all_orgs]

        # STEP 1: Prune any organization not in the canonical demo & test orgs
        print("\n[Step 1] Pruning non-canonical organizations from database...")
        stale_orgs = db.query(Organization).filter(~Organization.slug.in_(canonical_slugs)).all()
        pruned_count = len(stale_orgs)
        for stale in stale_orgs:
            print(f"  - Pruning stale org: {stale.slug} ('{stale.name}')")
            db.delete(stale)
        db.commit()
        print(f"  Successfully pruned {pruned_count} non-demo organizations.")

        # STEP 2: Seed / Update Canonical Demo & Baseline Test Organizations
        print(f"\n[Step 2] Provisioning {len(all_orgs)} Canonical Organizations & Datasets...")

        for idx, org_data in enumerate(all_orgs, 1):
            slug = org_data["slug"]
            name = org_data["name"]
            admin_email = org_data["email"]

            print(f"\n  [{idx}/{len(all_orgs)}] Setting up {name} ({slug})...")

            # 1. User
            user = db.query(User).filter_by(email=admin_email).first()
            if not user:
                user = User(email=admin_email, is_active="ACTIVE")
                db.add(user)
                db.flush()

            # 2. Organization
            org = db.query(Organization).filter_by(slug=slug).first()
            if not org:
                org = Organization(name=name, slug=slug)
                db.add(org)
                db.flush()
            else:
                org.name = name
                db.flush()

            # 3. Membership
            membership = db.query(OrganizationMembership).filter_by(organization_id=org.id, user_id=user.id).first()
            if not membership:
                membership = OrganizationMembership(organization_id=org.id, user_id=user.id, role=RoleEnum.OWNER)
                db.add(membership)

            # 4. Subscription
            sub = db.query(Subscription).filter_by(organization_id=org.id).first()
            if not sub:
                sub = Subscription(
                    organization_id=org.id,
                    plan=org_data["plan"],
                    status="ACTIVE",
                    limits={"max_storage_gb": 50000 if org_data["plan"] == "ENTERPRISE_PRO" else 1000000},
                )
                db.add(sub)

            # 5. Storage Connection
            storage_conn = db.query(StorageConnection).filter_by(organization_id=org.id).first()
            if not storage_conn:
                storage_conn = StorageConnection(
                    organization_id=org.id,
                    name=f"{name} Primary Connection",
                    provider=org_data["provider"],
                    credential_reference=f"env:{slug.upper().replace('-', '_')}_KEY",
                    config={"region": org_data["region"]},
                )
                db.add(storage_conn)
                db.flush()

            # 6. Environment
            env = db.query(Environment).filter_by(organization_id=org.id).first()
            if not env:
                env = Environment(
                    organization_id=org.id,
                    storage_connection_id=storage_conn.id,
                    name="production",
                    environment_type="PRODUCTION",
                    status="ACTIVE",
                )
                db.add(env)
                db.flush()

            # 7. Storage Location (Bucket)
            loc = db.query(StorageLocation).filter_by(organization_id=org.id).first()
            if not loc:
                loc = StorageLocation(
                    organization_id=org.id,
                    storage_connection_id=storage_conn.id,
                    name=f"{slug}-primary-data",
                    region=org_data["region"],
                )
                db.add(loc)
                db.flush()

            db.commit()

            # 8. Objects & Telemetry
            existing_objs = db.query(StorageObject).filter_by(organization_id=org.id).count()
            if existing_objs < 5:
                # Seed rich demo objects
                object_specs = generate_objects_for_org(org_data, ref_time)
                created_objs = []

                for spec in object_specs:
                    obj_key = spec["key"]
                    age = spec["age_days"]
                    size = spec["size_bytes"]
                    storage_cls = spec["storage_class"]
                    cat = spec["category"]

                    obj = StorageObject(
                        organization_id=org.id,
                        storage_location_id=loc.id,
                        environment_id=env.id,
                        object_key=obj_key,
                        object_size_bytes=size,
                        object_type="application/octet-stream",
                        category=cat,
                        storage_class=storage_cls,
                        current_state="ACTIVE",
                        dataset_partition="PRODUCTION",
                        created_at=ref_time - timedelta(days=age),
                        last_modified_at=ref_time - timedelta(days=age),
                        last_accessed_at=ref_time - timedelta(days=min(age, 3)) if spec["accesses_30d"] > 0 else (ref_time - timedelta(days=age)),
                        access_count_30d=spec["accesses_30d"],
                        access_count_90d=spec["accesses_30d"] * 2,
                        version_count=1,
                    )
                    db.add(obj)
                    db.flush()
                    created_objs.append(obj)

                    # Policies & Holds
                    if spec.get("retention_policy"):
                        db.add(RetentionPolicy(
                            organization_id=org.id,
                            object_id=obj.id,
                            name=f"{cat.title()} Lifecycle Retention Policy",
                            retention_duration_days=spec["retention_policy"],
                            effective_date=ref_time - timedelta(days=age),
                            status="ACTIVE",
                        ))

                    if spec.get("legal_hold"):
                        db.add(LegalHold(
                            organization_id=org.id,
                            object_id=obj.id,
                            reason_reference=spec.get("hold_reason", "Regulatory Compliance Injunction"),
                            status="ACTIVE",
                        ))

                    if spec.get("restores_90d", 0) > 0:
                        for r_idx in range(spec["restores_90d"]):
                            db.add(RestoreEvent(
                                organization_id=org.id,
                                object_id=obj.id,
                                requested_at=ref_time - timedelta(days=10 * (r_idx + 1)),
                                completed_at=ref_time - timedelta(days=10 * (r_idx + 1)),
                                status="COMPLETED",
                                source_storage_class="ARCHIVE",
                                target_storage_class="STANDARD",
                                restore_duration_seconds=3600,
                            ))

                    if spec.get("accesses_30d", 0) > 0:
                        db.add(AccessEvent(
                            organization_id=org.id,
                            object_id=obj.id,
                            event_timestamp=ref_time - timedelta(hours=6),
                            event_type="GET",
                            source="api_client",
                        ))

                db.commit()

            # Ensure recommendations exist for all objects in this organization
            org_objs = db.query(StorageObject).filter_by(organization_id=org.id).all()
            for o in org_objs:
                try:
                    rec_service.generate_and_save_recommendation(
                        db=db,
                        organization_id=org.id,
                        object_id=o.id,
                        reference_time=ref_time,
                    )
                except Exception as err:
                    print(f"    Warning generating recommendation for {o.object_key}: {err}")

            db.commit()
            recs_total = db.query(Recommendation).filter_by(organization_id=org.id).count()
            print(f"    Indexed {len(org_objs)} demo objects with {recs_total} telemetry & ML recommendations.")

        # Final Verification
        final_orgs = db.query(Organization).all()
        print("\n" + "=" * 70)
        print(f"VERIFICATION: Total Organizations in Database: {len(final_orgs)}")
        for o in final_orgs:
            obj_cnt = db.query(StorageObject).filter_by(organization_id=o.id).count()
            rec_cnt = db.query(Recommendation).filter_by(organization_id=o.id).count()
            print(f"  * {o.name.ljust(32)} | Slug: {o.slug.ljust(25)} | Objects: {str(obj_cnt).rjust(3)} | Recs: {str(rec_cnt).rjust(3)}")
        print("=" * 70)

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Seeding failed: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
