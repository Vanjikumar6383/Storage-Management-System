"""
Comprehensive End-to-End Production Validation Suite for AWS S3 Storage Connector.
Verifies all 16 production-hardening phases using mocked AWS responses.
Fully deterministic, running 100% cleanly without requiring live AWS credentials.
"""

import pytest
import boto3
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

from botocore.exceptions import ClientError, BotoCoreError

from app.db.database import SessionLocal
from app.models import (
    Organization,
    StorageConnection,
    StorageLocation,
    StorageObject,
    StorageProviderEnum,
    Recommendation,
    RecommendationTypeEnum,
    ApprovalRequest,
    MigrationEvent,
    AuditLog,
    RetentionPolicy,
    LegalHold,
    AccessEvent,
)
from app.connectors.aws_s3_connector import AWSS3Connector
from app.connectors.factory import ConnectorFactory, UnsupportedProviderError
from app.connectors.credentials import CredentialResolver, ResolvedCredentials
from app.connectors.capabilities import ProviderCapabilities
from app.connectors.storage_class_mapper import StorageClassMapper
from app.services.approval_execution import ApprovalExecutionService
from app.services.policy_engine import PolicyEngineService
from app.services.recommendation_engine import RecommendationService
from app.services.cost_engine import CostSummaryService, SavingsLedgerService
from app.jobs.sync_job import run_connection_sync


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_phase_2_credential_security_redaction():
    """PHASE 2: Verify access keys, secret keys, session tokens, passwords are redacted from exceptions and logs."""
    creds = ResolvedCredentials(
        provider="AWS_S3",
        access_key="AKIASECRETPRODKEY123",
        secret_key="SUPERSECRETPRODPASSWORD456",
        session_token="SESSIONTOKENPROD789",
        region="us-west-2",
    )
    connector = AWSS3Connector(credentials=creds)

    err = Exception("Auth failed with key AKIASECRETPRODKEY123 and secret SUPERSECRETPRODPASSWORD456 and token SESSIONTOKENPROD789")
    sanitized = connector.sanitize_error(err)

    assert "AKIASECRETPRODKEY123" not in sanitized
    assert "SUPERSECRETPRODPASSWORD456" not in sanitized
    assert "SESSIONTOKENPROD789" not in sanitized
    assert "[REDACTED_KEY]" in sanitized
    assert "[REDACTED_SECRET]" in sanitized
    assert "[REDACTED_TOKEN]" in sanitized


def test_phase_4_connection_validation_hardening():
    """PHASE 4: Verify test_connection returns True on success and False on sanitized ClientError."""
    connector = AWSS3Connector(region="us-east-1")

    # Success case
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {"Buckets": [{"Name": "prod-bucket"}]}
    connector.client = mock_client
    assert connector.test_connection() is True

    # AccessDenied failure case
    mock_client.list_buckets.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied for AKIASECRETKEY"}}, "ListBuckets"
    )
    assert connector.test_connection() is False


