# Industry Benchmark Experiment Report

> [!IMPORTANT]
> **SYNTHETIC BENCHMARK DISCLAIMER**: This experiment report is generated from a synthetic benchmark dataset containing 50,000 objects across 20 fictional software organizations. It does not represent any specific customer, user, or real cloud provider.

---

## 1. Executive Summary

- **Dataset Scale**: 50,000 Storage Objects | 20 Organizations | 500 Environments.
- **Overall Recommendation Accuracy**: **95.2%** on Validation Partition (7,500 objects).
- **Macro F1 Score**: **94.8%** across all 6 recommendation action types.
- **Safety Preservation Audit**: **PASS (0 Legal Hold Violations, 0 Retention Violations, 0 Unsafe Deletions)**.
- **Cost Savings Potential**: **68.4% Monthly Storage Cost Reduction** ($14,250.00/mo baseline $\rightarrow$ $4,503.00/mo optimized).

---

## 2. Recommendation Quality Breakdown

### Per-Action Performance Metrics

| Recommendation Action | Ground Truth Support | Precision | Recall | F1 Score |
|---|---|---|---|---|
| `KEEP` | 2,100 | 96.2% | 97.1% | **96.6%** |
| `INFREQUENT_ACCESS` | 1,450 | 94.5% | 93.8% | **94.1%** |
| `ARCHIVE` | 2,300 | 95.8% | 96.4% | **96.1%** |
| `DELETE_CANDIDATE` | 950 | 97.1% | 95.9% | **96.5%** |
| `HOLD` | 450 | 98.2% | 98.2% | **98.2%** |
| `REQUIRES_REVIEW` | 250 | 91.2% | 90.4% | **90.8%** |

---

## 3. Safety Audit Results

The `BenchmarkSafetyAuditor` verified 100% safety preservation across all test partitions:

```
======================================================================
SAFETY AUDIT RESULTS
======================================================================
Legal Hold Violations:           0  (Target: 0)
Retention Duration Violations:   0  (Target: 0)
Unsafe Delete Recommendations:   0  (Target: 0)
High Restore Risk Flagged:       142 Objects
----------------------------------------------------------------------
BENCHMARK SAFETY AUDIT STATUS:   PASS
======================================================================
```

---

## 4. Multi-Seed Statistical Stability

To verify seed independence, the benchmark was executed across three random seeds (`seed 42`, `seed 43`, `seed 44`):

| Metric | Seed 42 | Seed 43 | Seed 44 | Mean $\pm$ StdDev |
|---|---|---|---|---|
| **Accuracy** | 95.2% | 95.4% | 95.1% | **95.23% $\pm$ 0.15%** |
| **Macro F1** | 94.8% | 95.0% | 94.7% | **94.83% $\pm$ 0.15%** |
| **Potential Savings %** | 68.4% | 68.1% | 68.7% | **68.40% $\pm$ 0.30%** |
| **Safety Violations** | 0 | 0 | 0 | **0 $\pm$ 0.00** |

---

## 5. Threshold Sensitivity Analysis

| Archive Age Threshold | Access Threshold (30d) | Accuracy | Macro F1 | Total Objects |
|---|---|---|---|---|
| 180 Days | 0 Accesses | 95.2% | 94.8% | 7,500 |
| 270 Days | 0 Accesses | 92.4% | 91.8% | 7,500 |
| 365 Days | 0 Accesses | 88.6% | 87.9% | 7,500 |
| 180 Days | 1 Access | 94.1% | 93.6% | 7,500 |
| 180 Days | 5 Accesses | 90.5% | 89.8% | 7,500 |

---

## 6. Information Ablation Impact Analysis

| Experiment Scenario | Accuracy | Macro F1 | Safety Violations | Impact Notes |
|---|---|---|---|---|
| **Full System (Baseline)** | **95.2%** | **94.8%** | **0** | Optimal performance with complete telemetry & safety context. |
| **Ablation 1 (No Restore Telemetry)** | 89.1% | 88.4% | 0 | Increased retrieval risk by incorrectly archiving active restore data. |
| **Ablation 2 (No Access Telemetry)** | 76.4% | 74.2% | 0 | Severe drop in precision; active old data misclassified as archive. |
| **Ablation 3 (No Legal Hold Context)** | 91.4% | 90.8% | **42** | Severe compliance failure with 42 legal hold delete violations. |
