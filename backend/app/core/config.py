"""
Centralized Storage Configuration & Validation Module.
Provides default Demo Storage (LOCAL_S3_COMPATIBLE) mode, environment concept, and optional AWS S3 configuration resolution.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List
from pydantic import BaseModel, Field

from app.connectors.credentials import CredentialResolver

logger = logging.getLogger("storage.core.config")


class AppConfig(BaseModel):
    """Centralized production application settings."""
    app_name: str = Field(default="Storage Lifecycle Optimizer")
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "DEMO").upper())
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/storage_optimizer_dev"))
    cors_allowed_origins: List[str] = Field(default_factory=lambda: [
        origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173").split(",") if origin.strip()
    ])


class StorageSettings(BaseModel):
    """Storage system configuration settings resolved from environment variables."""
    provider: str = Field(default="LOCAL_S3_COMPATIBLE", description="Storage provider identifier (LOCAL_S3_COMPATIBLE or AWS_S3)")

    # Demo / Local S3 Configuration
    s3_endpoint_url: str = Field(default_factory=lambda: os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"))
    s3_region: str = Field(default_factory=lambda: os.getenv("S3_REGION", "us-east-1"))
    s3_access_key: Optional[str] = Field(default_factory=lambda: os.getenv("S3_ACCESS_KEY", "minioadmin"))
    s3_secret_key: Optional[str] = Field(default_factory=lambda: os.getenv("S3_SECRET_KEY", "minioadmin"))

    # Optional Real AWS S3 Configuration
    aws_access_key_id: Optional[str] = Field(default_factory=lambda: os.getenv("AWS_ACCESS_KEY_ID"))
    aws_secret_access_key: Optional[str] = Field(default_factory=lambda: os.getenv("AWS_SECRET_ACCESS_KEY"))
    aws_session_token: Optional[str] = Field(default_factory=lambda: os.getenv("AWS_SESSION_TOKEN"))
    aws_region: str = Field(default_factory=lambda: os.getenv("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "ap-south-1")))
    aws_s3_bucket: Optional[str] = Field(default_factory=lambda: os.getenv("AWS_S3_BUCKET"))

    @classmethod
    def load_from_env(cls) -> "StorageSettings":
        """Factory method loading configuration from environment variables."""
        provider_val = os.getenv("STORAGE_PROVIDER", "LOCAL_S3_COMPATIBLE").upper()
        return cls(provider=provider_val)


def get_app_config() -> AppConfig:
    """Returns application configuration settings."""
    return AppConfig()


def get_storage_settings() -> StorageSettings:
    """Returns singleton/resolved storage settings."""
    return StorageSettings.load_from_env()


def validate_aws_storage_config(settings: Optional[StorageSettings] = None) -> Tuple[bool, List[str]]:
    """
    Validates AWS S3 configuration parameters when AWS_S3 is selected.
    Returns (is_valid, list_of_missing_keys). Secret credentials are NEVER printed.
    """
    opts = settings or get_storage_settings()
    missing = []

    if not opts.aws_access_key_id:
        missing.append("AWS_ACCESS_KEY_ID")
    if not opts.aws_secret_access_key:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if not opts.aws_region:
        missing.append("AWS_REGION")
    if not opts.aws_s3_bucket:
        missing.append("AWS_S3_BUCKET")

    return (len(missing) == 0, missing)
