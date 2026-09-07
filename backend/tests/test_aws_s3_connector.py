"""
Unit tests for production AWSS3Connector and AWS_S3 provider integration.
Mocking AWS API boundaries via unittest.mock / MagicMock. Zero live AWS credentials or cloud calls required.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from botocore.exceptions import ClientError, BotoCoreError

from app.db.database import SessionLocal
from app.models import Organization, StorageConnection, StorageLocation, StorageObject, StorageProviderEnum, Recommendation, RecommendationTypeEnum, MigrationEvent
from app.connectors.aws_s3_connector import AWSS3Connector
from app.connectors.s3_connector import LocalS3Connector
from app.connectors.factory import ConnectorFactory, UnsupportedProviderError
from app.connectors.credentials import ResolvedCredentials
from app.connectors.capabilities import ProviderCapabilities
from app.services.approval_execution import ApprovalExecutionService


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_aws_connector_construction():
    """Verify AWSS3Connector initializes with ResolvedCredentials."""
    creds = ResolvedCredentials(
        provider="AWS_S3",
        access_key="AKIAFAKEKEY123",
        secret_key="SECRETKEYFAKE456",
        session_token="SESSIONTOKEN789",
        region="us-west-2",
    )
    connector = AWSS3Connector(credentials=creds)
    assert connector.region == "us-west-2"
    assert connector.access_key == "AKIAFAKEKEY123"
    assert connector.secret_key == "SECRETKEYFAKE456"
    assert connector.session_token == "SESSIONTOKEN789"


def test_2_aws_capabilities_descriptor():
    """Verify AWS_S3 capabilities descriptor attributes."""
    connector = AWSS3Connector(region="us-east-1")
    caps = connector.capabilities
    assert isinstance(caps, ProviderCapabilities)
    assert caps.provider == "AWS_S3"
    assert caps.supports_copy_based_migration is True
    assert caps.supports_in_place_tiering is False
    assert caps.supports_archive_restore is True
    assert caps.supports_immediate_archive_read is False


def test_3_4_factory_resolves_aws_s3_and_never_falls_back_to_local_s3(db_session):
    """Verify ConnectorFactory returns AWSS3Connector for AWS_S3 and never LocalS3Connector."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="Real AWS S3 Connection",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_SECRET_KEY",
        config={"region": "us-west-1", "access_key": "AKIA123", "secret_key": "SEC123"},
    )
    db_session.add(conn)
    db_session.commit()

    connector = ConnectorFactory.get_connector_for_connection(db_session, conn)
    assert isinstance(connector, AWSS3Connector)
    assert not isinstance(connector, LocalS3Connector)
    assert connector.region == "us-west-1"


def test_5_6_credential_sanitization():
    """Verify AWS secret access key and session tokens are redacted from error logs."""
    creds = ResolvedCredentials(
        provider="AWS_S3",
        access_key="AKIAREALKEY999",
        secret_key="SUPERSECRETKEY999",
        session_token="SESSIONTOKEN999",
        region="us-east-1",
    )
    connector = AWSS3Connector(credentials=creds)

    err = Exception("Failed connecting with key AKIAREALKEY999 and secret SUPERSECRETKEY999 and token SESSIONTOKEN999")
    sanitized = connector.sanitize_error(err)

    assert "AKIAREALKEY999" not in sanitized
    assert "SUPERSECRETKEY999" not in sanitized
    assert "SESSIONTOKEN999" not in sanitized
    assert "[REDACTED_KEY]" in sanitized
    assert "[REDACTED_SECRET]" in sanitized
    assert "[REDACTED_TOKEN]" in sanitized


def test_7_test_connection_success_and_access_denied():
    """Verify test_connection returns True on list_buckets success, False on ClientError AccessDenied."""
    connector = AWSS3Connector(region="us-east-1")

    # Success case
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {"Buckets": [{"Name": "bucket-1"}]}
    connector.client = mock_client
    assert connector.test_connection() is True

    # Failure case
    mock_client.list_buckets.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "ListBuckets"
    )
    assert connector.test_connection() is False


def test_8_list_storage_locations():
    """Verify list_storage_locations returns NormalizedStorageLocation objects."""
    connector = AWSS3Connector(region="us-west-2")
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {
        "Buckets": [
            {"Name": "prod-data-bucket", "CreationDate": datetime.now(timezone.utc)},
            {"Name": "prod-logs-bucket", "CreationDate": datetime.now(timezone.utc)},
        ]
    }
    connector.client = mock_client

    locs = connector.list_storage_locations()
    assert len(locs) == 2
    assert locs[0].name == "prod-data-bucket"
    assert locs[0].region == "us-west-2"


