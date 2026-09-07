"""
Unit & Integration Tests for Storage Configuration & Provider Validation.
Validates default Demo storage mode, AWS S3 mode resolution, safety gates, and secret redaction.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from app.core.config import StorageSettings, get_storage_settings, validate_aws_storage_config
from app.connectors.factory import ConnectorFactory, UnsupportedProviderError
from app.connectors.s3_connector import LocalS3Connector
from app.connectors.aws_s3_connector import AWSS3Connector
from app.connectors.credentials import CredentialResolver, ResolvedCredentials
from app.models import StorageConnection, StorageProviderEnum


def test_default_provider_is_local_s3_compatible(monkeypatch):
    """TEST 1 & 2: Verify default provider is LOCAL_S3_COMPATIBLE and demo mode starts without AWS credentials."""
    monkeypatch.delenv("STORAGE_PROVIDER", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    settings = StorageSettings.load_from_env()
    assert settings.provider == "LOCAL_S3_COMPATIBLE"
    assert settings.s3_endpoint_url == "http://localhost:9000"


def test_aws_s3_provider_resolves_aws_connector(monkeypatch):
    """TEST 3: Verify AWS_S3 provider resolves AWSS3Connector when credentials exist."""
    conn = StorageConnection(
        name="Valid AWS S3 Connection",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:AWS_KEY",
        config={
            "aws_access_key_id": "AKIA1111222233334444",
            "aws_secret_access_key": "SecretAccessKey1234567890",
            "region": "us-east-1",
        },
    )

    with patch.object(CredentialResolver, "resolve") as mock_resolve:
        mock_resolve.return_value = ResolvedCredentials(
            provider="AWS_S3",
            access_key="AKIA1111222233334444",
            secret_key="SecretAccessKey1234567890",
            region="us-east-1",
        )
        connector = ConnectorFactory.get_connector_for_connection(None, conn)
        assert isinstance(connector, AWSS3Connector)


def test_aws_s3_without_credentials_fails_safely(monkeypatch):
    """TEST 4 & 6: Verify AWS_S3 without credentials fails safely and NEVER falls back to LocalS3Connector."""
    conn = StorageConnection(
        name="Missing Credentials AWS Connection",
        provider=StorageProviderEnum.AWS_S3,
        credential_reference="env:MISSING",
        config={"region": "us-east-1"},
    )

    with patch.object(CredentialResolver, "resolve") as mock_resolve:
        mock_resolve.return_value = ResolvedCredentials(
            provider="AWS_S3",
            access_key="",
            secret_key="",
            region="us-east-1",
        )
        with pytest.raises(ValueError) as exc_info:
            ConnectorFactory.get_connector_for_connection(None, conn)

        err_text = str(exc_info.value)
        assert "AWS S3 provider selected but AWS credentials/configuration are missing" in err_text
        # Assert no silent fallback to LocalS3Connector
        assert "LocalS3Connector" not in err_text


def test_aws_config_validation_utility(monkeypatch):
    """TEST 5 & 7: Verify validate_aws_storage_config utility and zero secret credential leakage in error messages."""
    settings_incomplete = StorageSettings(
        provider="AWS_S3",
        aws_access_key_id="",
        aws_secret_access_key="SuperSecretKey999",
        aws_region="",
        aws_s3_bucket="",
    )

    is_valid, missing = validate_aws_storage_config(settings_incomplete)
    assert is_valid is False
    assert "AWS_ACCESS_KEY_ID" in missing
    assert "AWS_REGION" in missing
    assert "AWS_S3_BUCKET" in missing

    # Confirm secret credential values NEVER appear in missing key strings
    for item in missing:
        assert "SuperSecretKey999" not in item


def test_credential_sanitization_masks_secrets():
    """TEST 7: Verify secret redaction utility removes secret keys from text."""
    creds = ResolvedCredentials(
        provider="AWS_S3",
        access_key="AKIA9999888877776666",
        secret_key="MySuperSecretAWSKey123!",
        session_token="SessionTokenXYZ",
        region="ap-south-1",
    )

    raw_error = "Failed connecting with access_key=AKIA9999888877776666 and secret_key=MySuperSecretAWSKey123! token=SessionTokenXYZ"
    sanitized = CredentialResolver.sanitize_text(raw_error, creds)

    assert "AKIA9999888877776666" not in sanitized
    assert "MySuperSecretAWSKey123!" not in sanitized
    assert "SessionTokenXYZ" not in sanitized
    assert "[REDACTED]" in sanitized
