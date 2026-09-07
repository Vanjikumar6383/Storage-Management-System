# Production Storage Cost & Savings Engine Specification

## Overview
The **Storage Cost & Savings Engine** provides a provider-independent pricing abstraction (`PricingProvider`), exact PostgreSQL `Decimal` precision financial calculations, historical cost snapshots, an immutable realized savings ledger, a counterfactual **Baseline vs. Optimized** experiment framework, and unexecuted recommendation error classification.

---

## 1. Provider-Independent Pricing Abstraction

Pricing logic is fully decoupled from provider cloud credentials via `PricingProvider` ([backend/app/services/pricing_provider.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/services/pricing_provider.py)):

- `get_storage_price(db, provider, storage_class, region, version)`
- `get_retrieval_price(db, provider, storage_class, region, version)`
- `get_minimum_storage_duration(db, provider, storage_class, region, version)`
- `get_transition_cost(db, provider, source_class, target_class, region, version)`

### Development Demo Pricing Catalog (`storage_pricing_catalog` Table)
> [!NOTE]
> **Demo Pricing Disclaimer**: Default development pricing assumptions (`LOCAL_S3`) are for demonstration only and do not represent provider billing:
> - `STANDARD`: `$0.023000` / GB-month, 0 min days, `$0.00` retrieval
> - `INFREQUENT_ACCESS`: `$0.012500` / GB-month, 30 min storage days, `$0.01` retrieval / GB
> - `ARCHIVE`: `$0.004000` / GB-month, 90 min storage days, `$0.03` retrieval / GB

---

## 2. Financial Formulas & Precision

All monetary calculations utilize exact `Decimal` arithmetic persisted with PostgreSQL `Numeric` data types:

$$\text{monthly\_cost} = \text{round}\left(\frac{\text{object\_size\_bytes}}{1024^3} \times \text{price\_per\_gb\_month}, 4\right)$$

$$\text{estimated\_monthly\_savings} = \max(\text{current\_monthly\_cost} - \text{recommended\_monthly\_cost}, 0)$$

$$\text{savings\_percentage} = \frac{\text{baseline\_cost} - \text{optimized\_cost}}{\text{baseline\_cost}} \times 100$$

---

## 3. Savings Lifecycle & Ledger

```
  RECOMMENDED
       │
       ▼
    APPROVED
       │
       ▼
   EXECUTED
       │
       ▼
    REALIZED  ──────(Rollback)──────►  ROLLED_BACK
```

- **`SavingsLedger` Table**: Successful migration executions record an immutable ledger entry containing `previous_monthly_cost`, `new_monthly_cost`, `monthly_savings`, `annualized_savings`, and `pricing_version`.
- **Rollback Reversals**: Successful rollbacks update `status = 'ROLLED_BACK'`. Historical audit logs are never mutated.

---

## 4. Counterfactual Baseline vs. Optimized Experiment Framework

`ExperimentService` ([backend/app/services/cost_engine.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/services/cost_engine.py)) compares:
- **BASELINE**: Assumes objects remain in their original storage classes with zero tier transitions.
- **OPTIMIZED**: Counterfactual state assigning eligible objects their recommended storage class.

### Dataset Benchmark Results (`DemoCloud Labs` - 1,000 objects):
- **Baseline Monthly Cost**: `$18.29` / month
- **Optimized Monthly Cost**: `$6.70` / month
- **Estimated Monthly Savings**: `$11.59` / month (**63.35% cost reduction**)
- **Eligible Objects**: 749 objects (633 Archive, 116 Infrequent Access)
- **Kept in Standard**: 237 objects

---

## 5. Unexecuted Recommendation Error Analysis

`ErrorAnalysisService` categorizes unexecuted recommendations into 10 explicit operational categories:
1. `RETENTION_BLOCK`
2. `LEGAL_HOLD`
3. `HIGH_RESTORE_RISK`
4. `POLICY_CONFLICT`
5. `STALE_RECOMMENDATION`
6. `APPROVAL_REJECTED`
7. `EXECUTION_FAILED`
8. `MINIMUM_STORAGE_CONSTRAINT`
9. `INSUFFICIENT_DATA`
10. `OTHER`

---

## 6. Cost REST API Endpoints (`backend/app/api/v1/endpoints/costs.py`)

- `GET /api/v1/costs/summary`
- `GET /api/v1/costs/by-class`
- `GET /api/v1/costs/by-environment`
- `GET /api/v1/costs/history`
- `GET /api/v1/costs/savings`
- `GET /api/v1/costs/ledger`
- `GET /api/v1/costs/experiment`
- `GET /api/v1/costs/error-analysis`
