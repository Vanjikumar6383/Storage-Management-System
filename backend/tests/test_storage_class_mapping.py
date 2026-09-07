"""
Unit tests for StorageClassMapper abstraction.
"""

import pytest
from app.connectors.storage_class_mapper import (
    StorageClassMapper,
    NORMALIZED_STANDARD,
    NORMALIZED_INFREQUENT,
    NORMALIZED_ARCHIVE,
)
from app.models.storage import StorageProviderEnum


def test_aws_s3_storage_class_mapping():
    """Verify AWS S3 native <-> normalized storage class mappings."""
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AWS_S3, "STANDARD") == NORMALIZED_STANDARD
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AWS_S3, "STANDARD_IA") == NORMALIZED_INFREQUENT
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AWS_S3, "ONEZONE_IA") == NORMALIZED_INFREQUENT
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AWS_S3, "GLACIER") == NORMALIZED_ARCHIVE
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AWS_S3, "DEEP_ARCHIVE") == NORMALIZED_ARCHIVE

    # Reverse mappings
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.AWS_S3, NORMALIZED_STANDARD) == "STANDARD"
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.AWS_S3, NORMALIZED_INFREQUENT) == "STANDARD_IA"
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.AWS_S3, NORMALIZED_ARCHIVE) == "GLACIER"


def test_azure_blob_storage_class_mapping():
    """Verify Azure Blob native <-> normalized storage class mappings."""
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AZURE_BLOB, "Hot") == NORMALIZED_STANDARD
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AZURE_BLOB, "Cool") == NORMALIZED_INFREQUENT
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AZURE_BLOB, "Cold") == NORMALIZED_INFREQUENT
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.AZURE_BLOB, "Archive") == NORMALIZED_ARCHIVE

    # Reverse mappings
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.AZURE_BLOB, NORMALIZED_STANDARD) == "Hot"
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.AZURE_BLOB, NORMALIZED_INFREQUENT) == "Cool"
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.AZURE_BLOB, NORMALIZED_ARCHIVE) == "Archive"


def test_gcs_storage_class_mapping():
    """Verify Google Cloud Storage native <-> normalized storage class mappings."""
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.GOOGLE_CLOUD_STORAGE, "STANDARD") == NORMALIZED_STANDARD
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.GOOGLE_CLOUD_STORAGE, "NEARLINE") == NORMALIZED_INFREQUENT
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.GOOGLE_CLOUD_STORAGE, "COLDLINE") == NORMALIZED_INFREQUENT
    assert StorageClassMapper.to_normalized_class(StorageProviderEnum.GOOGLE_CLOUD_STORAGE, "ARCHIVE") == NORMALIZED_ARCHIVE

    # Reverse mappings
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.GOOGLE_CLOUD_STORAGE, NORMALIZED_STANDARD) == "STANDARD"
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.GOOGLE_CLOUD_STORAGE, NORMALIZED_INFREQUENT) == "NEARLINE"
    assert StorageClassMapper.from_normalized_class(StorageProviderEnum.GOOGLE_CLOUD_STORAGE, NORMALIZED_ARCHIVE) == "ARCHIVE"


def test_lossy_mapping_notes():
    """Verify lossy mapping detection and notes."""
    is_lossy, note = StorageClassMapper.is_lossy_mapping(StorageProviderEnum.AWS_S3, "INTELLIGENT_TIERING")
    assert is_lossy is True
    assert "INTELLIGENT_TIERING" in note

    is_lossy_azure, note_azure = StorageClassMapper.is_lossy_mapping(StorageProviderEnum.AZURE_BLOB, "Cold")
    assert is_lossy_azure is True
    assert "Cold" in note_azure

    is_lossy_std, _ = StorageClassMapper.is_lossy_mapping(StorageProviderEnum.AWS_S3, "STANDARD")
    assert is_lossy_std is False


def test_invalid_storage_class_fails_safely():
    """Verify invalid or unknown native/normalized storage class raises ValueError safely."""
    with pytest.raises(ValueError) as exc_info1:
        StorageClassMapper.to_normalized_class(StorageProviderEnum.AWS_S3, "SUPER_INVALID_CLASS")
    assert "Unknown native storage class" in str(exc_info1.value)

    with pytest.raises(ValueError) as exc_info2:
        StorageClassMapper.from_normalized_class(StorageProviderEnum.AWS_S3, "INVALID_NORM")
    assert "Invalid normalized storage class" in str(exc_info2.value)
