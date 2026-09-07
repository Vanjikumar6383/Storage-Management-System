"""
Unit tests for ConnectorFactory and provider resolution safety.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from app.db.database import SessionLocal
from app.models import Organization, StorageConnection, StorageLocation, StorageObject, StorageProviderEnum, Recommendation, ApprovalRequest, MigrationEvent
from app.connectors.factory import ConnectorFactory, UnsupportedProviderError
from app.connectors.s3_connector import LocalS3Connector
from app.jobs.sync_job import run_connection_sync
from app.services.approval_execution import ApprovalExecutionService


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_factory_local_s3_compatible(db_session):
    """TEST A: LOCAL_S3_COMPATIBLE returns LocalS3Connector instance."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="Local S3 Test Connection",
        provider=StorageProviderEnum.LOCAL_S3_COMPATIBLE,
        credential_reference="env:S3_SECRET_KEY",
        config={"endpoint_url": "http://localhost:9000", "region": "us-east-1"},
    )
    db_session.add(conn)
    db_session.commit()

    connector = ConnectorFactory.get_connector_for_connection(db_session, conn)
    assert isinstance(connector, LocalS3Connector)
    assert connector.endpoint_url == "http://localhost:9000"


def test_factory_aws_s3_supported(db_session):
    """TEST B: AWS_S3 returns AWSS3Connector (no silent fallback)."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="AWS S3 Test Connection",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="arn:aws:iam::123456789012:role/StorageOptimizerRole",
        config={"bucket_name": "prod-aws-bucket"},
    )
    db_session.add(conn)
    db_session.commit()

    connector = ConnectorFactory.get_connector_for_connection(db_session, conn)
    from app.connectors.aws_s3_connector import AWSS3Connector
    assert isinstance(connector, AWSS3Connector)
    assert not isinstance(connector, LocalS3Connector)


def test_factory_azure_blob_unsupported(db_session):
    """TEST C: AZURE_BLOB raises UnsupportedProviderError."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="Azure Blob Test Connection",
        provider=StorageProviderEnum.AZURE_BLOB,
        credential_reference="vault:azure-conn-string",
        config={"container_name": "prod-azure-container"},
    )
    db_session.add(conn)
    db_session.commit()

    with pytest.raises(UnsupportedProviderError) as exc_info:
        ConnectorFactory.get_connector_for_connection(db_session, conn)
    assert "AZURE_BLOB" in str(exc_info.value)


def test_factory_gcp_storage_unsupported(db_session):
    """TEST D: GOOGLE_CLOUD_STORAGE raises UnsupportedProviderError."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="GCP Test Connection",
        provider=StorageProviderEnum.GOOGLE_CLOUD_STORAGE,
        credential_reference="vault:gcp-service-account",
        config={"bucket_name": "prod-gcp-bucket"},
    )
    db_session.add(conn)
    db_session.commit()

    with pytest.raises(UnsupportedProviderError) as exc_info:
        ConnectorFactory.get_connector_for_connection(db_session, conn)
    assert "GOOGLE_CLOUD_STORAGE" in str(exc_info.value)


def test_factory_unknown_provider_fails_safely(db_session):
    """TEST E: Unknown/invalid provider string fails safely without fallback."""
    class DummyConnection:
        provider = "UNKNOWN_CLOUD_PROVIDER"
        name = "Unknown Conn"
        id = uuid4()
        config = {}

    with pytest.raises(UnsupportedProviderError):
        ConnectorFactory.get_connector_for_connection(db_session, DummyConnection())


def test_sync_job_uses_factory_and_fails_on_unsupported_provider(db_session):
    """TEST F: Verify sync_job uses ConnectorFactory and fails safely for Azure Blob."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="Azure Sync Connection",
        provider=StorageProviderEnum.AZURE_BLOB,
        credential_reference="vault:azure-key",
        config={},
    )
    db_session.add(conn)
    db_session.commit()

    sync_log = run_connection_sync(db_session, conn.id)
    assert sync_log.status == "FAILED"
    assert "AZURE_BLOB" in sync_log.error_summary
    assert "not yet implemented" in sync_log.error_summary


