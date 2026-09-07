# Industry-Grade Synthetic Benchmark Dataset

> [!NOTE]
> **SYNTHETIC BENCHMARK NOTICE**: This dataset is synthetic and does not represent any specific customer, user, or cloud provider. It is designed to model realistic software organization behavior across hundreds of short-lived development environments.

---

## 1. Overview & Objectives

The Storage Lifecycle Optimizer Benchmark Dataset models the storage usage, lifecycle behavior, and access patterns of software engineering organizations. It evaluates storage lifecycle optimization engines at scale (50,000+ objects) across realistic development environments without relying on cloud credentials or personal data.

### Key Objectives
- **Heterogeneous Organizations**: Represents 6 diverse company profiles (SaaS, FinTech, E-Commerce, AI/ML, Healthcare Software, Developer Tools).
- **Realistic Telemetry**: Incorporates realistic object size distributions, age populations, access frequencies, and restore behaviors.
- **Deterministic & Reproducible**: Fully reproducible using `random.seed(42)` with configurable scale parameters (`--organizations`, `--environments`, `--objects`).
- **Independent Ground-Truth**: Independent rules-based labeling (`compute_ground_truth_label`) ensures evaluation is non-circular.

---

## 2. Organization Profiles & Environment Types

### Fictional Organization Profiles
1. **SaaS Enterprise**: High volume of small log files, temporary build caches, and database backups.
2. **FinTech Platform**: Heavy retention policies, legal holds, and audit trace source archives.
3. **E-Commerce Cloud**: Moderate age distribution with analytics exports and package caches.
4. **AI / ML Startup**: Large object sizes (ML checkpoints, model artifacts 10 GB – 500 GB) with low access frequencies.
5. **Healthcare Software**: Strictest legal holds and 730-day retention policies with zero-delete compliance.
6. **Developer Tools**: High environment churn, short expected lifetimes (7–30 days), and stale build artifacts.

### Development Environment Types
- `DEVELOPMENT`: Developer sandboxes with active churn.
- `TEST` & `QA`: Intermediate test artifact storage.
- `STAGING`: Pre-production release staging environments.
- `CI_BUILD`: Short-lived ephemeral build workspaces.
- `DATA_ANALYTICS`: Heavy export files with medium access.
- `ML_TRAINING`: High-capacity model checkpoint buckets.
- `TEMPORARY`: Ephemeral work directories with short expected lifetimes (1–14 days).

---

## 3. Object Categories & Size Distributions

Objects are classified into 15 domain categories, each adhering to non-uniform size distributions:

| Object Category | Primary Size Tier | Size Range | Typical Access Pattern |
|---|---|---|---|
| `BUILD_CACHE` | Small / Medium | 1 MB – 100 MB | High during active builds, then drops |
| `LOG_FILE` | Small | 1 KB – 10 MB | High for 7d, then zero |
| `ML_CHECKPOINT` | Large / Very Large | 10 GB – 500 GB | Low access after training finishes |
| `DATABASE_BACKUP` | Large | 1 GB – 100 GB | Rare access, retention protected |
| `TEST_ARTIFACT` | Medium | 10 MB – 500 MB | Medium access for 30d |
| `RELEASE_ARTIFACT` | Medium / Large | 100 MB – 5 GB | Low access, long retention |
| `TEMPORARY_DATA` | Small | 1 KB – 50 MB | Never accessed after 1d |

---

## 4. Controlled Benchmark Scenarios (A–J)

The generator creates 10 explicit, tagged counterexamples and scenarios to evaluate recommender intelligence:

- **`SCENARIO_A`**: Old (>180d) + unused (0 accesses) + STANDARD $\rightarrow$ `ARCHIVE` candidate.
- **`SCENARIO_B`**: Old (>200d) + frequently accessed (15–100 accesses/30d) $\rightarrow$ `KEEP` (Tests false-positive protection).
- **`SCENARIO_C`**: Old + high restore frequency (3+ restores/90d) $\rightarrow$ `KEEP` / `HOLD` (Tests restore-risk awareness).
- **`SCENARIO_D`**: Expired retention policy + no legal hold $\rightarrow$ `DELETE_CANDIDATE`.
- **`SCENARIO_E`**: Expired retention policy + active legal hold $\rightarrow$ `HOLD` (Tests legal-hold safety block).
- **`SCENARIO_F`**: Conflicting retention policies $\rightarrow$ `REQUIRES_REVIEW` (Tests policy conflict safety).
- **`SCENARIO_G`**: Fresh object (<30d old) $\rightarrow$ `KEEP`.
- **`SCENARIO_H`**: Recently accessed after recommendation $\rightarrow$ Stale recommendation invalidation.
- **`SCENARIO_I`**: Minimum storage duration (30d) not satisfied $\rightarrow$ Transition warning/block.
- **`SCENARIO_J`**: Migration failure $\rightarrow$ Cost realization safety audit.

---

## 5. Benchmark Dataset Partitions

To prevent data leakage, objects are deterministically partitioned:
- **`DEVELOPMENT` Split (70%)**: 35,000 objects for threshold tuning and exploration.
- **`VALIDATION` Split (15%)**: 7,500 objects for benchmark quality & safety evaluation.
- **`STRESS` Split (15%)**: 7,500 objects for scale, concurrency, and high-hold density stress testing.

---

## 6. Dataset Quality & Validation CLI

The dataset quality validator enforces 9 strict integrity criteria before running experiments:

```bash
python -m app.scripts.validate_dataset --min-objects 50000
```

### Validation Checks Passed:
1. Total object count $\ge$ target.
2. Required non-null fields present.
3. Zero negative object sizes.
4. Valid storage class enums (`STANDARD`, `INFREQUENT_ACCESS`, `ARCHIVE`).
5. Access telemetry consistency ($30\text{d count} \le 90\text{d count}$).
6. Zero duplicate object keys.
7. Zero partition leakage across `DEV`, `VAL`, and `STRESS`.
8. Complete ground-truth labels for all objects.
9. Legal hold safety consistency (zero `DELETE_CANDIDATE` on active holds).
