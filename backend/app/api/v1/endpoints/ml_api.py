"""
Machine Learning Lifecycle Model REST Endpoints.
Provides model diagnostics, accuracy metrics, ad-hoc inference, and retraining triggers.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from app.ml.predictor import get_ml_predictor
from app.ml.train import train_lifecycle_model

router = APIRouter(prefix="/ml", tags=["Machine Learning Lifecycle Engine"])


class AdHocPredictSchema(BaseModel):
    size_bytes: int = Field(default=50 * 1024 * 1024)
    object_age_days: int = Field(default=90)
    access_count_30d: int = Field(default=0)
    last_access_days_ago: int = Field(default=90)
    restore_events_90d: int = Field(default=0)
    retention_days: int = Field(default=0)
    retention_expiry_days_left: int = Field(default=999)
    env_type: str = Field(default="production")
    region: str = Field(default="us-east-1")
    data_category: str = Field(default="general_data")
    current_storage_class: str = Field(default="STANDARD")
    retention_policy: str = Field(default="none")
    legal_hold: bool = Field(default=False)


@router.get("/model-info")
def get_ml_model_info():
    """Returns metadata, accuracy, F1 score, confusion matrix, and feature schema of trained ML model."""
    predictor = get_ml_predictor()
    if not predictor.is_available:
        return {
            "status": "UNAVAILABLE",
            "message": "ML Model artifact has not been trained or loaded.",
        }

    return {
        "status": "READY",
        "model_available": True,
        "metadata": predictor.metadata,
    }


@router.post("/predict")
def predict_lifecycle_ad_hoc(payload: AdHocPredictSchema):
    """Evaluate an object feature dictionary against the trained Random Forest model."""
    predictor = get_ml_predictor()
    if not predictor.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML Model not available.",
        )
    return predictor.predict_object(payload.model_dump())


def _background_retrain():
    train_lifecycle_model()
    predictor = get_ml_predictor()
    predictor.reload()


@router.post("/retrain")
def trigger_retrain(background_tasks: BackgroundTasks):
    """Trigger retraining on Data/storage_lifecycle_dataset_cleaned.csv."""
    background_tasks.add_task(_background_retrain)
    return {
        "status": "RETRAINING_SCHEDULED",
        "message": "Model retraining task dispatched in background on storage_lifecycle_dataset_cleaned.csv.",
    }
