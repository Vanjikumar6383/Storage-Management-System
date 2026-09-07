# Human Approval Workflow Specification

## Overview
The **Human Approval Workflow** governs storage lifecycle execution. To eliminate risk, **all recommendations require human approval by default**. No lifecycle migration or deletion simulation can be executed without an explicit `APPROVED` status recorded in the `approval_requests` table.

```
                  +--------------------+
                  |    PENDING         |
                  +---------+----------+
                            |
           +----------------+----------------+
           |                                 |
           v                                 v
  +------------------+             +------------------+
  |    APPROVED      |             |    REJECTED      |
  +--------+---------+             +------------------+
           |
           v
  +------------------+
  | EXECUTION_PENDING|
  +--------+---------+
           |
           v
  +------------------+
  |    EXECUTING     |
  +--------+---------+
           |
     +-----+-----+
     |           |
     v           v
+----+-----+ +---+--------------+
| EXECUTED | | EXECUTION_FAILED |
+----------+ +------------------+
```

---

## 1. Approval State Machine

| Status | Type | Description | Permitted Next Transitions |
|---|---|---|---|
| `PENDING` | Initial | Created upon recommendation generation. Awaiting review. | `APPROVED`, `REJECTED`, `EXPIRED` |
| `APPROVED` | Decision | Operator explicitly approved lifecycle action. | `EXECUTION_PENDING`, `EXECUTING`, `EXPIRED` |
| `REJECTED` | Decision | Operator rejected recommendation with override reason. | **Terminal** |
| `EXECUTION_PENDING` | Execution | Execution lock requested. | `EXECUTING` |
| `EXECUTING` | Execution | Migration / dry-run simulation currently executing. | `EXECUTED`, `EXECUTION_FAILED`, `EXECUTION_BLOCKED` |
| `EXECUTED` | Execution | Action completed successfully. | **Terminal** |
| `EXECUTION_FAILED` | Execution | Storage migration encountered error. | **Terminal** |
| `EXECUTION_BLOCKED` | Execution | Pre-execution safety gate blocked execution. | **Terminal** |
| `EXPIRED` | Expiry | Pre-execution check flagged stale recommendation. | **Terminal** |

### Invalid State Transitions:
Attempts to process invalid state transitions (e.g. `REJECTED` $\rightarrow$ `APPROVED`, `EXECUTED` $\rightarrow$ `APPROVED`, `EXECUTING` $\rightarrow$ `APPROVED`) raise strict `ValueError` and are rejected with HTTP 400.

---

## 2. Override Reasons & Audit Traceability

When an operator rejects or overrides a recommendation, an explicit override reason is captured in `approval_requests.override_reason` and logged in `audit_logs`:

```json
{
  "action": "RECOMMENDATION_REJECTED",
  "resource_type": "approval_requests",
  "resource_id": "appr-uuid-1234",
  "outcome": "REJECTED",
  "metadata": {
    "recommendation_id": "rec-uuid-5678",
    "decision": "REJECT",
    "override_reason": "Required for upcoming Q3 release build validation."
  }
}
```

---

## 3. Approval API Endpoints

- `POST /api/v1/recommendations/{recommendation_id}/approval`
- `GET /api/v1/recommendations/{recommendation_id}/approval`
