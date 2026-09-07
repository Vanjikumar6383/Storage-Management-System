# Retention & Legal-Hold Policy Engine Specification

## Overview
The **Retention and Legal-Hold Policy Engine** is an independent, fail-safe governance layer in the Storage Lifecycle Optimizer. It evaluates whether a proposed lifecycle action (`KEEP`, `MOVE_TO_INFREQUENT_ACCESS`, `ARCHIVE`, `DELETE`) is `ALLOWED`, `BLOCKED`, or `REQUIRES_REVIEW` for a specific object.

The policy engine operates **completely independent from the recommendation engine**. The recommendation engine generates candidate optimization opportunities; the policy engine enforces safety, compliance, and legal hold constraints before any action can be executed or recommended.

```
       +--------------------+
       |   Storage Object   |
       +---------+----------+
                 |
     +-----------+-----------+
     |                       |
     v                       v
+----+---------------+ +-----+--------+
| Retention Policies | | Legal Holds  |
+----+---------------+ +-----+--------+
     |                       |
     +-----------+-----------+
                 |
                 v
      +----------+----------+
      |    Policy Engine    |
      |   (Simulations)     |
      +----------+----------+
                 |
                 v
      +----------+----------+
      |   Policy Decision   |
      | (ALLOWED/BLOCKED/   |
      |   REQUIRES_REVIEW)  |
      +---------------------+
```

---

## 1. Deterministic Policy Precedence Hierarchy

When multiple retention policies exist within an organization, the policy engine resolves the single applicable policy using a 4-tier hierarchy:

| Hierarchy Level | Precedence | Rule & Criteria |
|---|---|---|
| **Level 1: OBJECT** | **1 (Highest)** | `retention_policies.object_id == storage_object.id` |
| **Level 2: STORAGE LOCATION** | **2** | `retention_policies.storage_location_id == storage_object.storage_location_id` |
| **Level 3: ENVIRONMENT** | **3** | `retention_policies.environment_id == storage_object.environment_id` |
| **Level 4: ORGANIZATION** | **4 (Lowest)** | `object_id`, `storage_location_id`, `environment_id` are ALL `NULL` |

### Conflict Resolution within Same Level:
1. If multiple active policies exist at the same hierarchy level, the policy with the highest `priority` integer value is selected.
2. If multiple policies at the same level share the identical highest priority and have conflicting retention durations, the policy engine flags `has_conflict = True`.
3. **Fail-Safe Behavior**: Conflicting policies result in `retention_state = UNKNOWN`, which **BLOCKS / REQUIRES_REVIEW** destructive actions (`DELETE`).

---

## 2. Retention Expiration & Retention States

Retention duration is calculated from the effective date or object creation date:

$$\text{retention\_expires\_at} = \max(\text{policy.effective\_date}, \text{object.created\_at}) + \text{timedelta}(\text{days}=\text{policy.retention\_duration\_days})$$

| Retention State | Condition |
|---|---|
| `ACTIVE` | $\text{reference\_time} < \text{retention\_expires\_at}$ |
| `EXPIRED` | $\text{reference\_time} \ge \text{retention\_expires\_at}$ |
| `UNKNOWN` | Multiple conflicting policies detected at applicable level |
| `NO_POLICY` | No active policy found at any hierarchy level |

---

## 3. Absolute Legal Hold Override Rule

The `legal_holds` table tracks active legal preservation orders (`status = 'ACTIVE'`).

> [!IMPORTANT]
> **ABSOLUTE RULE**: If ANY active legal hold exists for an object (`legal_hold_active == True`), proposed `DELETE` actions are **IMMEDIATELY BLOCKED**.
> This rule overrides object age, access frequency, storage cost savings, retention expiration, and recommendation scores.

- **Released Holds**: Holds with `status = 'RELEASED'` or `released_at IS NOT NULL` do not trigger `legal_hold_active` and will not block deletion.

---

## 4. Action-Specific Governance Evaluation Matrix

