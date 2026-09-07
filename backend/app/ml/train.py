"""
Storage Lifecycle Machine Learning Model Trainer.
Trains on Data/storage_lifecycle_dataset_cleaned.csv to predict optimal storage classes:
HOT, COOL, COLD, ARCHIVE, DELETE_ELIGIBLE.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("storage.ml.train")

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

TARGET_COLUMN = "recommended_storage_class"


def find_dataset_path() -> Path:
    """Resolve the path to storage_lifecycle_dataset_cleaned.csv."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "Data" / "storage_lifecycle_dataset_cleaned.csv",
        Path(__file__).resolve().parent.parent.parent / "Data" / "storage_lifecycle_dataset_cleaned.csv",
        Path.cwd() / "Data" / "storage_lifecycle_dataset_cleaned.csv",
        Path.cwd().parent / "Data" / "storage_lifecycle_dataset_cleaned.csv",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(f"Could not locate 'storage_lifecycle_dataset_cleaned.csv' in candidates: {candidates}")


def train_lifecycle_model(dataset_path: Path = None, artifacts_dir: Path = None):
    """
    Train and persist the Random Forest lifecycle recommendation model.
    """
    if dataset_path is None:
        dataset_path = find_dataset_path()

    if artifacts_dir is None:
        artifacts_dir = Path(__file__).resolve().parent / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading dataset from: {dataset_path}")
    df = pd.read_csv(dataset_path)
    logger.info(f"Loaded {len(df)} samples with columns: {list(df.columns)}")

    # Clean & format features
    df["legal_hold"] = df["legal_hold"].astype(str)
    for num_col in NUMERIC_FEATURES:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0)

    for cat_col in CATEGORICAL_FEATURES:
        df[cat_col] = df[cat_col].astype(str).fillna("unknown")

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET_COLUMN].astype(str)

    unique_classes = sorted(y.unique().tolist())
    logger.info(f"Target classes: {unique_classes}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    logger.info(f"Training split: {len(X_train)} samples; Test split: {len(X_test)} samples.")

    # Preprocessing Pipeline
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
        ]
    )

    # Random Forest Classifier
    classifier = RandomForestClassifier(
        n_estimators=120,
        max_depth=18,
        min_samples_split=4,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )

    logger.info("Training Random Forest Classifier pipeline...")
    pipeline.fit(X_train, y_train)

    # Evaluation
    logger.info("Evaluating on 20% test holdout...")
    y_pred = pipeline.predict(X_test)

    accuracy = float(accuracy_score(y_test, y_pred))
    weighted_f1 = float(f1_score(y_test, y_pred, average="weighted"))
    macro_f1 = float(f1_score(y_test, y_pred, average="macro"))
    precision = float(precision_score(y_test, y_pred, average="weighted"))
    recall = float(recall_score(y_test, y_pred, average="weighted"))

    cm = confusion_matrix(y_test, y_pred, labels=unique_classes).tolist()
    cls_report = classification_report(y_test, y_pred, output_dict=True)

    logger.info("=" * 60)
    logger.info(f"MODEL TRAINING RESULTS:")
    logger.info(f"   * Accuracy:  {accuracy * 100:.2f}%")
    logger.info(f"   * F1-Score:  {weighted_f1 * 100:.2f}% (Macro: {macro_f1 * 100:.2f}%)")
    logger.info(f"   * Precision: {precision * 100:.2f}%")
    logger.info(f"   * Recall:    {recall * 100:.2f}%")
    logger.info("=" * 60)

    # Persist model
    model_file = artifacts_dir / "lifecycle_model.joblib"
    joblib.dump(pipeline, model_file)
    logger.info(f"Saved trained pipeline to: {model_file}")

    metadata = {
        "model_name": "Storage Lifecycle RandomForestClassifier",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_name": dataset_path.name,
        "total_samples": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "metrics": {
            "accuracy": round(accuracy, 4),
            "weighted_f1": round(weighted_f1, 4),
            "macro_f1": round(macro_f1, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        },
        "target_classes": unique_classes,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "confusion_matrix": {
            "labels": unique_classes,
            "matrix": cm,
        },
        "classification_report": cls_report,
    }

    metadata_file = artifacts_dir / "model_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved model metadata to: {metadata_file}")

    return metadata


if __name__ == "__main__":
    train_lifecycle_model()
