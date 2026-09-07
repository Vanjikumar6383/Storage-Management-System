# Explainable Recommendation Algorithm & Decision Flow

Specification of the rule-based lifecycle recommendation engine, evidence structures, decision thresholds, and evaluation examples.

---

## 1. High-Level Decision Flow

```
Input: Storage Object Metadata (Key, Size, Class, Age)
                    │
                    ▼
          Query Active Legal Holds
                    │
        ┌───────────┴───────────┐
        │ Active Legal Hold?    │ ─── YES ───► Action: HOLD (Priority 1)
        └───────────┬───────────┘
                    │ NO
                    ▼
        Evaluate Retention Policies
                    │
        ┌───────────┴───────────┐
        │ Retention Active?     │ ─── YES ───► Action: HOLD (Priority 2)
        └───────────┬───────────┘
                    │ NO
                    ▼
        Evaluate Restore Penalties
                    │
        ┌───────────┴───────────┐
        │ High Restore Risk?    │ ─── YES ───► Action: HOLD / KEEP (Priority 3)
        └───────────┬───────────┘
                    │ NO
                    ▼
        Evaluate Telemetry Access Profile
                    │
        ┌───────────┴───────────┐
        │ Expired & 0 Access    │ ─── YES ───► Action: DELETE_CANDIDATE (Priority 4)
        │ (Age > 365d)?         │
        └───────────┬───────────┘
                    │ NO
                    ▼
        ┌───────────┴───────────┐
        │ Cold Object           │ ─── YES ───► Action: ARCHIVE (Priority 5)
        │ (Age > 180d, Acc90=0)?│
        └───────────┬───────────┘
                    │ NO
                    ▼
        ┌───────────┴───────────┐
        │ Inactive Object       │ ─── YES ───► Action: MOVE_TO_INFREQUENT_ACCESS (Priority 6)
        │ (Age > 60d, Acc30<=1)?│
        └───────────┬───────────┘
                    │ NO
                    ▼
              Action: KEEP (Priority 7)
```

---

## 2. Rule Evaluation Matrix & Priorities

| Priority | Rule ID | Action | Condition | Risk Level | High Impact? |
|---|---|---|---|---|---|
| **1** | `RULE_LEGAL_HOLD` | `HOLD` | Active record in `legal_holds` | `HIGH` | No |
| **2** | `RULE_RETENTION_ACTIVE` | `HOLD` | Unexpired retention policy | `HIGH` | No |
| **3** | `RULE_RESTORE_RISK` | `HOLD` | Restores (90d) > 3 AND penalty cost > savings | `HIGH` | No |
| **4** | `RULE_DELETE_EXPIRED` | `DELETE_CANDIDATE` | Retention expired AND 0 accesses (365d) AND age > 365d | `HIGH` | **Yes** |
| **5** | `RULE_ARCHIVE_COLD` | `ARCHIVE` | Age > 180d AND 0 accesses (90d) AND class != `ARCHIVE` | `MEDIUM` | Depends on size |
| **6** | `RULE_INFREQUENT` | `MOVE_TO_INFREQUENT_ACCESS` | Age > 60d AND accesses (30d) $\le$ 1 AND class == `STANDARD` | `LOW` | No |
| **7** | `RULE_DEFAULT_KEEP` | `KEEP` | Default / active access / already optimal class | `LOW` | No |

---

## 3. Concrete Step-by-Step Scenario Examples

### Scenario A: Cold Object Archival (`DEMO_ARCHIVE_COLD.dat`)
- **Object Metadata**: Key=`demo/DEMO_ARCHIVE_COLD.dat`, Size=50 GB, Class=`STANDARD`, Created=200 days ago.
- **Telemetry Profile**: Read Accesses (30d)=0, Read Accesses (90d)=0.
- **Policy Evaluation**: Legal Hold=False, Retention Policy=None.
- **Rule Processing**:
  - Rule 1 (Legal Hold): FAIL
  - Rule 2 (Retention Active): FAIL
  - Rule 3 (Restore Risk): FAIL
  - Rule 4 (Delete Expired): FAIL (Age < 365d)
  - Rule 5 (Archive Cold): **PASS** (`Age=200d > 180d, Acc90d=0`)
- **Generated Recommendation**:
  - **Action**: `ARCHIVE`
  - **Target Class**: `GLACIER` / `ARCHIVE`
  - **Reason**: `"Object age exceeds 180 days with zero recent access. Archival optimizes cost."`
  - **Estimated Savings**: `$0.95/month` (50 GB * ($0.023 - $0.004))

### Scenario B: Legal Hold Protection (`DEMO_LEGAL_HOLD.pdf`)
- **Object Metadata**: Key=`demo/DEMO_LEGAL_HOLD.pdf`, Size=8 GB, Class=`STANDARD`, Created=300 days ago.
- **Telemetry Profile**: Read Accesses (90d)=0.
- **Policy Evaluation**: Legal Hold=True (`"Regulatory Audit Hold #4092"`).
- **Rule Processing**:
  - Rule 1 (Legal Hold): **PASS** (`"Active legal hold 'Regulatory Audit Hold #4092' present."`)
- **Generated Recommendation**:
  - **Action**: `HOLD`
  - **Target Class**: `STANDARD` (No change allowed)
  - **Reason**: `"Active legal hold prevents lifecycle transition or deletion."`
  - **Estimated Savings**: `$0.00/month`

### Scenario C: Delete Candidate Safety Simulation (`DEMO_DELETE_CANDIDATE.tmp`)
- **Object Metadata**: Key=`demo/DEMO_DELETE_CANDIDATE.tmp`, Size=10 GB, Class=`STANDARD`, Created=400 days ago.
- **Telemetry Profile**: Read Accesses (365d)=0.
- **Policy Evaluation**: Retention Policy Expired (Effective 400d ago, Duration 30d).
- **Rule Processing**:
  - Rule 4 (Delete Expired): **PASS** (`"Retention expired 370d ago, 0 accesses in 365d"`)
- **Generated Recommendation**:
  - **Action**: `DELETE_CANDIDATE`
  - **High Impact**: `True` (Requires explicit approval)
  - **Execution Outcome**: Returns `DELETE_SIMULATION_SUCCESS` in dry-run mode without deleting physical bytes.
