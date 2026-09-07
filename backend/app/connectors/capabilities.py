"""
Provider capability abstraction for Storage Lifecycle Optimizer.
Defines strongly typed capabilities per cloud storage provider to decouple business logic from provider specifics.
"""

from typing import List, Union
from pydantic import BaseModel, Field
from app.models.storage import StorageProviderEnum


class ProviderCapabilities(BaseModel):
    """Strongly typed capability model representing cloud provider capabilities and restrictions."""

    provider: str = Field(..., description="Storage provider identifier (e.g., LOCAL_S3_COMPATIBLE, AWS_S3, AZURE_BLOB, GOOGLE_CLOUD_STORAGE)")
    supports_list_objects: bool = Field(default=True, description="Supports discovery of object metadata with pagination")
    supports_get_metadata: bool = Field(default=True, description="Supports HEAD metadata retrieval")
    supports_get_storage_class: bool = Field(default=True, description="Supports inspection of current storage tier/class")
    supports_in_place_tiering: bool = Field(..., description="Supports changing object storage tier without copying payload")
    supports_copy_based_migration: bool = Field(..., description="Supports copy_object with target storage class header")
    supports_storage_class_migration: bool = Field(..., description="Supports zero-download lifecycle storage class migration")
    supports_rollback: bool = Field(..., description="Supports migrating object back to original storage class")
    supports_archive_restore: bool = Field(..., description="Requires asynchronous restore request before reading archived objects")
    supports_immediate_archive_read: bool = Field(..., description="Supports immediate byte read from archive storage class")
    supports_pagination: bool = Field(default=True, description="Supports paginated object listing using continuation tokens")
    native_storage_classes: List[str] = Field(default_factory=list, description="Supported provider-native storage class names")


# Static Capability Catalog for supported and upcoming providers
PROVIDER_CAPABILITIES_CATALOG = {
    "LOCAL_S3_COMPATIBLE": ProviderCapabilities(
        provider="LOCAL_S3_COMPATIBLE",
        supports_list_objects=True,
        supports_get_metadata=True,
        supports_get_storage_class=True,
        supports_in_place_tiering=False,
        supports_copy_based_migration=True,
        supports_storage_class_migration=True,
        supports_rollback=True,
        supports_archive_restore=False,
        supports_immediate_archive_read=True,
        supports_pagination=True,
        native_storage_classes=["STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE"],
    ),
    "AWS_S3": ProviderCapabilities(
        provider="AWS_S3",
        supports_list_objects=True,
        supports_get_metadata=True,
        supports_get_storage_class=True,
        supports_in_place_tiering=False,
        supports_copy_based_migration=True,
        supports_storage_class_migration=True,
        supports_rollback=True,
        supports_archive_restore=True,
        supports_immediate_archive_read=False,
        supports_pagination=True,
        native_storage_classes=["STANDARD", "STANDARD_IA", "ONEZONE_IA", "GLACIER_IR", "GLACIER", "DEEP_ARCHIVE", "INTELLIGENT_TIERING"],
    ),
    "AZURE_BLOB": ProviderCapabilities(
        provider="AZURE_BLOB",
        supports_list_objects=True,
        supports_get_metadata=True,
        supports_get_storage_class=True,
        supports_in_place_tiering=True,
        supports_copy_based_migration=False,
        supports_storage_class_migration=True,
        supports_rollback=True,
        supports_archive_restore=True,
        supports_immediate_archive_read=False,
        supports_pagination=True,
        native_storage_classes=["Hot", "Cool", "Cold", "Archive"],
    ),
    "GOOGLE_CLOUD_STORAGE": ProviderCapabilities(
        provider="GOOGLE_CLOUD_STORAGE",
        supports_list_objects=True,
        supports_get_metadata=True,
        supports_get_storage_class=True,
        supports_in_place_tiering=True,
        supports_copy_based_migration=False,
        supports_storage_class_migration=True,
        supports_rollback=True,
        supports_archive_restore=False,
        supports_immediate_archive_read=True,
        supports_pagination=True,
        native_storage_classes=["STANDARD", "NEARLINE", "COLDLINE", "ARCHIVE"],
    ),
}


def get_provider_capabilities(provider: Union[StorageProviderEnum, str]) -> ProviderCapabilities:
    """
    Returns ProviderCapabilities for a given provider.
    Fails safely if provider is unknown.
    """
    provider_str = provider.value if hasattr(provider, "value") else str(provider).upper()
    if provider_str not in PROVIDER_CAPABILITIES_CATALOG:
        raise ValueError(f"Unknown or unsupported storage provider '{provider_str}'.")
    return PROVIDER_CAPABILITIES_CATALOG[provider_str]