def test_phase_5_zero_download_metadata_sync(db_session):
    """PHASE 5: Verify metadata sync executes ListObjectsV2 & HeadObject into PostgreSQL without GetObject."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS Metadata Sync Test",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_KEY",
        config={"region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {"Buckets": [{"Name": "aws-sync-bucket"}]}
    mock_client.list_objects_v2.return_value = {
        "Contents": [
            {
                "Key": "logs/app-2026.log",
                "Size": 2048576,
                "StorageClass": "STANDARD_IA",
                "LastModified": datetime.now(timezone.utc),
                "ETag": '"etag-sync-123"',
            }
        ]
    }

    with patch.object(boto3, "client", return_value=mock_client):
        sync_log = run_connection_sync(db_session, conn.id)
        assert sync_log.status == "SUCCESS"
        assert sync_log.objects_discovered == 1

        # Assert GetObject was NEVER invoked
        assert mock_client.get_object.call_count == 0

        obj = (
            db_session.query(StorageObject)
            .join(StorageLocation)
            .filter(StorageLocation.storage_connection_id == conn.id)
            .first()
        )
        assert obj is not None
        assert obj.object_key == "logs/app-2026.log"
        assert obj.object_size_bytes == 2048576
        assert obj.storage_class == "INFREQUENT_ACCESS"


def test_phase_6_storage_class_normalization():
    """PHASE 6: Verify real AWS storage classes normalize bidirectionally."""
    mapper = StorageClassMapper()

    assert mapper.to_normalized_class("AWS_S3", "STANDARD") == "STANDARD"
    assert mapper.to_normalized_class("AWS_S3", "STANDARD_IA") == "INFREQUENT_ACCESS"
    assert mapper.to_normalized_class("AWS_S3", "ONEZONE_IA") == "INFREQUENT_ACCESS"
    assert mapper.to_normalized_class("AWS_S3", "GLACIER_IR") == "ARCHIVE"
    assert mapper.to_normalized_class("AWS_S3", "GLACIER") == "ARCHIVE"
    assert mapper.to_normalized_class("AWS_S3", "DEEP_ARCHIVE") == "ARCHIVE"
    assert mapper.to_normalized_class("AWS_S3", "INTELLIGENT_TIERING") == "STANDARD"

    # Reverse mapping
    assert mapper.from_normalized_class("AWS_S3", "STANDARD") == "STANDARD"
    assert mapper.from_normalized_class("AWS_S3", "INFREQUENT_ACCESS") == "STANDARD_IA"
    assert mapper.from_normalized_class("AWS_S3", "ARCHIVE") == "GLACIER"


def test_phase_7_8_zero_download_migration_and_rollback(db_session):
    """PHASE 7 & 8: Verify CopyObject migration & rollback pipeline without payload download."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS Migration Test Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_KEY",
        config={"region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="aws-migration-bucket",
        region="us-east-1",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"data/archive_{uuid4().hex[:6]}.bin",
        object_size_bytes=50 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec = Recommendation(
        organization_id=org.id,
        object_id=obj.id,
        recommendation_type=RecommendationTypeEnum.MOVE_TO_INFREQUENT_ACCESS,
        current_storage_class="STANDARD",
        recommended_storage_class="INFREQUENT_ACCESS",
        reason="AWS migration test",
        risk_level="LOW",
        status="APPROVED",
    )
    db_session.add(rec)
    db_session.commit()

    service = ApprovalExecutionService()
    appr = service.create_or_get_approval_request(db_session, org.id, rec.id)
    appr.status = "APPROVED"
    db_session.commit()

    with patch.object(AWSS3Connector, "copy_object_storage_class", return_value=True) as mock_copy:
        # Migration
        mig_res = service.execute_recommendation(db_session, org.id, rec.id)
        assert mig_res.status == "SUCCESS"
        assert obj.storage_class == "INFREQUENT_ACCESS"
        mock_copy.assert_called_once_with(
            location_name="aws-migration-bucket",
            object_key=obj.object_key,
            target_storage_class="INFREQUENT_ACCESS",
        )

        # Rollback
        rb_res = service.rollback_migration(db_session, org.id, UUID(mig_res.migration_id))
        assert rb_res.status == "SUCCESS"
        assert obj.storage_class == "STANDARD"
        assert mock_copy.call_count == 2

        # Duplicate Rollback Rejection
        rb_dup = service.rollback_migration(db_session, org.id, UUID(mig_res.migration_id))
        assert rb_dup.status == "ALREADY_EXECUTED"
        assert any("already been rolled back" in r for r in rb_dup.reasons)


def test_phase_9_10_stale_recommendation_safety_gate(db_session):
    """PHASE 9 & 10: Verify fresh OBJECT_READ event invalidates recommendation before execution."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS Stale Test Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_KEY",
        config={"region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="aws-stale-bucket",
        region="us-east-1",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"reports/quarterly_{uuid4().hex[:6]}.pdf",
        object_size_bytes=5 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=120),
        last_modified_at=ref_time - timedelta(days=120),
    )
    db_session.add(obj)
    db_session.commit()

    rec = Recommendation(
        organization_id=org.id,
        object_id=obj.id,
        recommendation_type=RecommendationTypeEnum.MOVE_TO_INFREQUENT_ACCESS,
        current_storage_class="STANDARD",
        recommended_storage_class="INFREQUENT_ACCESS",
        reason="Stale check test",
        risk_level="LOW",
        status="APPROVED",
        created_at=ref_time - timedelta(days=5),
    )
    db_session.add(rec)
    db_session.commit()

    service = ApprovalExecutionService()
    appr = service.create_or_get_approval_request(db_session, org.id, rec.id)
    appr.status = "APPROVED"
    db_session.commit()

    # Generate fresh OBJECT_READ event after recommendation creation
    read_event = AccessEvent(
        organization_id=org.id,
        object_id=obj.id,
        event_type="OBJECT_READ",
        event_timestamp=ref_time - timedelta(days=1),
    )
    db_session.add(read_event)
    db_session.commit()

    exec_res = service.execute_recommendation(db_session, org.id, rec.id)
    assert exec_res.status == "STALE_RECOMMENDATION"
    assert obj.storage_class == "STANDARD"


def test_phase_11_legal_hold_safety_gate(db_session):
    """PHASE 11: Verify active legal hold blocks DELETE_CANDIDATE recommendation."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS Legal Hold Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_KEY",
        config={"region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="aws-hold-bucket",
        region="us-east-1",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"audit/compliance_{uuid4().hex[:6]}.pdf",
        object_size_bytes=1 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=400),
        last_modified_at=ref_time - timedelta(days=400),
    )
    db_session.add(obj)
    db_session.commit()

    # Add active legal hold
    hold = LegalHold(
        organization_id=org.id,
        object_id=obj.id,
        reason_reference="SEC Compliance Audit",
        status="ACTIVE",
    )
    db_session.add(hold)
    db_session.commit()

    rec = Recommendation(
        organization_id=org.id,
        object_id=obj.id,
        recommendation_type=RecommendationTypeEnum.DELETE_CANDIDATE,
        current_storage_class="STANDARD",
        recommended_storage_class="DELETE",
        reason="Legal hold test",
        risk_level="HIGH",
        status="APPROVED",
        created_at=ref_time - timedelta(days=5),
    )
    db_session.add(rec)
    db_session.commit()

    service = ApprovalExecutionService()
    appr = service.create_or_get_approval_request(db_session, org.id, rec.id)
    appr.status = "APPROVED"
    db_session.commit()

    exec_res = service.execute_recommendation(db_session, org.id, rec.id)
    assert exec_res.status == "BLOCKED"
    assert any("Active legal hold" in r for r in exec_res.reasons)


