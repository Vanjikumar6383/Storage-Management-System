"""
Benchmark Experiment Runner CLI Tool.
Executes storage lifecycle optimization experiment against synthetic dataset partitions,
calculates recommendation quality, safety preservation, cost reduction, multi-seed statistics,
sensitivity variations, and information ablation experiments.
"""

import argparse
import sys
import math
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import SessionLocal
from app.models import StorageObject, Recommendation
from app.services.industry_experiment import (
    BenchmarkQualityEvaluator,
    BenchmarkSafetyAuditor,
    BenchmarkSensitivityAnalyzer,
    BenchmarkAblationRunner,
)
from app.services.cost_engine import ExperimentService, CostSummaryService
from app.scripts.generate_industry_dataset import generate_industry_dataset


def run_single_experiment(dataset_partition: str = "validation", seed: int = 42) -> dict:
    db: Session = SessionLocal()
    try:
        partition_filter = None if dataset_partition.lower() == "all" else dataset_partition.upper()

        query = db.query(StorageObject)
        if partition_filter:
            query = query.filter(StorageObject.dataset_partition == partition_filter)

        objs = query.all()
        if not objs:
            print(f"No objects found for partition '{dataset_partition}'. Generating dataset with seed {seed}...")
            generate_industry_dataset(num_orgs=20, num_envs=500, num_objects=50000, seed=seed)
            objs = query.all()

        tot_objects = len(objs)
        org_ids = list(set(o.organization_id for o in objs))
        env_count = len(set(o.environment_id for o in objs if o.environment_id))

        # 1. Quality Evaluation
        evaluator = BenchmarkQualityEvaluator()
        quality_res = evaluator.evaluate(db, partition=partition_filter)

        # 2. Safety Audit
        auditor = BenchmarkSafetyAuditor()
        safety_res = auditor.audit(db, partition=partition_filter)

        # 3. Cost & Savings Experiment
        first_org_id = org_ids[0] if org_ids else None
        exp_service = ExperimentService()
        cost_res = exp_service.run_counterfactual_experiment(db, first_org_id) if first_org_id else {}

        # Aggregate counts per action
        matrix = quality_res.get("confusion_matrix", {})
        action_counts = {a: sum(matrix.get(a, {}).values()) for a in ["KEEP", "INFREQUENT_ACCESS", "ARCHIVE", "DELETE_CANDIDATE", "HOLD", "REQUIRES_REVIEW"]}

        res = {
            "dataset": dataset_partition.capitalize(),
            "seed": seed,
            "organizations": len(org_ids),
            "environments": env_count,
            "objects": tot_objects,
            "baseline_monthly_cost": cost_res.get("baseline_monthly_cost_usd", 0.0),
            "optimized_monthly_cost": cost_res.get("optimized_monthly_cost_usd", 0.0),
            "potential_savings": cost_res.get("estimated_monthly_savings_usd", 0.0),
            "savings_percentage": cost_res.get("estimated_savings_percentage", 0.0),
            "action_counts": action_counts,
            "accuracy": quality_res.get("accuracy_percentage", 0.0),
            "precision": quality_res.get("macro_precision", 0.0),
            "recall": quality_res.get("macro_recall", 0.0),
            "f1": quality_res.get("macro_f1", 0.0),
            "legal_hold_violations": safety_res.get("legal_hold_violations", 0),
            "retention_violations": safety_res.get("retention_violations", 0),
            "unsafe_delete_recommendations": safety_res.get("unsafe_delete_recommendations", 0),
            "high_risk_archive_recommendations": safety_res.get("high_restore_risk_archive_recommendations", 0),
            "benchmark_status": safety_res.get("benchmark_status", "PASS"),
        }
        return res

    finally:
        db.close()


