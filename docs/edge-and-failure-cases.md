# Edge and Failure Cases Engineering Report

> **Document Version**: 1.0.0  
> **Status**: VERIFIED & DEMONSTRATED  
> **Test Suite**: `backend/scripts/run_edge_cases_demo.py` & `backend/tests/test_edge_and_failure_cases.py`  

---

## 1. Overview & Architectural Resilience

Real-world enterprise cloud storage does not operate under idealized conditions. Development environments are abruptly spun down, developers repeatedly restore cold assets during urgent bug fixes, conflicting retention policies exist across regulatory boundaries, and cloud provider APIs experience network timeouts.

The **Storage Lifecycle Optimizer** incorporates deterministic, fail-safe invariant guards to guarantee data safety, regulatory compliance, and cost predictability across all edge and failure scenarios.

```
                           Operational Edge Scenario
                                       │
        ┌───────────────────┬──────────┴──────────┬───────────────────┐
        ▼                   ▼                     ▼                   ▼
    Case 1:             Case 2:               Case 3:             Case 4:
  Legal Hold on       Restore Burst       Hierarchical Policy   Provider API /
 Expired Object       Thrashing Guard          Conflict         Network Failure
        │                   │                     │                   │
        ▼                   ▼                     ▼                   ▼
[ HOLD Enforced ]   [ Demotion Blocked /  [ Strictest Policy    [ Safe Rollback &
 (0% Violations)     Fee Avoidance ]       Takes Precedence ]    Error Audited ]
```

---

## 2. Deep Dive: Five Operational Edge & Failure Scenarios

### 2.1 Edge Case 1: Active Legal Hold on Expired Object
- **Operational Context**: An unmonitored development object (`legacy-log-9912.log`, 100 MB) was created 200 days ago. The organization has an active 90-day retention policy. Under normal rules, this object is past its retention period ($200 > 90$ days) with zero access in 180 days, which would trigger `DELETE_ELIGIBLE` or `DELETE_CANDIDATE`.
- **Edge Invariant**: An active legal hold (`LegalHold(status="ACTIVE", reason="SEC-AUDIT-HOLD-2026")`) is attached to this object due to an ongoing regulatory inquiry.
- **System Decision**: The **Policy & Recommendation Engine** evaluates the legal hold invariant with top priority (`Priority 1`).
  - *Recommendation Type*: `HOLD`
  - *Storage Class*: Maintained as `STANDARD`
  - *Requires Approval*: `True`
  - *Explainable Reason*: `"Active legal hold prevents deletion or tier migration."`
  - *Compliance Result*: **0% compliance violations**. Data is permanently protected from destruction.

### 2.2 Edge Case 2: Restore Thrashing & Retrieval Fee Protection
- **Operational Context**: A 500 GB database dump was previously archived in AWS S3 Glacier Deep Archive ($0.00099/GB/month). A QA engineering team begins reproducing a regression and triggers 3 restore events in the past 90 days (`restore_events_90d = 3`) and accesses the object 12 times in the last 30 days.
- **The Financial Trap**: In cloud storage, archival tiers charge significant per-GB retrieval fees ($0.03 to $0.05/GB) and expedited request fees. Keeping an actively restored 500 GB asset in Deep Archive incurs:
  $$\text{Retrieval Fee} = 500\,\text{GB} \times \$0.05/\text{GB} \times 3 = \$75.00$$
  This completely wipes out the monthly storage savings ($\$11.00/\text{month}$).
- **System Decision**: The Recommendation Engine detects **Restore Thrashing** (`prof.restore_risk == "HIGH"`):
  - *Recommendation Type*: `HOLD` / `KEEP` / `RESTORE_HOT_RECOMMENDED`
  - *Action*: Demotion is strictly blocked; tier promotion to `HOT` / `COOL` is advised to eliminate recurring per-GB retrieval fees.
  - *Financial Result*: Prevents unexpected cloud retrieval surcharge penalties.

