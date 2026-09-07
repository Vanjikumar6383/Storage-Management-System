"""
Provider-independent Storage Class Mapping Abstraction.
Translates provider-native storage tiers to normalized domain storage classes (STANDARD, INFREQUENT_ACCESS, ARCHIVE)
and vice versa. Explicitly documents lossy mappings.
"""

from typing import Dict, Optional, Union
from app.models.storage import StorageProviderEnum

NORMALIZED_STANDARD = "STANDARD"
NORMALIZED_INFREQUENT = "INFREQUENT_ACCESS"
NORMALIZED_ARCHIVE = "ARCHIVE"

VALID_NORMALIZED_CLASSES = {NORMALIZED_STANDARD, NORMALIZED_INFREQUENT, NORMALIZED_ARCHIVE}

# Provider Native -> Normalized Mappings
NATIVE_TO_NORMALIZED_MAPPINGS: Dict[str, Dict[str, str]] = {
    "LOCAL_S3_COMPATIBLE": {
        "STANDARD": NORMALIZED_STANDARD,
        "STANDARD_IA": NORMALIZED_INFREQUENT,
        "INFREQUENT_ACCESS": NORMALIZED_INFREQUENT,
        "GLACIER": NORMALIZED_ARCHIVE,
        "DEEP_ARCHIVE": NORMALIZED_ARCHIVE,
        "ARCHIVE": NORMALIZED_ARCHIVE,
    },
    "AWS_S3": {
        "STANDARD": NORMALIZED_STANDARD,
        "STANDARD_IA": NORMALIZED_INFREQUENT,
        "ONEZONE_IA": NORMALIZED_INFREQUENT,
        "INFREQUENT_ACCESS": NORMALIZED_INFREQUENT,
        "GLACIER_IR": NORMALIZED_ARCHIVE,
        "GLACIER": NORMALIZED_ARCHIVE,
        "DEEP_ARCHIVE": NORMALIZED_ARCHIVE,
        "ARCHIVE": NORMALIZED_ARCHIVE,
        # Note: INTELLIGENT_TIERING is lossy when normalized to STANDARD
        "INTELLIGENT_TIERING": NORMALIZED_STANDARD,
    },
    "AZURE_BLOB": {
        "HOT": NORMALIZED_STANDARD,
        "COOL": NORMALIZED_INFREQUENT,
        "COLD": NORMALIZED_INFREQUENT,
        "ARCHIVE": NORMALIZED_ARCHIVE,
    },
    "GOOGLE_CLOUD_STORAGE": {
        "STANDARD": NORMALIZED_STANDARD,
        "NEARLINE": NORMALIZED_INFREQUENT,
        "COLDLINE": NORMALIZED_INFREQUENT,
        "ARCHIVE": NORMALIZED_ARCHIVE,
    },
}

# Normalized -> Provider Native Mappings
NORMALIZED_TO_NATIVE_MAPPINGS: Dict[str, Dict[str, str]] = {
    "LOCAL_S3_COMPATIBLE": {
        NORMALIZED_STANDARD: "STANDARD",
        NORMALIZED_INFREQUENT: "STANDARD_IA",
        NORMALIZED_ARCHIVE: "GLACIER",
    },
    "AWS_S3": {
        NORMALIZED_STANDARD: "STANDARD",
        NORMALIZED_INFREQUENT: "STANDARD_IA",
        NORMALIZED_ARCHIVE: "GLACIER",
    },
    "AZURE_BLOB": {
        NORMALIZED_STANDARD: "Hot",
        NORMALIZED_INFREQUENT: "Cool",
        NORMALIZED_ARCHIVE: "Archive",
    },
    "GOOGLE_CLOUD_STORAGE": {
        NORMALIZED_STANDARD: "STANDARD",
        NORMALIZED_INFREQUENT: "NEARLINE",
        NORMALIZED_ARCHIVE: "ARCHIVE",
    },
}

