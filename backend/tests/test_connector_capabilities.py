"""
Unit tests for Provider Capabilities Abstraction.
"""

import pytest
from app.connectors.capabilities import (
    ProviderCapabilities,
    get_provider_capabilities,
    PROVIDER_CAPABILITIES_CATALOG,
)
from app.connectors.s3_connector import LocalS3Connector
from app.models.storage import StorageProviderEnum


def test_local_s3_capabilities():
    """Verify LocalS3Connector exposes capabilities property correctly."""
    connector = LocalS3Connector()
    caps = connector.capabilities

    assert isinstance(caps, ProviderCapabilities)
    assert caps.provider == "LOCAL_S3_COMPATIBLE"
    assert caps.supports_copy_based_migration is True
    assert caps.supports_in_place_tiering is False
    assert caps.supports_storage_class_migration is True
    assert caps.supports_rollback is True
    assert caps.supports_archive_restore is False
    assert caps.supports_immediate_archive_read is True
    assert "STANDARD" in caps.native_storage_classes
    assert "GLACIER" in caps.native_storage_classes


def test_provider_capabilities_catalog_entries():
    """Verify capabilities exist for AWS, Azure, and GCS in catalog."""
    aws_caps = get_provider_capabilities(StorageProviderEnum.AWS_S3)
    assert aws_caps.provider == "AWS_S3"
    assert aws_caps.supports_copy_based_migration is True
    assert aws_caps.supports_archive_restore is True
    assert aws_caps.supports_immediate_archive_read is False

    azure_caps = get_provider_capabilities(StorageProviderEnum.AZURE_BLOB)
    assert azure_caps.provider == "AZURE_BLOB"
    assert azure_caps.supports_in_place_tiering is True
    assert azure_caps.supports_copy_based_migration is False
    assert azure_caps.supports_archive_restore is True

    gcp_caps = get_provider_capabilities(StorageProviderEnum.GOOGLE_CLOUD_STORAGE)
    assert gcp_caps.provider == "GOOGLE_CLOUD_STORAGE"
    assert gcp_caps.supports_in_place_tiering is True
    assert gcp_caps.supports_immediate_archive_read is True


def test_unknown_provider_capability_fails_safely():
    """Verify querying capabilities for unknown provider raises ValueError safely."""
    with pytest.raises(ValueError) as exc_info:
        get_provider_capabilities("INVALID_UNKNOWN_CLOUD")
    assert "Unknown or unsupported storage provider" in str(exc_info.value)
