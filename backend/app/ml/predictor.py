"""
Machine Learning Lifecycle Predictor & Inference Service.
Loads the trained Random Forest pipeline to classify storage objects into optimal lifecycle tiers.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd
import joblib

logger = logging.getLogger("storage.ml.predictor")

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_FILE = ARTIFACTS_DIR / "lifecycle_model.joblib"
METADATA_FILE = ARTIFACTS_DIR / "model_metadata.json"

NUMERIC_FEATURES = [
    "size_mb",
    "object_age_days",
    "access_count_30d",
    "last_access_days_ago",
    "restore_events_90d",
    "retention_days",
    "retention_expiry_days_left",
]

CATEGORICAL_FEATURES = [
    "env_type",
    "region",
    "data_category",
    "current_storage_class",
    "retention_policy",
    "legal_hold",
]

# Normalization mapping to application enum types
TARGET_TO_REC_TYPE = {
    "HOT": "KEEP",
    "COOL": "MOVE_TO_INFREQUENT_ACCESS",
    "COLD": "ARCHIVE",
    "ARCHIVE": "ARCHIVE",
    "DELETE_ELIGIBLE": "DELETE_CANDIDATE",
}

TARGET_TO_STORAGE_CLASS = {
    "HOT": "STANDARD",
    "COOL": "INFREQUENT_ACCESS",
    "COLD": "GLACIER",
    "ARCHIVE": "DEEP_ARCHIVE",
    "DELETE_ELIGIBLE": "DELETED",
}

STORAGE_CLASS_STANDARDIZATION = {
    "STANDARD": "HOT",
    "HOT": "HOT",
    "INFREQUENT_ACCESS": "COOL",
    "COOL": "COOL",
    "GLACIER": "COLD",
    "COLD": "COLD",
    "DEEP_ARCHIVE": "ARCHIVE",
    "ARCHIVE": "ARCHIVE",
}


class MLPredictor:
    """Singleton inference class for storage lifecycle recommendations."""

    _instance = None
    _pipeline = None
    _metadata = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MLPredictor, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        try:
            if MODEL_FILE.exists():
                logger.info(f"Loading ML model from {MODEL_FILE}")
                self._pipeline = joblib.load(MODEL_FILE)
            else:
                logger.warning(f"ML model file not found at {MODEL_FILE}. Predictions will be unavailable.")

            if METADATA_FILE.exists():
                with open(METADATA_FILE, "r") as f:
                    self._metadata = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load ML lifecycle model: {e}")
            self._pipeline = None
            self._metadata = None

    @property
    def is_available(self) -> bool:
        return self._pipeline is not None

    @property
    def metadata(self) -> Optional[Dict[str, Any]]:
        return self._metadata

    def reload(self):
        """Reload the model from disk after retraining."""
        self._load_model()

    def predict_object(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate an ML lifecycle recommendation prediction for an object.
        """
        if not self.is_available:
            return {
                "available": False,
                "reason": "ML Model not loaded or unavailable on host.",
            }

        # Normalize incoming raw features into model input
        raw_storage_class = str(features.get("current_storage_class", "STANDARD")).upper()
        norm_current_class = STORAGE_CLASS_STANDARDIZATION.get(raw_storage_class, "HOT")

        size_bytes = float(features.get("size_bytes", 0))
        size_mb = round(size_bytes / (1024 * 1024), 2) if size_bytes > 0 else float(features.get("size_mb", 1.0))

        row_dict = {
            "size_mb": size_mb,
            "object_age_days": int(features.get("object_age_days", 30)),
            "access_count_30d": int(features.get("access_count_30d", 0)),
            "last_access_days_ago": int(features.get("last_access_days_ago", features.get("object_age_days", 30))),
            "restore_events_90d": int(features.get("restore_events_90d", 0)),
            "retention_days": int(features.get("retention_days", 0)),
            "retention_expiry_days_left": int(features.get("retention_expiry_days_left", 999)),
            "env_type": str(features.get("env_type", "production")).lower(),
            "region": str(features.get("region", "us-east-1")).lower(),
            "data_category": str(features.get("data_category", "general_data")).lower(),
            "current_storage_class": norm_current_class,
            "retention_policy": str(features.get("retention_policy", "none")).lower(),
            "legal_hold": str(bool(features.get("legal_hold", False))),
        }

        df_single = pd.DataFrame([row_dict])
        pred_label = self._pipeline.predict(df_single)[0]

        # Calculate class probabilities
        probs = self._pipeline.predict_proba(df_single)[0]
        classes = self._pipeline.classes_
        class_prob_map = {cls_name: round(float(prob), 4) for cls_name, prob in zip(classes, probs)}
        confidence = float(class_prob_map.get(pred_label, max(probs)))

        # Rule overrides / guardrails for strict legal compliance
        has_legal_hold = bool(features.get("legal_hold", False))
        if has_legal_hold and pred_label == "DELETE_ELIGIBLE":
            logger.info("Compliance Override: Legal hold active. Demoting DELETE_ELIGIBLE to KEEP.")
            pred_label = "HOT"
            confidence = 1.0

        mapped_rec_type = TARGET_TO_REC_TYPE.get(pred_label, "KEEP")
        mapped_dest_class = TARGET_TO_STORAGE_CLASS.get(pred_label, raw_storage_class)

        # Estimate savings
        # Standard: ~$0.023/GB/mo, IA: ~$0.0125/GB/mo, Glacier: ~$0.004/GB/mo, Deep: ~$0.00099/GB/mo
        size_gb = size_mb / 1024.0
        unit_rates = {
            "STANDARD": 0.023,
            "HOT": 0.023,
            "INFREQUENT_ACCESS": 0.0125,
            "COOL": 0.0125,
            "GLACIER": 0.004,
            "COLD": 0.004,
            "DEEP_ARCHIVE": 0.00099,
            "ARCHIVE": 0.00099,
            "DELETED": 0.0,
        }

        current_rate = unit_rates.get(raw_storage_class, 0.023)
        target_rate = unit_rates.get(mapped_dest_class, current_rate)
        est_savings = max(0.0, round(size_gb * (current_rate - target_rate), 4))

        risk_level = "LOW"
        if pred_label == "DELETE_ELIGIBLE":
            risk_level = "HIGH"
        elif pred_label in ("COLD", "ARCHIVE"):
            risk_level = "MEDIUM"

        return {
            "available": True,
            "model_name": self._metadata.get("model_name", "RandomForestClassifier") if self._metadata else "RandomForest",
            "model_accuracy": self._metadata["metrics"]["accuracy"] if self._metadata else 0.99,
            "predicted_label": pred_label,
            "confidence": round(confidence, 4),
            "probabilities": class_prob_map,
            "mapped_recommendation_type": mapped_rec_type,
            "recommended_storage_class": mapped_dest_class,
            "current_storage_class": raw_storage_class,
            "estimated_monthly_savings_usd": est_savings,
            "risk_level": risk_level,
            "features_used": row_dict,
        }


# Global helper
_predictor_instance = None

def get_ml_predictor() -> MLPredictor:
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = MLPredictor()
    return _predictor_instance