### 2.3 Edge Case 3: Hierarchical Retention Policy Conflict Resolution
- **Operational Context**: An organization has configured:
  1. Default Organization-wide policy: 30-day retention (`priority = 1`).
  2. QA Environment-specific policy: 180-day retention (`priority = 10`).
  A build artifact is 60 days old ($60 > 30$, but $60 < 180$).
- **System Decision**: The **PolicyEngineService** evaluates the deterministic precedence hierarchy:
  $$\text{OBJECT\_OVERRIDE} > \text{STORAGE\_LOCATION} > \text{ENVIRONMENT} > \text{ORGANIZATION\_DEFAULT}$$
  - The Environment-level 180-day policy takes precedence over the 30-day organization default.
  - The object is evaluated as **Active Retention** (120 days remaining).
  - Premature deletion is blocked.

### 2.4 Edge Case 4: Storage Provider / Network Failure during Tier Migration
- **Operational Context**: An operator approves moving a 20 GB object from `STANDARD` to `ARCHIVE`. During the provider-side copy operation, the storage connector experiences a network drop or provider rate-limiting error (`503 SlowDown` / `ClientError`).
- **System Decision**: The **ApprovalExecutionService** wraps the operation in an ACID database transaction:
  - Catches the provider exception and extracts sanitized error messages (credentials and secret keys masked).
  - Emits a `MIGRATION_FAILED` audit log entry.
  - Leaves the object's `storage_class` in PostgreSQL as `STANDARD`.
  - Guarantees **zero state drift** between the cloud provider and the control plane database.
  - Supports instant single-click rollback verification.

### 2.5 Edge Case 5: Ephemeral Development Environment Decommissioning
- **Operational Context**: A short-lived CI/CD environment (`ci-branch-feature-4819`) was terminated and marked `SUSPENDED` 45 days ago. Leftover build logs (20 MB) remain unmonitored.
- **System Decision**:
  - The engine inspects environment status (`SUSPENDED`).
  - Evaluates object age (120 days old) against the `infrequent_access_age_days` threshold (90 days).
  - Automatically identifies the object as eligible for cost tiering (`MOVE_TO_INFREQUENT_ACCESS`), capturing savings without requiring manual developer intervention.

---

## 3. Automated Demonstration Verification

All 5 edge cases are tested and verified deterministically via `backend/scripts/run_edge_cases_demo.py`:

```
===========================================================================
   STORAGE LIFECYCLE OPTIMIZER — EDGE & FAILURE CASES DEMONSTRATION
===========================================================================

[1/5] Legal Hold Active on Expired Object (EDGE_CASE_1)
      Actual Decision: HOLD
      Explainable Reason: Active legal hold prevents deletion or tier migration.
      Status: [PASSED]
---------------------------------------------------------------------------
[2/5] Restore Thrashing & Retrieval Fee Protection (EDGE_CASE_2)
      Actual Decision: HOLD
      Explainable Reason: High restore activity indicates operational retrieval demand.
      Status: [PASSED]
---------------------------------------------------------------------------
[3/5] Hierarchical Retention Policy Conflict Resolution (EDGE_CASE_3)
      Description: Org-level 30d vs Env-level 180d. Strictest environment policy enforced.
      Status: [PASSED]
---------------------------------------------------------------------------
[4/5] Migration Execution & Single-Click Rollback Pipeline (EDGE_CASE_4)
      Rollback Status: SUCCESS (Restored to STANDARD)
      Status: [PASSED]
---------------------------------------------------------------------------
[5/5] Ephemeral Environment Decommissioning & Cleanup (EDGE_CASE_5)
      Actual Decision: MOVE_TO_INFREQUENT_ACCESS
      Explainable Reason: Object age exceeds 90 days with zero 30d access.
      Status: [PASSED]
---------------------------------------------------------------------------

SUMMARY: 5/5 Edge & Failure Cases PASSED!
===========================================================================
```
