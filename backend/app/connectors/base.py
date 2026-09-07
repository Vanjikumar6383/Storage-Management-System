"""
Provider-independent storage connector abstraction and normalized metadata models.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class NormalizedStorageLocation(BaseModel):
    """Normalized storage location representation (bucket / container / namespace)."""
    name: str = Field(..., description="Bucket, container, or namespace name")
    region: Optional[str] = Field(None, description="Cloud region or local zone")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp if available")


class NormalizedObjectMetadata(BaseModel):
    """Normalized object metadata representation. Strictly metadata only."""
    external_object_id: str = Field(..., description="Provider unique object key or ARN")
    storage_location: str = Field(..., description="Parent storage location / bucket name")
    object_key: str = Field(..., description="Full object path / key")
    object_size_bytes: int = Field(..., description="Object size in bytes")
    storage_class: str = Field(default="STANDARD", description="Normalized storage class (STANDARD, INFREQUENT_ACCESS, ARCHIVE)")
    last_modified_at: datetime = Field(..., description="Last modified timestamp")
    etag: Optional[str] = Field(None, description="ETag or MD5 hash header")
    version_id: Optional[str] = Field(None, description="Object version identifier if versioned")
    content_type: Optional[str] = Field(None, description="MIME content type header if present")


from app.connectors.capabilities import ProviderCapabilities
from app.connectors.credentials import CredentialResolver


class BaseStorageConnector(ABC):
    """Abstract Base Class for all external storage connectors."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return the strongly typed capabilities descriptor for this connector's provider."""
        pass

    def sanitize_error(self, err: Exception) -> str:
        """Sanitize error message to ensure no access keys, secret keys, or tokens leak in exceptions/logs."""
        return CredentialResolver.sanitize_text(str(err))

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify endpoint connectivity and credential validity."""
        pass

    @abstractmethod
    def list_storage_locations(self) -> List[NormalizedStorageLocation]:
        """List all storage locations (buckets, containers, namespaces)."""
        pass

    @abstractmethod
    def list_objects(
        self, location_name: str, cursor: Optional[str] = None
    ) -> Tuple[List[NormalizedObjectMetadata], Optional[str]]:
        """
        List metadata for objects in a given location with pagination support.
        Returns tuple of (list of normalized metadata records, next page cursor/token).
        """
        pass

    @abstractmethod
    def get_object_metadata(
        self, location_name: str, object_key: str
    ) -> NormalizedObjectMetadata:
        """Fetch head metadata for a specific object."""
        pass

    @abstractmethod
    def get_storage_class(self, location_name: str, object_key: str) -> str:
        """Get storage class for a specific object."""
        pass

    @abstractmethod
    def get_object_size(self, location_name: str, object_key: str) -> int:
        """Get object size in bytes."""
        pass

    @abstractmethod
    def get_last_modified(self, location_name: str, object_key: str) -> datetime:
        """Get last modified timestamp for an object."""
        pass

    @abstractmethod
    def copy_object_storage_class(
        self, location_name: str, object_key: str, target_storage_class: str
    ) -> bool:
        """
        Executes provider-side zero-download storage class migration.
        Returns True if successful, False otherwise.
        """
        pass