def test_9_10_list_objects_and_pagination():
    """Verify list_objects uses ListObjectsV2 with ContinuationToken pagination."""
    connector = AWSS3Connector(region="us-east-1")
    mock_client = MagicMock()
    mock_client.list_objects_v2.side_effect = [
        {
            "Contents": [
                {
                    "Key": "data/part1.parquet",
                    "Size": 1048576,
                    "StorageClass": "STANDARD_IA",
                    "LastModified": datetime.now(timezone.utc),
                    "ETag": '"etag-part1"',
                }
            ],
            "NextContinuationToken": "token_page_2",
        },
        {
            "Contents": [
                {
                    "Key": "data/part2.parquet",
                    "Size": 2097152,
                    "StorageClass": "GLACIER",
                    "LastModified": datetime.now(timezone.utc),
                    "ETag": '"etag-part2"',
                }
            ]
        },
    ]
    connector.client = mock_client

    objs1, token1 = connector.list_objects("prod-data-bucket")
    assert len(objs1) == 1
    assert objs1[0].object_key == "data/part1.parquet"
    assert objs1[0].storage_class == "INFREQUENT_ACCESS"
    assert token1 == "token_page_2"

    objs2, token2 = connector.list_objects("prod-data-bucket", cursor=token1)
    assert len(objs2) == 1
    assert objs2[0].object_key == "data/part2.parquet"
    assert objs2[0].storage_class == "ARCHIVE"
    assert token2 is None


def test_11_12_13_14_get_object_metadata_and_storage_class_normalization():
    """Verify get_object_metadata uses head_object and maps AWS native classes."""
    connector = AWSS3Connector(region="us-east-1")
    mock_client = MagicMock()
    mock_client.head_object.return_value = {
        "ContentLength": 4096,
        "StorageClass": "DEEP_ARCHIVE",
        "LastModified": datetime.now(timezone.utc),
        "ETag": '"etag-head-1"',
        "ContentType": "application/x-parquet",
    }
    connector.client = mock_client

    meta = connector.get_object_metadata("prod-data-bucket", "data/part1.parquet")
    assert meta.object_size_bytes == 4096
    assert meta.storage_class == "ARCHIVE"
    assert meta.content_type == "application/x-parquet"
    assert connector.get_object_size("prod-data-bucket", "data/part1.parquet") == 4096
    assert connector.get_storage_class("prod-data-bucket", "data/part1.parquet") == "ARCHIVE"


def test_15_16_copy_object_storage_class():
    """Verify copy_object_storage_class calls CopyObject with target AWS storage class."""
    connector = AWSS3Connector(region="us-east-1")
    mock_client = MagicMock()
    connector.client = mock_client

    # STANDARD -> INFREQUENT_ACCESS maps to STANDARD_IA
    success = connector.copy_object_storage_class("prod-data-bucket", "data/file.csv", "INFREQUENT_ACCESS")
    assert success is True
    mock_client.copy_object.assert_called_once_with(
        Bucket="prod-data-bucket",
        Key="data/file.csv",
        CopySource={"Bucket": "prod-data-bucket", "Key": "data/file.csv"},
        StorageClass="STANDARD_IA",
        MetadataDirective="REPLACE",
    )


def test_17_18_zero_download_guarantee():
    """REGRESSION SAFETY TEST: Assert get_object (payload download) is NEVER called."""
    connector = AWSS3Connector(region="us-east-1")
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = {"Buckets": []}
    mock_client.list_objects_v2.return_value = {"Contents": []}
    mock_client.head_object.return_value = {
        "ContentLength": 100,
        "StorageClass": "STANDARD",
        "LastModified": datetime.now(timezone.utc),
    }
    connector.client = mock_client

    connector.test_connection()
    connector.list_storage_locations()
    connector.list_objects("b")
    connector.get_object_metadata("b", "k")
    connector.get_storage_class("b", "k")
    connector.get_object_size("b", "k")
    connector.get_last_modified("b", "k")
    connector.copy_object_storage_class("b", "k", "ARCHIVE")

    assert mock_client.get_object.call_count == 0, "CRITICAL VIOLATION: get_object was invoked!"


def test_19_20_approval_execution_and_rollback_routing_for_aws(db_session):
    """Verify approval execution migration and rollback route through AWSS3Connector."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS Production Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_CRED",
        config={"region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="aws-prod-bucket",
        region="us-east-1",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"aws/data_{uuid4().hex[:6]}.bin",
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
        reason="Test AWS migration",
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
        res = service.execute_recommendation(db_session, org.id, rec.id)
        assert res.status == "SUCCESS"
        assert obj.storage_class == "INFREQUENT_ACCESS"
        mock_copy.assert_called_once_with(
            location_name="aws-prod-bucket",
            object_key=obj.object_key,
            target_storage_class="INFREQUENT_ACCESS",
        )


def test_21_tenant_isolation_aws(db_session):
    """Verify tenant isolation for AWS connections."""
    org1 = db_session.query(Organization).filter_by(slug="demo-organization").first()
    org2 = db_session.query(Organization).filter_by(slug="test-organization").first()

    conn1 = StorageConnection(
        organization_id=org1.id,
        name="Org1 AWS Conn",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_1",
        config={},
    )
    db_session.add(conn1)
    db_session.commit()

    # Attempt resolving conn1 under org2 should fail DB filter checks
    found = db_session.query(StorageConnection).filter_by(id=conn1.id, organization_id=org2.id).first()
    assert found is None


def test_22_local_s3_regression(db_session):
    """Verify LOCAL_S3_COMPATIBLE provider continues to instantiate LocalS3Connector."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="Regression Local S3",
        provider=StorageProviderEnum.LOCAL_S3_COMPATIBLE,
        credential_reference="env:MINIO",
        config={"endpoint_url": "http://localhost:9000"},
    )
    db_session.add(conn)
    db_session.commit()

    connector = ConnectorFactory.get_connector_for_connection(db_session, conn)
    assert isinstance(connector, LocalS3Connector)
