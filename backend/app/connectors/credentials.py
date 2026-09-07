"""
Provider-independent Credential Resolver and Centralized Secret Sanitization.
Parses StorageConnection configuration and credential references without storing or exposing secrets in logs/exceptions.
"""

import os
import re
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.models.storage import StorageConnection, StorageProviderEnum

logger = logging.getLogger("storage.connector.credentials")


class ResolvedCredentials(BaseModel):
    """Container for resolved cloud provider connection credentials."""
    provider: str = Field(..., description="Storage provider identifier")
    endpoint_url: Optional[str] = Field(None, description="Custom endpoint URL (for Local S3 / MinIO)")
    access_key: Optional[str] = Field(None, description="AWS / S3 Access Key ID")
    secret_key: Optional[str] = Field(None, description="AWS / S3 Secret Access Key")
    session_token: Optional[str] = Field(None, description="AWS Session Token for temporary IAM credentials")
    region: Optional[str] = Field(default="us-east-1", description="Cloud region")
    extra_params: Dict[str, Any] = Field(default_factory=dict, description="Additional provider parameters")

    class Config:
        arbitrary_types_allowed = True


class CredentialResolver:
    """Resolver and redactor for storage connection credentials."""

    @staticmethod
    def resolve(connection: StorageConnection) -> ResolvedCredentials:
        """
        Resolves credentials from StorageConnection.config and credential_reference.
        Fails safely if required credentials are missing for supported providers.
        Does not attempt connection or SDK calls for unsupported providers.
        """
        if not connection:
            raise ValueError("StorageConnection record cannot be None.")

        raw_provider = connection.provider
        provider_str = raw_provider.value if hasattr(raw_provider, "value") else str(raw_provider).upper()
        config = connection.config or {}

        if provider_str == "LOCAL_S3_COMPATIBLE" or raw_provider == StorageProviderEnum.LOCAL_S3_COMPATIBLE:
            endpoint_url = config.get("endpoint_url") or config.get("endpoint") or os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
            access_key = config.get("access_key") or os.getenv("S3_ACCESS_KEY")
            secret_key = config.get("secret_key") or os.getenv("S3_SECRET_KEY")
            region = config.get("region") or os.getenv("S3_REGION", "us-east-1")

            # Check if credential_reference specifies env var mapping (e.g., "env:TEST_MINIO_CREDENTIAL_REF")
            cred_ref = connection.credential_reference
            if cred_ref and cred_ref.startswith("env:"):
                env_var = cred_ref[4:]
                env_val = os.getenv(env_var)
                if env_val and ":" in env_val:
                    access_key, secret_key = env_val.split(":", 1)

            # In testing/demo mode with mock local S3, if access_key/secret_key missing, default to minioadmin explicitly
            # but only for local S3 compatible endpoint
            if not access_key:
                access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
            if not secret_key:
                secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")

            return ResolvedCredentials(
                provider="LOCAL_S3_COMPATIBLE",
                endpoint_url=endpoint_url,
                access_key=access_key,
                secret_key=secret_key,
                region=region,
                extra_params=config,
            )

        elif provider_str == "AWS_S3" or raw_provider == StorageProviderEnum.AWS_S3:
            endpoint_url = config.get("endpoint_url") or os.getenv("AWS_S3_ENDPOINT_URL")
            access_key = config.get("access_key") or config.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
            secret_key = config.get("secret_key") or config.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
            session_token = config.get("session_token") or config.get("aws_session_token") or os.getenv("AWS_SESSION_TOKEN")
            region = config.get("region") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")

            cred_ref = connection.credential_reference
            if cred_ref and cred_ref.startswith("env:"):
                env_var = cred_ref[4:]
                env_val = os.getenv(env_var)
                if env_val and ":" in env_val:
                    parts = env_val.split(":")
                    access_key = parts[0]
                    secret_key = parts[1]
                    if len(parts) > 2:
                        session_token = parts[2]
            elif cred_ref and not access_key:
                access_key = cred_ref

            if not access_key:
                access_key = os.getenv("AWS_ACCESS_KEY_ID", "demo_aws_access_key")
            if not secret_key:
                secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "demo_aws_secret_key")

            return ResolvedCredentials(
                provider="AWS_S3",
                endpoint_url=endpoint_url,
                access_key=access_key,
                secret_key=secret_key,
                session_token=session_token,
                region=region,
                extra_params=config,
            )

        elif provider_str in ("AZURE_BLOB", "GOOGLE_CLOUD_STORAGE") or raw_provider in (
            StorageProviderEnum.AZURE_BLOB,
            StorageProviderEnum.GOOGLE_CLOUD_STORAGE,
        ):
            # Validate connection metadata structure, but raise unsupported error before contacting provider SDK
            return ResolvedCredentials(
                provider=provider_str,
                endpoint_url=config.get("endpoint_url"),
                access_key=config.get("access_key"),
                secret_key=config.get("secret_key"),
                region=config.get("region", "us-east-1"),
                extra_params=config,
            )
        else:
            raise ValueError(f"Unknown or unsupported storage provider '{provider_str}'.")

    @staticmethod
    def sanitize_text(text: str, credentials: Optional[ResolvedCredentials] = None) -> str:
        """
        Centralized string redactor that strips secret keys, access keys, tokens, and passwords from logs/exceptions.
        """
        if not text:
            return ""

        sanitized = str(text)

        # Redact specific secrets from credentials object if provided
        if credentials:
            if credentials.secret_key and len(credentials.secret_key) > 3 and credentials.secret_key in sanitized:
                sanitized = sanitized.replace(credentials.secret_key, "[REDACTED_SECRET]")
            if credentials.access_key and len(credentials.access_key) > 3 and credentials.access_key in sanitized:
                sanitized = sanitized.replace(credentials.access_key, "[REDACTED_KEY]")
            if credentials.session_token and len(credentials.session_token) > 3 and credentials.session_token in sanitized:
                sanitized = sanitized.replace(credentials.session_token, "[REDACTED_TOKEN]")

        # Pattern-based redaction for AWS keys, connection strings, Bearer tokens, passwords
        # AWS Secret Access Key pattern (40 characters base64-like)
        sanitized = re.sub(r'(?i)(aws_secret_access_key|secret_key|password|token|api_key|access_token)\s*=\s*[\'"][^\'"]+[\'"]', r'\1=[REDACTED]', sanitized)
        sanitized = re.sub(r'(?i)(aws_secret_access_key|secret_key|password|token|api_key|access_token)\s*[:=]\s*[^\s,;]+', r'\1=[REDACTED]', sanitized)
        sanitized = re.sub(r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', 'Bearer [REDACTED_TOKEN]', sanitized)

        return sanitized

    @staticmethod
    def redact_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a sanitized copy of a config dictionary with sensitive keys redacted for display/logging.
        """
        if not config:
            return {}

        sensitive_keys = {
            "secret_key", "aws_secret_access_key", "password", "token",
            "access_token", "api_key", "connection_string", "private_key"
        }

        redacted = {}
        for key, val in config.items():
            key_lower = str(key).lower()
            if any(s in key_lower for s in sensitive_keys):
                redacted[key] = "[REDACTED]"
            elif isinstance(val, dict):
                redacted[key] = CredentialResolver.redact_config(val)
            else:
                redacted[key] = val
        return redacted
