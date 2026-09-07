"""
Industry Benchmark REST API Endpoints.
Exposes benchmark quality metrics, safety preservation audit, threshold sensitivity analysis,
and information ablation experiment results to the control-plane UI.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.industry_experiment import (
    BenchmarkQualityEvaluator,
    BenchmarkSafetyAuditor,
    BenchmarkSensitivityAnalyzer,
    BenchmarkAblationRunner,
)
from app.scripts.run_industry_experiment import run_single_experiment

router = APIRouter(prefix="/benchmark", tags=["Industry Benchmark & Experiment Framework"])


@router.get("/summary")
def get_benchmark_summary(
    partition: str = Query("validation", description="Dataset partition split (development, validation, stress, all)"),
    seed: int = Query(42, description="Random seed used for synthetic benchmark generation"),
    db: Session = Depends(get_db),
):
    """
    Fetch comprehensive benchmark summary including cost, quality, safety, and recommendation counts.
    """
    return run_single_experiment(dataset_partition=partition, seed=seed)


@router.get("/quality")
def get_benchmark_quality(
    partition: Optional[str] = Query(None, description="Partition filter"),
    db: Session = Depends(get_db),
):
    """
    Fetch precision, recall, F1 score, accuracy, and confusion matrix against ground truth.
    """
    evaluator = BenchmarkQualityEvaluator()
    return evaluator.evaluate(db, partition=partition)


@router.get("/safety")
def get_benchmark_safety(
    partition: Optional[str] = Query(None, description="Partition filter"),
    db: Session = Depends(get_db),
):
    """
    Audit legal-hold, retention, and restore-risk safety preservation.
    """
    auditor = BenchmarkSafetyAuditor()
    return auditor.audit(db, partition=partition)


@router.get("/sensitivity")
def get_benchmark_sensitivity(
    partition: Optional[str] = Query(None, description="Partition filter"),
    db: Session = Depends(get_db),
):
    """
    Fetch threshold sensitivity analysis results across archive age and access variations.
    """
    analyzer = BenchmarkSensitivityAnalyzer()
    return analyzer.analyze(db, partition=partition)


@router.get("/ablation")
def get_benchmark_ablation(
    partition: Optional[str] = Query(None, description="Partition filter"),
    db: Session = Depends(get_db),
):
    """
    Fetch information ablation experiment results (simulated removal of restore/access/legal-hold evidence).
    """
    runner = BenchmarkAblationRunner()
    return runner.run_ablation(db, partition=partition)
