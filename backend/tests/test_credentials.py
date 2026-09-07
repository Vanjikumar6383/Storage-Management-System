"""
Unit tests for CredentialResolver and Centralized Secret Sanitization.
"""

import pytest
from uuid import uuid4
from app.models.storage import StorageConnection, StorageProviderEnum
from app.connectors.credentials import CredentialResolver, ResolvedCredentials


def test_credential_resolver_local_s3():
    """Verify CredentialResolver extracts credentials from LOCAL_S3_COMPATIBLE connection."""
    class DummyConnection:
        provider = StorageProviderEnum.LOCAL_S3_COMPATIBLE
        config = {
            "endpoint_url": "http://localhost:9000",
            "access_key": "myaccesskey",
            "secret_key": "mysecretkey",
            "region": "us-west-2",
        }
        credential_reference = "env:NONE"

    creds = CredentialResolver.resolve(DummyConnection()) # type: ignore
    assert isinstance(creds, ResolvedCredentials)
    assert creds.provider == "LOCAL_S3_COMPATIBLE"
    assert creds.endpoint_url == "http://localhost:9000"
    assert creds.access_key == "myaccesskey"
    assert creds.secret_key == "mysecretkey"
    assert creds.region == "us-west-2"


def test_secret_sanitization_text():
    """Verify secrets and keys are redacted from text strings."""
    creds = ResolvedCredentials(
        provider="LOCAL_S3_COMPATIBLE",
        endpoint_url="http://localhost:9000",
        access_key="AKIAEXAMPLEKEY123",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
    )

    err_text = f"Connection failed to endpoint with key AKIAEXAMPLEKEY123 and secret wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY."
    sanitized = CredentialResolver.sanitize_text(err_text, creds)

    assert "AKIAEXAMPLEKEY123" not in sanitized
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in sanitized
    assert "[REDACTED_KEY]" in sanitized
    assert "[REDACTED_SECRET]" in sanitized


def test_secret_sanitization_pattern_redaction():
    """Verify pattern-based secret masking for generic keys, tokens, and authorization headers."""
    text = "Error detail: aws_secret_access_key='SUPER_SECRET_VALUE' and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    sanitized = CredentialResolver.sanitize_text(text)

    assert "SUPER_SECRET_VALUE" not in sanitized
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "Bearer [REDACTED_TOKEN]" in sanitized


def test_config_redaction():
    """Verify dictionary config redaction for logging/display."""
    raw_config = {
        "endpoint_url": "http://localhost:9000",
        "access_key": "my_access_key",
        "secret_key": "my_secret_key",
        "nested": {
            "password": "my_password",
            "safe_field": "public_val",
        },
    }
    redacted = CredentialResolver.redact_config(raw_config)

    assert redacted["endpoint_url"] == "http://localhost:9000"
    assert redacted["access_key"] == "my_access_key"
    assert redacted["secret_key"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["nested"]["safe_field"] == "public_val"


def test_none_connection_fails_safely():
    """Verify passing None to CredentialResolver.resolve raises ValueError safely."""
    with pytest.raises(ValueError) as exc_info:
        CredentialResolver.resolve(None) # type: ignore
    assert "cannot be None" in str(exc_info.value)
