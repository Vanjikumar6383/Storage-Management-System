"""
Centralized Configuration for Telemetry, Access Thresholds, and Restore Risk Metrics.
"""

import enum
from typing import Set
from pydantic import BaseModel


class AccessEventTypeEnum(str, enum.Enum):
    OBJECT_READ = "OBJECT_READ"
    OBJECT_RESTORED = "OBJECT_RESTORED"
    OBJECT_METADATA_READ = "OBJECT_METADATA_READ"
    OBJECT_CREATED = "OBJECT_CREATED"
    OBJECT_DELETED = "OBJECT_DELETED"
    OBJECT_MIGRATED = "OBJECT_MIGRATED"


class AccessFrequencyEnum(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"
    NONE = "NONE"


class RestoreRiskEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RestoreStatusEnum(str, enum.Enum):
    REQUESTED = "REQUESTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Controlled set of events that represent meaningful payload access/retrieval
MEANINGFUL_ACCESS_EVENTS: Set[str] = {
    AccessEventTypeEnum.OBJECT_READ.value,
    AccessEventTypeEnum.OBJECT_RESTORED.value,
}


class TelemetryThresholds(BaseModel):
    """Centralized thresholds for usage profiling and risk classification."""

    # Access frequency thresholds (based on 30-day and 180-day window access counts)
    high_access_30d: int = 20
    medium_access_30d: int = 5
    low_access_30d: int = 1
    very_low_access_180d: int = 1

    # Restore risk thresholds
    high_restore_count_90d: int = 3
    high_restore_failure_rate: float = 0.40  # 40% failure rate triggers HIGH risk
    medium_restore_count_90d: int = 1

    # Telemetry data retention (in days)
    raw_event_retention_days: int = 180
    aggregated_profile_retention_days: int = 730


# Global threshold instance
TELEMETRY_THRESHOLDS = TelemetryThresholds()
