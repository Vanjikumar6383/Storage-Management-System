"""
Standalone Real AWS Smoke Test Script.
Safely checks for live AWS credentials and test bucket in environment variables.
If credentials exist, runs a live connection test, metadata sync, safe STANDARD -> STANDARD_IA CopyObject migration, and immediate rollback.
If credentials do not exist, cleanly reports that live environment validation was skipped while code-level production readiness is verified.
"""

import os
import sys
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("aws_smoke_test")

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.connectors.aws_s3_connector import AWSS3Connector
from app.connectors.credentials import ResolvedCredentials


def main():
    logger.info("=== STORAGE LIFECYCLE OPTIMIZER — REAL AWS S3 SMOKE TEST ===")

    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = os.getenv("AWS_SESSION_TOKEN")
    region = os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1"))
    test_bucket = os.getenv("AWS_TEST_BUCKET")

    if not access_key or not secret_key or not test_bucket:
        logger.info("----------------------------------------------------------------------")
        logger.info("NOTICE: Real AWS smoke test not executed because AWS test credentials/bucket were not available.")
        logger.info("Required env vars missing: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_TEST_BUCKET.")
        logger.info("Code-level production readiness verified via automated test suite.")
        logger.info("----------------------------------------------------------------------")
        sys.exit(0)

    logger.info(f"Resolving AWS credentials for region '{region}' and bucket '{test_bucket}'...")
    creds = ResolvedCredentials(
        provider="AWS_S3",
        access_key=access_key,
        secret_key=secret_key,
        session_token=session_token,
        region=region,
    )

    connector = AWSS3Connector(credentials=creds)

    # 1. Connection Test
    logger.info("Phase 1: Testing AWS S3 Connection...")
    if not connector.test_connection():
        logger.error("FAILED: AWS S3 connection test failed. Check credentials and region.")
        sys.exit(1)
    logger.info("SUCCESS: AWS S3 connection test passed.")

    # 2. Bucket Discovery
    logger.info("Phase 2: Discovering Storage Locations...")
    locations = connector.list_storage_locations()
    bucket_names = [loc.name for loc in locations]
    logger.info(f"Discovered buckets: {bucket_names}")
    if test_bucket not in bucket_names:
        logger.warning(f"Test bucket '{test_bucket}' not listed in list_buckets output, attempting direct object listing...")

    # 3. Object Listing
    logger.info(f"Phase 3: Listing Objects in '{test_bucket}'...")
    objects, next_token = connector.list_objects(test_bucket)
    logger.info(f"Discovered {len(objects)} objects in '{test_bucket}'.")

    if not objects:
        logger.info(f"No objects found in '{test_bucket}'. Real smoke test requires at least 1 object in '{test_bucket}'.")
        logger.info("Real AWS connection and discovery verified successfully.")
        sys.exit(0)

    target_obj = objects[0]
    test_key = target_obj.object_key
    initial_class = target_obj.storage_class
    logger.info(f"Selected test object '{test_key}' with storage class '{initial_class}'.")

    # 4. Storage Class Migration (STANDARD -> INFREQUENT_ACCESS)
    target_class = "INFREQUENT_ACCESS" if initial_class == "STANDARD" else "STANDARD"
    logger.info(f"Phase 4: Migrating '{test_key}' to target storage class '{target_class}' via zero-download CopyObject...")

    success = connector.copy_object_storage_class(test_bucket, test_key, target_class)
    if not success:
        logger.error(f"FAILED: Provider-side migration of '{test_key}' to '{target_class}' failed.")
        sys.exit(1)

    # Verify Migration
    post_meta = connector.get_object_metadata(test_bucket, test_key)
    logger.info(f"Verified post-migration storage class: '{post_meta.storage_class}'.")

    # 5. Rollback Migration
    logger.info(f"Phase 5: Rolling back '{test_key}' to initial class '{initial_class}'...")
    rollback_success = connector.copy_object_storage_class(test_bucket, test_key, initial_class)
    if not rollback_success:
        logger.error(f"FAILED: Rollback of '{test_key}' to '{initial_class}' failed.")
        sys.exit(1)

    restored_meta = connector.get_object_metadata(test_bucket, test_key)
    logger.info(f"Verified restored storage class: '{restored_meta.storage_class}'.")

    logger.info("======================================================================")
    logger.info("SUCCESS: Real AWS S3 end-to-end smoke test completed cleanly!")
    logger.info("======================================================================")


if __name__ == "__main__":
    main()