# Explicit documentation notes on lossy or approximate mappings
LOSSY_MAPPING_NOTES: Dict[str, Dict[str, str]] = {
    "AWS_S3": {
        "INTELLIGENT_TIERING": "INTELLIGENT_TIERING auto-tiers objects internally; mapped to STANDARD for metadata baseline cost comparison.",
        "ONEZONE_IA": "ONEZONE_IA lacks multi-AZ durability; mapped to INFREQUENT_ACCESS.",
    },
    "AZURE_BLOB": {
        "COLD": "Azure Cold tier has 90-day minimum retention vs Cool 30-day; both map to normalized INFREQUENT_ACCESS.",
    },
    "GOOGLE_CLOUD_STORAGE": {
        "COLDLINE": "GCS COLDLINE has 90-day minimum retention vs NEARLINE 30-day; both map to normalized INFREQUENT_ACCESS.",
    },
}


class StorageClassMapper:
    """Abstraction for bidirectional storage class translation across cloud providers."""

    @staticmethod
    def to_normalized_class(provider: Union[StorageProviderEnum, str], native_class: Optional[str]) -> str:
        """
        Translates a provider-native storage class to a normalized class (STANDARD, INFREQUENT_ACCESS, ARCHIVE).
        Defaults to STANDARD if native_class is missing or blank.
        Raises ValueError if native_class is unknown.
        """
        if not native_class or str(native_class).strip() == "":
            return NORMALIZED_STANDARD

        provider_str = provider.value if hasattr(provider, "value") else str(provider).upper()
        if provider_str not in NATIVE_TO_NORMALIZED_MAPPINGS:
            raise ValueError(f"Unknown storage provider '{provider_str}'.")

        native_clean = str(native_class).strip().upper()
        # Direct match check if native_clean already matches a valid normalized class
        mapping = NATIVE_TO_NORMALIZED_MAPPINGS[provider_str]
        if native_clean in mapping:
            return mapping[native_clean]

        # Case-insensitive lookup fallback
        for key, val in mapping.items():
            if key.upper() == native_clean:
                return val

        if native_clean in VALID_NORMALIZED_CLASSES:
            return native_clean

        raise ValueError(f"Unknown native storage class '{native_class}' for provider '{provider_str}'.")

    @staticmethod
    def from_normalized_class(provider: Union[StorageProviderEnum, str], normalized_class: str) -> str:
        """
        Translates a normalized class (STANDARD, INFREQUENT_ACCESS, ARCHIVE) back to a provider-native storage class.
        Raises ValueError if normalized_class is invalid or provider is unknown.
        """
        if not normalized_class or str(normalized_class).strip().upper() not in VALID_NORMALIZED_CLASSES:
            raise ValueError(f"Invalid normalized storage class '{normalized_class}'. Must be one of {VALID_NORMALIZED_CLASSES}.")

        provider_str = provider.value if hasattr(provider, "value") else str(provider).upper()
        if provider_str not in NORMALIZED_TO_NATIVE_MAPPINGS:
            raise ValueError(f"Unknown storage provider '{provider_str}'.")

        norm_clean = str(normalized_class).strip().upper()
        return NORMALIZED_TO_NATIVE_MAPPINGS[provider_str][norm_clean]

    @staticmethod
    def get_native_mapping_info(provider: Union[StorageProviderEnum, str]) -> Dict[str, str]:
        """Returns the native-to-normalized mapping dict for a provider."""
        provider_str = provider.value if hasattr(provider, "value") else str(provider).upper()
        if provider_str not in NATIVE_TO_NORMALIZED_MAPPINGS:
            raise ValueError(f"Unknown storage provider '{provider_str}'.")
        return NATIVE_TO_NORMALIZED_MAPPINGS[provider_str].copy()

    @staticmethod
    def is_lossy_mapping(provider: Union[StorageProviderEnum, str], native_class: str) -> Tuple[bool, Optional[str]]:
        """Checks if mapping native_class to normalized class involves loss of precision."""
        provider_str = provider.value if hasattr(provider, "value") else str(provider).upper()
        native_clean = str(native_class).strip().upper()
        notes = LOSSY_MAPPING_NOTES.get(provider_str, {})
        if native_clean in notes:
            return True, notes[native_clean]
        return False, None
