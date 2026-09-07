# Explainable Storage Lifecycle Recommendation Engine Specification

## Overview
The **Storage Lifecycle Recommendation Engine** is an explainable, deterministic, rule-based decision service. It analyzes object metadata, telemetry usage profiles, cold-restore activity, retention policy decisions, active legal holds, and storage class parameters to generate cost-optimized, governance-compliant lifecycle recommendations:

- `KEEP`: Maintain current storage class.
- `MOVE_TO_INFREQUENT_ACCESS`: Tier to Infrequent Access storage (e.g. AWS S3 Standard-IA / Azure Cool).
- `ARCHIVE`: Migrate to cold archive storage (e.g. AWS S3 Glacier / Azure Cold).
- `DELETE_CANDIDATE`: Candidate for human deletion review.
- `HOLD`: Blocked from automated tiering or deletion due to legal hold, active retention, restore risk, or policy ambiguity.

> [!IMPORTANT]
> **READ-ONLY SIMULATION BOUNDARY**: The recommendation engine **NEVER** executes deletions, storage migrations, or archive operations. All recommendations are advisory candidates that require explicit human approval via the governance workflow before any storage action can occur.

```
+-------------------+   +--------------------+   +-------------------+
|  Object Metadata  |   | Telemetry Profile  |   |   Policy Decision |
+---------+---------+   +---------+----------+   +---------+---------+
          |                       |                        |
          +-----------------------+------------------------+
                                  |
                                  v
                   +--------------+-------------+
                   |  Lifecycle Rule Engine     |
                   |  (Centralized Thresholds)  |
                   +--------------+-------------+
                                  |
                                  v
                   +--------------+-------------+
                   |  Explainable Recommendation|
                   |  & Cost Estimation         |
                   +----------------------------+
```

---

## 1. Rule Catalog & Deterministic Precedence

Rules are evaluated in strict priority order. Safety and legal constraints always supersede cost optimization:

| Priority | Rule ID | Rule Name | Trigger Condition | Output Recommendation | Risk Level | Impact Level | Requires Approval |
|---|---|---|---|---|---|---|---|
| **1** | `LEGAL-001` | Active Legal Hold Protection | `legal_hold_active == True` | **`HOLD`** | `LOW` | `HIGH_IMPACT` | `True` |
| **2** | `POLICY-002` | Policy Conflict Protection | `retention_state == 'UNKNOWN'` | **`HOLD`** | `HIGH` | `HIGH_IMPACT` | `True` |
| **3** | `RESTORE-001` | High Restore Risk Protection | `restore_risk == 'HIGH'` | **`HOLD` / `KEEP`** | `HIGH` | `HIGH_IMPACT` | `True` |
| **4** | `ACCESS-001` | Active Access Activity | `accesses_30d >= 5` or `HIGH`/`MEDIUM` frequency | **`KEEP`** | `LOW` | `LOW_IMPACT` | `False` |
| **5** | `SIZE-001` | Size Below Migration Limit | `object_size_bytes < 128 KB` or $\le 0$ | **`KEEP`** | `LOW` | `LOW_IMPACT` | `False` |
| **6** | `DELETE-001` | Deletion Eligibility Review | `age >= 365d`, `accesses_180d == 0`, `restores_90d == 0`, `retention == EXPIRED`, `legal_hold == False` | **`DELETE_CANDIDATE`** | `MEDIUM` | `HIGH_IMPACT` | `True` |
| **7** | `POLICY-001` | Active Retention Override | `age >= 365d`, `retention == ACTIVE` | **`HOLD`** | `LOW` | `HIGH_IMPACT` | `True` |
| **8** | `ARCHIVE-001` | Cold Archival Candidate | `age >= 180d`, `accesses_30d == 0`, `restores_90d == 0`, current class `STANDARD`/`IA` | **`ARCHIVE`** | `LOW` | `HIGH_IMPACT` | `True` |
| **9** | `IA-001` | Infrequent Access Candidate | `age >= 90d`, `accesses_30d == 0`, current class `STANDARD` | **`MOVE_TO_INFREQUENT_ACCESS`** | `LOW` | `LOW_IMPACT` | `False` |
| **10** | `SAME_CLASS-001`| Optimal Class Match | Already in target storage class | **`KEEP`** | `LOW` | `LOW_IMPACT` | `False` |

---

## 2. Centralized Thresholds & Configuration

Centralized configuration is maintained in [backend/app/core/recommendation_config.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/core/recommendation_config.py):

```python
rule_version = "baseline-v1"
archive_age_days = 180
infrequent_access_age_days = 90
delete_candidate_age_days = 365
minimum_accesses_for_keep = 5
minimum_object_size_for_migration_bytes = 131072 # 128 KB
```

---

## 3. Explainable Cost Estimation Model

Storage cost and potential monthly savings are estimated using baseline pricing assumptions:

$$\text{Current Monthly Cost} = \left(\frac{\text{size\_bytes}}{10^9}\right) \times \text{Rate}_{\text{current}}$$
$$\text{Recommended Monthly Cost} = \left(\frac{\text{size\_bytes}}{10^9}\right) \times \text{Rate}_{\text{recommended}}$$
$$\text{Estimated Monthly Savings} = \max(0, \text{Current Monthly Cost} - \text{Recommended Monthly Cost})$$

### Baseline Pricing Assumptions (USD per GB-month):
- `STANDARD`: **$0.023**
- `INFREQUENT_ACCESS`: **$0.0125**
- `ARCHIVE`: **$0.004**
- `DEEP_ARCHIVE`: **$0.00099**
- `RETRIEVAL_COST_PER_GB`: **$0.03**

---

## 4. Structured Evidence Payload Structure

Every generated recommendation contains a transparent, auditable evidence JSON payload:

```json
{
  "rules": [
    {
      "rule_id": "ARCHIVE-001",
      "rule_name": "Cold Object Eligible for Archival",
      "result": true,
      "evidence": "Age (250d) exceeds 180d with 0 accesses in 30d and 0 restores.",
      "priority": 8
    }
  ],
  "rule_version": "baseline-v1",
  "pricing_assumption_version": "2026-v1",
  "calculated_at": "2026-08-17T11:45:44Z",
  "impact_level": "HIGH_IMPACT",
  "requires_approval": true,
  "telemetry_summary": {
    "age_days": 250,
    "accesses_30d": 0,
    "accesses_180d": 0,
    "restores_90d": 0,
    "access_frequency": "NONE",
    "restore_risk": "LOW"
  },
  "policy_summary": {
    "retention_state": "EXPIRED",
    "legal_hold_active": false,
    "policy_decision": "ALLOWED"
  },
  "cost_summary": {
    "object_size_bytes": 52428800,
    "current_storage_class": "STANDARD",
    "recommended_storage_class": "ARCHIVE",
    "current_monthly_cost_usd": 0.0011,
    "recommended_monthly_cost_usd": 0.0002,
    "estimated_monthly_savings_usd": 0.0009,
    "estimated_retrieval_risk_usd": 0.0,
    "pricing_assumption_version": "2026-v1"
  }
}
```

---

## 5. Human Approval & Override Integrity

- **High-Impact Recommendations**: `ARCHIVE` and `DELETE_CANDIDATE` are flagged as `HIGH_IMPACT` with `requires_approval = True`.
- **Immutable History**: Operator approvals, rejections, or overrides are recorded separately in `approval_requests` and `audit_logs`. Existing recommendations remain immutable for audit integrity.