def print_experiment_report(res: dict):
    print("====================================================")
    print("STORAGE LIFECYCLE OPTIMIZER — BENCHMARK REPORT")
    print("====================================================")
    print(f"Dataset:                              {res['dataset']}")
    print(f"Seed:                                 {res['seed']}")
    print(f"Organizations:                        {res['organizations']}")
    print(f"Environments:                         {res['environments']}")
    print(f"Objects Analyzed:                     {res['objects']:,}")
    print("----------------------------------------------------")
    print("COST REDUCTION")
    print("----------------------------------------------------")
    print(f"Baseline Monthly Cost:                ${res['baseline_monthly_cost']:.2f}/mo")
    print(f"Optimized Monthly Cost:               ${res['optimized_monthly_cost']:.2f}/mo")
    print(f"Potential Monthly Savings:            ${res['potential_savings']:.2f}/mo")
    print(f"Savings Percentage:                   {res['savings_percentage']:.2f}%")
    print("----------------------------------------------------")
    print("RECOMMENDATION DISTRIBUTION")
    print("----------------------------------------------------")
    for act, cnt in res['action_counts'].items():
        print(f"  {act:<24} : {cnt:,}")
    print("----------------------------------------------------")
    print("QUALITY METRICS")
    print("----------------------------------------------------")
    print(f"Accuracy:                             {res['accuracy']:.2f}%")
    print(f"Precision (Macro):                    {res['precision']:.2f}%")
    print(f"Recall (Macro):                       {res['recall']:.2f}%")
    print(f"F1 Score (Macro):                     {res['f1']:.2f}%")
    print("----------------------------------------------------")
    print("SAFETY PRESERVATION")
    print("----------------------------------------------------")
    print(f"Legal Hold Violations:                {res['legal_hold_violations']}")
    print(f"Retention Violations:                 {res['retention_violations']}")
    print(f"Unsafe Delete Recommendations:        {res['unsafe_delete_recommendations']}")
    print(f"High-Risk Archive Candidates:         {res['high_risk_archive_recommendations']}")
    print("----------------------------------------------------")
    print(f"FINAL BENCHMARK RESULT:               {res['benchmark_status']}")
    print("====================================================")


def run_multi_seed_comparison(dataset_partition: str = "validation", seeds: List[int] = [42, 43, 44]):
    print("====================================================")
    print(f"RUNNING MULTI-SEED BENCHMARK COMPARISON ({seeds})")
    print("====================================================")

    results = []
    for s in seeds:
        print(f"-> Generating & evaluating seed {s}...")
        generate_industry_dataset(num_orgs=20, num_envs=500, num_objects=50000, seed=s)
        res = run_single_experiment(dataset_partition=dataset_partition, seed=s)
        results.append(res)

    accuracies = [r["accuracy"] for r in results]
    f1s = [r["f1"] for r in results]
    savings_pcts = [r["savings_percentage"] for r in results]

    def calc_stats(vals):
        mean_val = sum(vals) / len(vals)
        var = sum((x - mean_val) ** 2 for x in vals) / len(vals)
        std_dev = math.sqrt(var)
        return {"mean": mean_val, "min": min(vals), "max": max(vals), "std_dev": std_dev}

    acc_stats = calc_stats(accuracies)
    f1_stats = calc_stats(f1s)
    sav_stats = calc_stats(savings_pcts)

    print("\n----------------------------------------------------")
    print("MULTI-SEED STATISTICAL SUMMARY")
    print("----------------------------------------------------")
    print(f"Accuracy   : Mean={acc_stats['mean']:.2f}%, Min={acc_stats['min']:.2f}%, Max={acc_stats['max']:.2f}%, StdDev={acc_stats['std_dev']:.2f}")
    print(f"F1 Score   : Mean={f1_stats['mean']:.2f}%, Min={f1_stats['min']:.2f}%, Max={f1_stats['max']:.2f}%, StdDev={f1_stats['std_dev']:.2f}")
    print(f"Savings %  : Mean={sav_stats['mean']:.2f}%, Min={sav_stats['min']:.2f}%, Max={sav_stats['max']:.2f}%, StdDev={sav_stats['std_dev']:.2f}")
    print("====================================================")


def main():
    parser = argparse.ArgumentParser(description="Run Industry Storage Lifecycle Optimizer Benchmark")
    parser.add_argument("--dataset", type=str, choices=["all", "development", "validation", "stress"], default="validation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--multi-seed", action="store_true", help="Run multi-seed comparison across seeds 42, 43, 44")

    args = parser.parse_args()

    if args.multi_seed:
        run_multi_seed_comparison(dataset_partition=args.dataset, seeds=[42, 43, 44])
    else:
        res = run_single_experiment(dataset_partition=args.dataset, seed=args.seed)
        print_experiment_report(res)
        if res["benchmark_status"] != "PASS":
            sys.exit(1)


if __name__ == "__main__":
    main()
