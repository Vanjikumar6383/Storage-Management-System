"""
Production AWS S3 storage connector implementation using boto3.
Fully integrates into the provider-independent connector architecture, using NormalizedObjectMetadata,
ProviderCapabilities, CredentialResolver, and StorageClassMapper.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError

from app.connectors.base import (
    BaseStorageConnector,
    NormalizedStorageLocation,
    NormalizedObjectMetadata,
)
from app.connectors.capabilities import ProviderCapabilities, get_provider_capabilities
from app.connectors.credentials import CredentialResolver, ResolvedCredentials
from app.connectors.storage_class_mapper import StorageClassMapper

logger = logging.getLogger("storage.connector.aws_s3")


class AWSS3Connector(BaseStorageConnector):
    """Production AWS S3 Connector implementing provider-independent BaseStorageConnector."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        session_token: Optional[str] = None,
        region: Optional[str] = None,
        credentials: Optional[ResolvedCredentials] = None,
    ):
        if credentials:
            self.endpoint_url = credentials.endpoint_url
            self.access_key = credentials.access_key
            self.secret_key = credentials.secret_key
            self.session_token = credentials.session_token
            self.region = credentials.region or "us-east-1"
        else:
            self.endpoint_url = endpoint_url
            self.access_key = access_key
            self.secret_key = secret_key
            self.session_token = session_token
            self.region = region or "us-east-1"

        self._credentials = ResolvedCredentials(
            provider="AWS_S3",
            endpoint_url=self.endpoint_url,
            access_key=self.access_key,
            secret_key=self.secret_key,
            session_token=self.session_token,
            region=self.region,
        )

        client_kwargs = {
            "service_name": "s3",
            "region_name": self.region,
            "config": Config(
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=5,
            ),
        }

        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key:
            client_kwargs["aws_access_key_id"] = self.access_key
        if self.secret_key:
            client_kwargs["aws_secret_access_key"] = self.secret_key
        if self.session_token:
            client_kwargs["aws_session_token"] = self.session_token

        self.client = boto3.client(**client_kwargs)

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Returns capabilities descriptor for AWS_S3."""
        return get_provider_capabilities("AWS_S3")

    def sanitize_error(self, err: Exception) -> str:
        """Sanitize error messages using centralized CredentialResolver."""
        return CredentialResolver.sanitize_text(str(err), self._credentials)

    def _normalize_storage_class(self, raw_class: Optional[str]) -> str:
        """Delegates to StorageClassMapper for AWS S3."""
        return StorageClassMapper.to_normalized_class("AWS_S3", raw_class)

    def test_connection(self) -> bool:
        """Test connectivity using inexpensive AWS S3 list_buckets call."""
        try:
            self.client.list_buckets()
            logger.info(f"AWS S3 connection test successful for region '{self.region}'.")
            return True
        except (ClientError, BotoCoreError, NoCredentialsError, Exception) as e:
            logger.error(f"AWS S3 connection test failed: {self.sanitize_error(e)}")
            return False

    def list_storage_locations(self) -> List[NormalizedStorageLocation]:
        """Discover S3 buckets for this AWS connection."""
        try:
            response = self.client.list_buckets()
            locations = []
            for bucket in response.get("Buckets", []):
                created_at = bucket.get("CreationDate")
                if created_at and created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                locations.append(
                    NormalizedStorageLocation(
                        name=bucket["Name"],
                        region=self.region,
                        created_at=created_at,
                    )
                )
            logger.info(f"Discovered {len(locations)} AWS S3 storage locations.")
            return locations
        except Exception as e:
            sanitized = self.sanitize_error(e)
            logger.error(f"Failed to list AWS S3 buckets: {sanitized}")
            raise RuntimeError(f"AWS storage location discovery failed: {sanitized}")

    def list_objects(
        self, location_name: str, cursor: Optional[str] = None
    ) -> Tuple[List[NormalizedObjectMetadata], Optional[str]]:
        """List metadata for objects in an S3 bucket using ListObjectsV2 pagination."""
        kwargs = {"Bucket": location_name, "MaxKeys": 1000}
        if cursor:
            kwargs["ContinuationToken"] = cursor

        try:
            response = self.client.list_objects_v2(**kwargs)
            contents = response.get("Contents", [])
            next_token = response.get("NextContinuationToken")

            metadata_list = []
            for item in contents:
                key = item["Key"]
                size = item["Size"]
                raw_storage_class = item.get("StorageClass", "STANDARD")
                last_modified = item.get("LastModified")
                if last_modified and last_modified.tzinfo is None:
                    last_modified = last_modified.replace(tzinfo=timezone.utc)

                etag = item.get("ETag", "").strip('"')

                norm_meta = NormalizedObjectMetadata(
                    external_object_id=f"arn:aws:s3:::{location_name}/{key}",
                    storage_location=location_name,
                    object_key=key,
                    object_size_bytes=size,
                    storage_class=self._normalize_storage_class(raw_storage_class),
                    last_modified_at=last_modified or datetime.now(timezone.utc),
                    etag=etag,
                )
                metadata_list.append(norm_meta)

            logger.info(f"Discovered {len(metadata_list)} objects in AWS location '{location_name}'.")
            return metadata_list, next_token
        except Exception as e:
            sanitized = self.sanitize_error(e)
            logger.error(f"Failed to list objects in AWS location '{location_name}': {sanitized}")
            raise RuntimeError(f"AWS object listing failed for '{location_name}': {sanitized}")

    def get_object_metadata(
        self, location_name: str, object_key: str
    ) -> NormalizedObjectMetadata:
        """Fetch head metadata for a specific AWS S3 object using head_object (never get_object)."""
        try:
            head = self.client.head_object(Bucket=location_name, Key=object_key)
            size = head.get("ContentLength", 0)
            raw_storage_class = head.get("StorageClass", "STANDARD")
            last_modified = head.get("LastModified")
            if last_modified and last_modified.tzinfo is None:
                last_modified = last_modified.replace(tzinfo=timezone.utc)

            etag = head.get("ETag", "").strip('"')
            version_id = head.get("VersionId")
            content_type = head.get("ContentType")

            return NormalizedObjectMetadata(
                external_object_id=f"arn:aws:s3:::{location_name}/{object_key}",
                storage_location=location_name,
                object_key=object_key,
                object_size_bytes=size,
                storage_class=self._normalize_storage_class(raw_storage_class),
                last_modified_at=last_modified or datetime.now(timezone.utc),
                etag=etag,
                version_id=version_id,
                content_type=content_type,
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                raise ValueError(f"Object '{object_key}' not found in AWS location '{location_name}'.")
            sanitized = self.sanitize_error(e)
            raise RuntimeError(f"Failed to fetch metadata for AWS object '{object_key}': {sanitized}")

    def copy_object_storage_class(
        self, location_name: str, object_key: str, target_storage_class: str
    ) -> bool:
        """
        Executes provider-side zero-download storage class migration via S3 CopyObject using StorageClassMapper.
        """
        aws_target_class = StorageClassMapper.from_normalized_class("AWS_S3", target_storage_class)
        try:
            self.client.copy_object(
                Bucket=location_name,
                Key=object_key,
                CopySource={"Bucket": location_name, "Key": object_key},
                StorageClass=aws_target_class,
                MetadataDirective="REPLACE",
            )
            logger.info(f"Successfully migrated AWS S3 object '{object_key}' in '{location_name}' to class '{aws_target_class}'.")
            return True
        except (ClientError, BotoCoreError, Exception) as e:
            sanitized = self.sanitize_error(e)
            logger.warning(f"AWS S3 copy_object tier migration failed: {sanitized}")
            return False

    def get_storage_class(self, location_name: str, object_key: str) -> str:
        meta = self.get_object_metadata(location_name, object_key)
        return meta.storage_class

    def get_object_size(self, location_name: str, object_key: str) -> int:
        meta = self.get_object_metadata(location_name, object_key)
        return meta.object_size_bytes

    def get_last_modified(self, location_name: str, object_key: str) -> datetime:
        meta = self.get_object_metadata(location_name, object_key)
        return meta.last_modified_at
