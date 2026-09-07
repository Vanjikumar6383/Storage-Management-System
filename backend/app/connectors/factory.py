"""
Provider-aware Storage Connector Factory.
Instantiates the appropriate BaseStorageConnector implementation based on StorageConnection provider configuration.
"""

import logging
from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.connectors.base import BaseStorageConnector
from app.connectors.s3_connector import LocalS3Connector
from app.models import StorageConnection, StorageProviderEnum, StorageLocation, StorageObject

logger = logging.getLogger("storage.connector.factory")


from app.connectors.credentials import CredentialResolver


from app.connectors.aws_s3_connector import AWSS3Connector


class UnsupportedProviderError(Exception):
    """Raised when a storage provider adapter is requested that is not supported or implemented."""
    pass


class ConnectorFactory:
    """Factory for resolving and instantiating provider-specific storage connectors."""

    @staticmethod
    def get_connector_for_connection(
        db: Session,
        storage_connection: StorageConnection,
    ) -> BaseStorageConnector:
        """
        Inspects storage_connection.provider and instantiates the correct BaseStorageConnector.
        Never falls back silently to LocalS3Connector for unsupported providers.
        """
        if not storage_connection:
            raise ValueError("StorageConnection record cannot be None.")

        raw_provider = storage_connection.provider
        provider_str = raw_provider.value if hasattr(raw_provider, "value") else str(raw_provider).upper()

        conn_id_str = getattr(storage_connection, 'id', 'n/a')
        conn_name = getattr(storage_connection, 'name', 'unnamed')

        if provider_str == "LOCAL_S3_COMPATIBLE" or raw_provider == StorageProviderEnum.LOCAL_S3_COMPATIBLE:
            creds = CredentialResolver.resolve(storage_connection)
            logger.info(f"Instantiating LocalS3Connector for connection '{conn_name}' (ID: {conn_id_str}).")
            return LocalS3Connector(credentials=creds)

        elif provider_str == "AWS_S3" or raw_provider == StorageProviderEnum.AWS_S3:
            creds = CredentialResolver.resolve(storage_connection)
            if not creds.access_key or not creds.secret_key:
                err_msg = (
                    "AWS S3 provider selected but AWS credentials/configuration are missing. "
                    "Please configure: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_S3_BUCKET."
                )
                logger.error(f"Failed to instantiate AWSS3Connector for connection '{conn_name}': {err_msg}")
                raise ValueError(err_msg)
            logger.info(f"Instantiating AWSS3Connector for connection '{conn_name}' (ID: {conn_id_str}).")
            return AWSS3Connector(credentials=creds)

        elif provider_str in ("AZURE_BLOB", "GOOGLE_CLOUD_STORAGE") or raw_provider in (
            StorageProviderEnum.AZURE_BLOB,
            StorageProviderEnum.GOOGLE_CLOUD_STORAGE,
        ):
            logger.warning(
                f"Attempted to instantiate connector for unsupported provider '{provider_str}' "
                f"on connection '{conn_name}' (ID: {conn_id_str})."
            )
            raise UnsupportedProviderError(
                f"Storage provider '{provider_str}' adapter is not yet implemented. "
                f"Supported providers currently: LOCAL_S3_COMPATIBLE, AWS_S3."
            )

        else:
            logger.error(f"Unknown storage provider '{provider_str}' on connection '{conn_id_str}'.")
            raise UnsupportedProviderError(
                f"Unknown or unsupported storage provider '{provider_str}'."
            )

    @staticmethod
    def get_connector_for_object(
        db: Session,
        object_id: UUID,
    ) -> Tuple[BaseStorageConnector, StorageLocation, StorageObject]:
        """
        Resolves object -> StorageLocation -> StorageConnection -> BaseStorageConnector.
        Returns tuple of (connector, storage_location, storage_object).
        """
        obj = db.query(StorageObject).filter_by(id=object_id).first()
        if not obj:
            raise ValueError(f"StorageObject '{object_id}' not found.")

        loc = db.query(StorageLocation).filter_by(id=obj.storage_location_id).first()
        if not loc:
            raise ValueError(f"StorageLocation for object '{object_id}' not found.")

        conn = db.query(StorageConnection).filter_by(id=loc.storage_connection_id).first()
        if not conn:
            raise ValueError(f"StorageConnection for location '{loc.id}' not found.")

        connector = ConnectorFactory.get_connector_for_connection(db, conn)
        return connector, loc, obj