| Proposed Action | Active Legal Hold Present? | Retention State | Policy Decision | Reason & Behavior |
|---|---|---|---|---|
| **`KEEP`** | Irrelevant | Any | `ALLOWED` | No data modification or deletion. |
| **`MOVE_TO_INFREQUENT_ACCESS`** | Active | Any | `ALLOWED` | Preserves accessibility & retention compliance. |
| **`ARCHIVE`** | Active | Any | `ALLOWED` | Archiving cold data preserves retention & legal holds. |
| **`DELETE`** | **Active** | Any | **`BLOCKED`** | Active legal hold prevents deletion. |
| **`DELETE`** | None | **`ACTIVE`** | **`BLOCKED`** | Retention period has not expired. |
| **`DELETE`** | None | **`EXPIRED`** | **`ALLOWED`** | Expiration passed and no legal hold present. |
| **`DELETE`** | None | **`NO_POLICY`** | **`REQUIRES_REVIEW`** | **Fail-Safe**: No policy requires manual review before deletion. |
| **`DELETE`** | None | **`UNKNOWN`** | **`REQUIRES_REVIEW`** | **Fail-Safe**: Conflicting policies require manual review before deletion. |

---

## 5. Fail-Safe Design Principles

1. **Closed by Default**: When policy information is missing (`NO_POLICY`), conflicting (`UNKNOWN`), or ambiguous, destructive actions (`DELETE`) are **NEVER** automatically allowed.
2. **Explicit Review Escalation**: Fail-safe scenarios return `decision = "REQUIRES_REVIEW"` with human-explainable evidence strings.
3. **No Side-Effects**: `PolicyEngineService.evaluate_action()` is a pure simulation algorithm. It evaluates governance logic without modifying storage tiers or deleting files.

---

## 6. Auditability & Governance Logs

Policy evaluations optionally log immutable audit records into `audit_logs`:
- `action`: `POLICY_EVALUATION`
- `resource_type`: `storage_objects`
- `resource_id`: `{object_id}`
- `outcome`: `ALLOWED` | `BLOCKED` | `REQUIRES_REVIEW`
- `metadata`: includes `proposed_action`, `retention_state`, `legal_hold_active`, and explainability `reasons`.

---

## 7. Example Decision Objects

### Example 1: Deletion Blocked by Active Legal Hold
```json
{
  "object_id": "ccf6aff2-1e23-407f-8d27-5bde35319fab",
  "organization_id": "5e82acbf-43ab-4cc3-8529-1ad83c0fdc26",
  "action": "DELETE",
  "decision": "BLOCKED",
  "retention_state": "EXPIRED",
  "legal_hold_active": true,
  "retention_expires_at": "2026-02-28T00:00:00Z",
  "applicable_policy_id": "ce26806d-0be3-495f-92db-716d1ed0a227",
  "reasons": [
    "Retention policy 'Expired 30d Retention' (OBJECT level) EXPIRED on 2026-02-28T00:00:00Z.",
    "Active legal hold(s) present: REF-LEGAL-LITIGATION-01.",
    "Active legal hold prevents object deletion."
  ],
  "evaluated_at": "2026-08-17T11:45:44Z"
}
```

### Example 2: Deletion Allowed (Retention Expired, No Legal Hold)
```json
{
  "object_id": "4a949840-0986-4a6f-ae7e-0678efec7aab",
  "organization_id": "5e82acbf-43ab-4cc3-8529-1ad83c0fdc26",
  "action": "DELETE",
  "decision": "ALLOWED",
  "retention_state": "EXPIRED",
  "legal_hold_active": false,
  "retention_expires_at": "2026-02-28T00:00:00Z",
  "applicable_policy_id": "3e935648-2a51-4cf9-a52c-af148d38c9bc",
  "reasons": [
    "Retention policy 'Expired 30d Retention' (OBJECT level) EXPIRED on 2026-02-28T00:00:00Z.",
    "Retention period has expired and no active legal hold exists."
  ],
  "evaluated_at": "2026-08-17T11:45:44Z"
}
```

### Example 3: Fail-Safe Requires Review (No Retention Policy)
```json
{
  "object_id": "5980cc5d-605a-4dae-8a32-70bb5480e952",
  "organization_id": "5e82acbf-43ab-4cc3-8529-1ad83c0fdc26",
  "action": "DELETE",
  "decision": "REQUIRES_REVIEW",
  "retention_state": "NO_POLICY",
  "legal_hold_active": false,
  "retention_expires_at": null,
  "applicable_policy_id": null,
  "reasons": [
    "No applicable retention policy found for object.",
    "No applicable retention policy found. Manual review required before deletion."
  ],
  "evaluated_at": "2026-08-17T11:45:44Z"
}
```
