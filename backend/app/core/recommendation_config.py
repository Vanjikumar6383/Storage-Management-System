"""
Centralized Storage Lifecycle Recommendation Configuration.
Baseline rules, age thresholds, size limits, and pricing assumptions.
"""

from typing import Dict
from pydantic import BaseModel, Field


class StoragePricingAssumption(BaseModel):
    """Monthly storage pricing per GB-month in USD."""
    standard_cost_per_gb_month: float = 0.023
    infrequent_access_cost_per_gb_month: float = 0.0125
    archive_cost_per_gb_month: float = 0.004
    deep_archive_cost_per_gb_month: float = 0.00099
    retrieval_cost_per_gb: float = 0.03


class LifecycleRuleThresholds(BaseModel):
    """Configurable lifecycle rule thresholds."""
    rule_version: str = "baseline-v1"
    pricing_assumption_version: str = "2026-v1"

    # Age thresholds (days)
    archive_age_days: int = 180
    infrequent_access_age_days: int = 90
    delete_candidate_age_days: int = 365

    # Access frequency thresholds
    minimum_accesses_for_keep: int = 5
    recent_access_window_days: int = 30
    cold_access_window_days: int = 180

    # Size & savings thresholds
    minimum_object_size_for_migration_bytes: int = 128 * 1024  # 128 KB
    minimum_monthly_savings_usd: float = 0.01

    # Pricing assumptions
    pricing: StoragePricingAssumption = Field(default_factory=StoragePricingAssumption)


RECOMMENDATION_THRESHOLDS = LifecycleRuleThresholds()