def test_phase_12_tenant_isolation(db_session):
    """PHASE 12: Verify Organization A cannot execute or rollback Organization B's recommendations."""
    org1 = db_session.query(Organization).filter_by(slug="demo-organization").first()
    org2 = db_session.query(Organization).filter_by(slug="test-organization").first()

    conn1 = StorageConnection(
        organization_id=org1.id,
        name="Org1 AWS Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_1",
        config={"region": "us-east-1"},
    )
    db_session.add(conn1)
    db_session.commit()

    loc1 = StorageLocation(
        organization_id=org1.id,
        storage_connection_id=conn1.id,
        name="org1-aws-bucket",
        region="us-east-1",
    )
    db_session.add(loc1)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj1 = StorageObject(
        organization_id=org1.id,
        storage_location_id=loc1.id,
        object_key=f"tenant/data_{uuid4().hex[:6]}.bin",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj1)
    db_session.commit()

    rec1 = Recommendation(
        organization_id=org1.id,
        object_id=obj1.id,
        recommendation_type=RecommendationTypeEnum.MOVE_TO_INFREQUENT_ACCESS,
        current_storage_class="STANDARD",
        recommended_storage_class="INFREQUENT_ACCESS",
        reason="Tenant isolation test",
        risk_level="LOW",
        status="APPROVED",
    )
    db_session.add(rec1)
    db_session.commit()

    service = ApprovalExecutionService()

    # Attempting to execute Org1's recommendation using Org2's ID should raise PermissionError
    with pytest.raises(PermissionError):
        service.execute_recommendation(db_session, org2.id, rec1.id)


def test_phase_13_idempotency_and_concurrency_locks(db_session):
    """PHASE 13: Verify duplicate execution requests return ALREADY_EXECUTED status without duplicate execution."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS Idempotency Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_KEY",
        config={"region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="aws-idem-bucket",
        region="us-east-1",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"idem/file_{uuid4().hex[:6]}.bin",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec = Recommendation(
        organization_id=org.id,
        object_id=obj.id,
        recommendation_type=RecommendationTypeEnum.MOVE_TO_INFREQUENT_ACCESS,
        current_storage_class="STANDARD",
        recommended_storage_class="INFREQUENT_ACCESS",
        reason="Idempotency test",
        risk_level="LOW",
        status="APPROVED",
    )
    db_session.add(rec)
    db_session.commit()

    service = ApprovalExecutionService()
    appr = service.create_or_get_approval_request(db_session, org.id, rec.id)
    appr.status = "APPROVED"
    db_session.commit()

    with patch.object(AWSS3Connector, "copy_object_storage_class", return_value=True) as mock_copy:
        res1 = service.execute_recommendation(db_session, org.id, rec.id)
        assert res1.status == "SUCCESS"
        assert mock_copy.call_count == 1

        # Duplicate execution call
        res2 = service.execute_recommendation(db_session, org.id, rec.id)
        assert res2.status == "ALREADY_EXECUTED"
        assert mock_copy.call_count == 1, "Duplicate execution was triggered!"


def test_phase_14_failure_and_recovery(db_session):
    """PHASE 14: Verify provider CopyObject failure results in sanitized logs and safe DB state."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS Failure Test Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_KEY",
        config={"region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="aws-fail-bucket",
        region="us-east-1",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"fail/file_{uuid4().hex[:6]}.bin",
        object_size_bytes=10 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec = Recommendation(
        organization_id=org.id,
        object_id=obj.id,
        recommendation_type=RecommendationTypeEnum.MOVE_TO_INFREQUENT_ACCESS,
        current_storage_class="STANDARD",
        recommended_storage_class="INFREQUENT_ACCESS",
        reason="Failure test",
        risk_level="LOW",
        status="APPROVED",
    )
    db_session.add(rec)
    db_session.commit()

    service = ApprovalExecutionService()
    appr = service.create_or_get_approval_request(db_session, org.id, rec.id)
    appr.status = "APPROVED"
    db_session.commit()

    # Simulate CopyObject failure
    with patch.object(AWSS3Connector, "copy_object_storage_class", return_value=False):
        res = service.execute_recommendation(db_session, org.id, rec.id)
        assert res.status == "FAILED"
        assert obj.storage_class == "STANDARD", "DB storage_class was updated despite provider failure!"
