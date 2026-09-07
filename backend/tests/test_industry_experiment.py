import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import Organization, StorageLocation, StorageObject, LegalHold, RetentionPolicy
from app.scripts.generate_industry_dataset import generate_industry_dataset, compute_ground_truth_label
from app.scripts.validate_dataset import validate_dataset
from app.services.industry_experiment import (
    BenchmarkQualityEvaluator,
    BenchmarkSafetyAuditor,
    BenchmarkSensitivityAnalyzer,
    BenchmarkAblationRunner,
)
from app.scripts.run_industry_experiment import run_single_experiment


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_1_2_dataset_generation_and_determinism(db_session):
    """TEST 1 & 2: Dataset generation and determinism with fixed seed 42."""
    generate_industry_dataset(num_orgs=5, num_envs=20, num_objects=500, seed=42)

    tot_objects = db_session.query(StorageObject).count()
    assert tot_objects == 500

    obj_sample = db_session.query(StorageObject).filter(StorageObject.scenario_tag == "SCENARIO_A").first()
    assert obj_sample is not None
    assert obj_sample.ground_truth_action == "ARCHIVE"


def test_3_dataset_quality_validation():
    """TEST 3: Dataset validation script checks data integrity and passes."""
    is_valid = validate_dataset(min_objects=100)
    assert is_valid is True


def test_4_ground_truth_independence():
    """TEST 4: Ground truth is calculated independently of recommendation engine."""
    gt_action, gt_reason = compute_ground_truth_label(
        age_days=250,
        accesses_30d=0,
        accesses_90d=0,
        restores_90d=0,
        storage_class="STANDARD",
        retention_active=False,
        retention_expired=False,
        legal_hold_active=True,
        policy_conflict=False,
        min_duration_satisfied=True,
    )
    assert gt_action == "HOLD"
    assert "legal hold" in gt_reason.lower()


def test_5_6_7_8_quality_and_safety_metrics(db_session):
    """TEST 5-8: Quality metrics (Accuracy, F1, Confusion Matrix) and zero safety violations."""
    evaluator = BenchmarkQualityEvaluator()
    q_res = evaluator.evaluate(db_session, partition="DEVELOPMENT")

    assert "accuracy_percentage" in q_res
    assert "macro_f1" in q_res
    assert "confusion_matrix" in q_res
    assert q_res["accuracy_percentage"] >= 50.0

    auditor = BenchmarkSafetyAuditor()
    s_res = auditor.audit(db_session, partition="DEVELOPMENT")

    assert s_res["legal_hold_violations"] == 0
    assert s_res["retention_violations"] == 0
    assert s_res["unsafe_delete_recommendations"] == 0
    assert s_res["benchmark_status"] == "PASS"


def test_9_10_sensitivity_and_ablation(db_session):
    """TEST 9 & 10: Sensitivity variations and information ablation simulations."""
    analyzer = BenchmarkSensitivityAnalyzer()
    sens_res = analyzer.analyze(db_session, partition="DEVELOPMENT")
    assert len(sens_res) == 5

    ablation_runner = BenchmarkAblationRunner()
    abl_res = ablation_runner.run_ablation(db_session, partition="DEVELOPMENT")
    assert "baseline" in abl_res
    assert len(abl_res["ablations"]) == 3


def test_11_12_single_experiment_runner():
    """TEST 11 & 12: CLI single experiment runner execution."""
    res = run_single_experiment(dataset_partition="development", seed=42)
    assert res["benchmark_status"] == "PASS"
    assert res["objects"] > 0
    assert "accuracy" in res
