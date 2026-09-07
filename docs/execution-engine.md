# Safe Lifecycle Execution Engine & Pre-Execution Safety Gate

## Overview
The **Execution Engine** processes approved lifecycle recommendations. It enforces a **fresh pre-execution safety gate** immediately before executing any action, ensuring no stale or illegal operation is performed even if states changed after approval.

---

## 1. Pre-Execution Safety Gate (11 Safety Criteria)

Before executing any storage tier migration or deletion simulation, the engine evaluates 11 fresh criteria:

1. **Object Existence**: Object record exists in database.
2. **Tenant Scoping**: Object belongs to target `organization_id`.
3. **Approval Status**: Approval request status equals `APPROVED`.
4. **Recommendation Rule Version**: Rule version matches baseline specification (`baseline-v1`).
5. **Fresh Retention Policy Check**: Retention is `EXPIRED` (for deletion) or valid.
6. **Fresh Legal Hold Check**: Zero active legal holds exist for object.
7. **Storage Class Integrity**: Object storage class has not changed since recommendation was generated.
8. **Fresh Access Check**: Zero `OBJECT_READ` or `OBJECT_RESTORED` events occurred since recommendation creation. If accessed $\rightarrow$ returns `STALE_RECOMMENDATION`.
9. **Fresh Restore Check**: Zero restore events requested since recommendation creation. If restored $\rightarrow$ returns `STALE_RECOMMENDATION`.
10. **Recommendation Expiration**: Recommendation has not expired.
11. **Approval Expiration**: Approval remains valid.

> [!CAUTION]
> If ANY safety criterion fails, execution is immediately **BLOCKED** or marked **`STALE_RECOMMENDATION`**. An immutable audit log entry `EXECUTION_BLOCKED` is recorded.

---

## 2. Prototype Delete Safety Mode

> [!IMPORTANT]
> **PHYSICAL DELETION DISABLED**: In prototype safety mode, physical object deletion commands are strictly disabled.
> Approved `DELETE_CANDIDATE` executions run a **safe dry-run simulation** producing `status = "DELETE_SIMULATION_SUCCESS"`. The storage object payload remains 100% intact in storage.

---

## 3. Provider-Side Zero-Download Migration Execution

Storage class migrations (`MOVE_TO_INFREQUENT_ACCESS` or `ARCHIVE`) execute via provider-side zero-download copy semantics (`LocalS3Connector.copy_object_storage_class`).

- **No Memory Overhead**: Object content bytes are never downloaded into application memory.
- **Transactional DB State**: Database state updates (`storage_objects.storage_class`, `migration_events.status = 'SUCCESS'`) occur only after provider copy verification.
- **Failure Resilience**: If provider copy fails, object `storage_class` remains intact in its source tier. `migration_events.status = 'FAILED'` is recorded cleanly.

---

## 4. Execution API Endpoints

- `POST /api/v1/recommendations/{recommendation_id}/execute`
