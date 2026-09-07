"""
Explainable Storage Cost Estimation Service.
Calculates storage class costs, monthly savings, and retrieval risk estimates.
"""

from typing import Dict, Tuple
from pydantic import BaseModel, Field

from app.core.recommendation_config import RECOMMENDATION_THRESHOLDS, LifecycleRuleThresholds


class StorageCostEstimate(BaseModel):
    object_size_bytes: int
    current_storage_class: str
    recommended_storage_class: str
    current_monthly_cost_usd: float
    recommended_monthly_cost_usd: float
    estimated_monthly_savings_usd: float
    estimated_retrieval_risk_usd: float
    pricing_assumption_version: str


class CostEstimationService:
    """Calculates storage pricing and cost savings estimations."""

    @staticmethod
    def get_unit_cost_per_gb_month(storage_class: str, thresholds: LifecycleRuleThresholds = RECOMMENDATION_THRESHOLDS) -> float:
        sc_upper = storage_class.upper()
        p = thresholds.pricing
        if sc_upper in ("STANDARD", "HOT"):
            return p.standard_cost_per_gb_month
        elif sc_upper in ("INFREQUENT_ACCESS", "STANDARD_IA", "COOL"):
            return p.infrequent_access_cost_per_gb_month
        elif sc_upper in ("ARCHIVE", "GLACIER", "COLD"):
            return p.archive_cost_per_gb_month
        elif sc_upper in ("DEEP_ARCHIVE", "GLACIER_DEEP_ARCHIVE"):
            return p.deep_archive_cost_per_gb_month
        return p.standard_cost_per_gb_month

    def calculate_savings(
        self,
        object_size_bytes: int,
        current_storage_class: str,
        recommended_storage_class: str,
        restores_90d: int = 0,
        thresholds: LifecycleRuleThresholds = RECOMMENDATION_THRESHOLDS,
    ) -> StorageCostEstimate:
        size_bytes_clean = max(0, object_size_bytes)
        size_gb = size_bytes_clean / (1024.0 * 1024.0 * 1024.0)

        current_rate = self.get_unit_cost_per_gb_month(current_storage_class, thresholds)
        recommended_rate = self.get_unit_cost_per_gb_month(recommended_storage_class, thresholds)

        current_cost = round(size_gb * current_rate, 4)
        recommended_cost = round(size_gb * recommended_rate, 4)
        raw_savings = round(current_cost - recommended_cost, 4)
        monthly_savings = max(0.0, raw_savings)

        retrieval_risk = 0.0
        if recommended_storage_class.upper() in ("ARCHIVE", "GLACIER", "DEEP_ARCHIVE"):
            retrieval_risk = round(size_gb * thresholds.pricing.retrieval_cost_per_gb * max(1, restores_90d), 4)

        return StorageCostEstimate(
            object_size_bytes=size_bytes_clean,
            current_storage_class=current_storage_class,
            recommended_storage_class=recommended_storage_class,
            current_monthly_cost_usd=current_cost,
            recommended_monthly_cost_usd=recommended_cost,
            estimated_monthly_savings_usd=monthly_savings,
            estimated_retrieval_risk_usd=retrieval_risk,
            pricing_assumption_version=thresholds.pricing_assumption_version,
        )
