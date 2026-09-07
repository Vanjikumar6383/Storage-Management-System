"""
Local S3 End-to-End Verification & Demonstration Script.
Validates bucket discovery, metadata ingestion, idempotency, updates, and error handling.
"""

import boto3
from moto import mock_aws
from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models import Organization, StorageConnection, StorageObject, StorageLocation
from app.connectors.s3_connector import LocalS3Connector
from app.jobs.sync_job import run_connection_sync


def run_e2e_local_validation():
    print("==================================================")
    print("STEP 3 — Local S3 End-to-End Metadata Validation")
    print("==================================================")

    db = SessionLocal()
    try:
        demo_org = db.query(Organization).filter_by(slug="demo-organization").first()
        if not demo_org:
            raise RuntimeError("Demo Organization not found in PostgreSQL database.")

        conn = db.query(StorageConnection).filter_by(organization_id=demo_org.id).first()
        if not conn:
            raise RuntimeError("Storage Connection not found in PostgreSQL database.")

        print(f"Using Organization: '{demo_org.name}' ({demo_org.id})")
        print(f"Using Storage Connection: '{conn.name}' ({conn.id})")

        # 1. Start mock S3 environment
        with mock_aws():
            s3_client = boto3.client("s3", region_name="us-east-1")

            bucket_name = "demo-analytics-bucket"
            s3_client.create_bucket(Bucket=bucket_name)
            print(f"\n1. Created local S3 test bucket: '{bucket_name}'")

            # 2. Upload 5 test objects (zero personal data)
            test_files = [
                ("datasets/raw/2026/metrics_part1.json", b"x" * 5120),
                ("datasets/raw/2026/metrics_part2.json", b"x" * 5120),
                ("logs/system/app_20260817.log", b"x" * 1024),
                ("backups/db/daily_dump_20260815.tar.gz", b"x" * 1048576),
                ("temp/scratch/cache_build.tmp", b"x" * 2048),
            ]

            for key, content in test_files:
                s3_client.put_object(Bucket=bucket_name, Key=key, Body=content)
            print(f"2. Uploaded {len(test_files)} sample objects to '{bucket_name}'.")

            # 3. Create LocalS3Connector targeting mock S3
            connector = LocalS3Connector()
            connector.client = s3_client

            # 4. Run First Sync
            print("\n3. Executing First Sync Job...")
            sync_log_1 = run_connection_sync(db, conn.id, connector_override=connector)
            print(f"   Status: {sync_log_1.status}")
            print(f"   Locations Discovered: {sync_log_1.locations_discovered}")
            print(f"   Objects Discovered: {sync_log_1.objects_discovered}")
            print(f"   Objects Created: {sync_log_1.objects_created}")
            print(f"   Objects Updated: {sync_log_1.objects_updated}")

            # Verify in PostgreSQL
            db_objs_1 = db.query(StorageObject).filter_by(organization_id=demo_org.id).all()
            print(f"   PostgreSQL Record Count: {len(db_objs_1)}")
            assert len(db_objs_1) >= 5, "Expected at least 5 objects in PostgreSQL after sync"

            # 5. Run Second Sync (Idempotency Check)
            print("\n4. Executing Second Sync Job (Idempotency Test)...")
            sync_log_2 = run_connection_sync(db, conn.id, connector_override=connector)
            print(f"   Status: {sync_log_2.status}")
            print(f"   Objects Discovered: {sync_log_2.objects_discovered}")
            print(f"   Objects Created: {sync_log_2.objects_created}")
            print(f"   Objects Updated: {sync_log_2.objects_updated}")
            assert sync_log_2.objects_created == 0, "Idempotency failed: New records created on duplicate sync"

            # 6. Modify 1 object metadata and re-sync
            print("\n5. Modifying object metadata in S3 and re-syncing...")
            s3_client.put_object(
                Bucket=bucket_name,
                Key="logs/system/app_20260817.log",
                Body=b"x" * 4096,  # Size changed from 1024 to 4096 bytes
            )

            sync_log_3 = run_connection_sync(db, conn.id, connector_override=connector)
            print(f"   Status: {sync_log_3.status}")
            print(f"   Objects Updated: {sync_log_3.objects_updated}")
            assert sync_log_3.objects_updated == 1, "Expected 1 object to be updated"

            updated_obj = (
                db.query(StorageObject)
                .join(StorageLocation)
                .filter(
                    StorageLocation.name == bucket_name,
                    StorageObject.object_key == "logs/system/app_20260817.log",
                )
                .first()
            )
            assert updated_obj.object_size_bytes == 4096, "Updated size verification failed"
            print(f"   Verified updated object size in PostgreSQL: {updated_obj.object_size_bytes} bytes")

            # 7. Test Error Handling (Invalid connection failure)
            print("\n6. Testing Connector Error Handling (Simulated Connection Failure)...")
            class FailingConnector:
                def test_connection(self):
                    return False

            sync_log_err = run_connection_sync(db, conn.id, connector_override=FailingConnector())
            print(f"   Status: {sync_log_err.status}")
            print(f"   Error Summary: {sync_log_err.error_summary}")
            assert sync_log_err.status == "FAILED"

            print("\n==================================================")
            print("ALL END-TO-END VALIDATION CHECKS PASSED CLEANLY!")
            print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_e2e_local_validation()