def test_approval_execution_migration_uses_factory_and_fails_on_unsupported_provider(db_session):
    """TEST G: Verify approval execution migration uses ConnectorFactory and fails for Azure Blob."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="Azure Migration Connection",
        provider=StorageProviderEnum.AZURE_BLOB,
        credential_reference="vault:azure-key",
        config={},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="azure-test-container",
        region="eastus",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"azure/blob_{uuid4().hex[:6]}.dat",
        object_size_bytes=5 * 1024 * 1024,
        storage_class="STANDARD",
        created_at=ref_time - timedelta(days=200),
        last_modified_at=ref_time - timedelta(days=200),
    )
    db_session.add(obj)
    db_session.commit()

    rec = Recommendation(
        organization_id=org.id,
        object_id=obj.id,
        recommendation_type="ARCHIVE",
        current_storage_class="STANDARD",
        recommended_storage_class="ARCHIVE",
        reason="Test recommendation",
        risk_level="LOW",
        status="APPROVED",
    )
    db_session.add(rec)
    db_session.commit()

    service = ApprovalExecutionService()
    appr = service.create_or_get_approval_request(db_session, org.id, rec.id)
    appr.status = "APPROVED"
    db_session.commit()

    result = service.execute_recommendation(db_session, org.id, rec.id)
    assert result.status == "FAILED"
    assert any("AZURE_BLOB" in r for r in result.reasons)


def test_approval_execution_rollback_uses_factory_and_fails_on_unsupported_provider(db_session):
    """TEST H: Verify rollback uses ConnectorFactory and fails safely for GCP."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    conn = StorageConnection(
        organization_id=org.id,
        name="GCP Rollback Connection",
        provider=StorageProviderEnum.GOOGLE_CLOUD_STORAGE,
        credential_reference="vault:gcp-key",
        config={},
    )
    db_session.add(conn)
    db_session.commit()

    loc = StorageLocation(
        organization_id=org.id,
        storage_connection_id=conn.id,
        name="gcp-test-bucket",
        region="us-central1",
    )
    db_session.add(loc)
    db_session.commit()

    ref_time = datetime.now(timezone.utc)
    obj = StorageObject(
        organization_id=org.id,
        storage_location_id=loc.id,
        object_key=f"gcp/data_{uuid4().hex[:6]}.bin",
        object_size_bytes=1024,
        storage_class="ARCHIVE",
        created_at=ref_time,
        last_modified_at=ref_time,
    )
    db_session.add(obj)
    db_session.commit()

    mig = MigrationEvent(
        organization_id=org.id,
        object_id=obj.id,
        source_storage_class="STANDARD",
        destination_storage_class="ARCHIVE",
        status="SUCCESS",
        rollback_status="AVAILABLE",
    )
    db_session.add(mig)
    db_session.commit()

    service = ApprovalExecutionService()
    rb_res = service.rollback_migration(db_session, org.id, mig.id, reason="Test rollback GCP")
    assert rb_res.status == "FAILED"
    assert any("GOOGLE_CLOUD_STORAGE" in r for r in rb_res.reasons)


def test_no_provider_falls_back_to_local_s3(db_session):
    """TEST I: Confirm non-local providers never fall back to LocalS3Connector."""
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    for prov in [StorageProviderEnum.AZURE_BLOB, StorageProviderEnum.GOOGLE_CLOUD_STORAGE]:
        conn = StorageConnection(
            organization_id=org.id,
            name=f"No Fallback {prov.value}",
            provider=prov,
            credential_reference="dummy",
            config={},
        )
        db_session.add(conn)
        db_session.commit()

        with pytest.raises(UnsupportedProviderError):
            ConnectorFactory.get_connector_for_connection(db_session, conn)

    # Verify AWS_S3 returns AWSS3Connector and NOT LocalS3Connector
    aws_conn = StorageConnection(
        organization_id=org.id,
        name="AWS No Fallback Test",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="dummy",
        config={},
    )
    db_session.add(aws_conn)
    db_session.commit()

    connector = ConnectorFactory.get_connector_for_connection(db_session, aws_conn)
    from app.connectors.aws_s3_connector import AWSS3Connector
    assert isinstance(connector, AWSS3Connector)
    assert not isinstance(connector, LocalS3Connector)
