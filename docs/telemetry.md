# Storage Access & Restore Telemetry Specification

## Overview
The **Telemetry & Object Usage Profiling Layer** measures storage object access patterns, frequency metrics, and cold-storage restore activity. It builds evidence profiles (`ObjectUsageProfile`) consumed by the future lifecycle recommendation engine.

The system enforces **strict data minimization** — tracking event timestamps, event types, and storage classes without collecting personal information, user identities, or object content.

---

## 1. Controlled Event Types

Telemetry events are ingested via `access_events` and `restore_events` tables:

| Event Type | Category | Description | Affects Lifecycle Access Frequency? |
|---|---|---|---|
| `OBJECT_READ` | Access Event | Object payload bytes retrieved | **YES (Meaningful Access)** |
| `OBJECT_RESTORED` | Access Event | Object restored from archive tier | **YES (Meaningful Access)** |
| `OBJECT_METADATA_READ` | Access Event | `HEAD` / `GET` metadata query | **NO (Operational Metadata)** |
| `OBJECT_CREATED` | Access Event | Initial object upload | NO |
| `OBJECT_DELETED` | Access Event | Object deletion event | NO |
| `OBJECT_MIGRATED` | Access Event | Storage class tier migration | NO |

---

## 2. Meaningful Access Definition

To prevent automated scanner or control-plane metadata requests from falsifying access metrics, the engine distinguishes between **operational metadata activity** and **actual object retrieval**:

- `OBJECT_METADATA_READ` events do **not** update `storage_objects.last_accessed_at` or increment access frequency counters.
- Only `OBJECT_READ` and `OBJECT_RESTORED` events increment access counters (`accesses_7d`, `accesses_30d`, `accesses_90d`, `accesses_180d`) and update `last_accessed_at`.

---

## 3. Access Frequency Classification

Access frequency is categorized into 5 tiers based on centralized thresholds ([backend/app/core/telemetry_config.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/core/telemetry_config.py)):

| Category | Threshold Condition (30-day / 180-day Window) |
|---|---|
| `HIGH` | $\ge 20$ meaningful accesses in last 30 days |
| `MEDIUM` | $\ge 5$ meaningful accesses in last 30 days |
| `LOW` | $\ge 1$ meaningful access in last 30 days |
| `VERY_LOW` | $\ge 1$ meaningful access in last 180 days |
| `NONE` | $0$ meaningful accesses in last 180 days |

---

## 4. Restore Risk Classification

Restore activity measures the operational and financial risk of archiving or migrating objects to deeper cold storage tiers:

| Risk Tier | Trigger Conditions & Explainability |
|---|---|
| `HIGH` | $\ge 3$ restores in 90 days **OR** restore failure rate $\ge 40\%$ ($\ge 2$ attempts) |
| `MEDIUM` | $1 - 2$ restores in 90 days **OR** $\ge 1$ restore in last 30 days |
| `LOW` | $0$ restores in 90 days |

Every risk calculation returns human-explainable evidence strings (e.g. `"High restore frequency: 5 restores in last 90 days"`).

---

## 5. Object Usage Profile (`ObjectUsageProfile`)

The telemetry service combines object metadata, access statistics, and restore risk into a unified evidence model:

```json
{
  "object_id": "44a7c7a2-b58a-40b2-a846-b89b70f2f4f2",
  "organization_id": "5e82acbf-43ab-4cc3-8529-1ad83c0fdc26",
  "object_key": "datasets/raw/2026/metrics.json",
  "storage_class": "STANDARD",
  "object_size_bytes": 1048576,
  "age_days": 200,
  "last_access_at": "2026-05-15T10:00:00Z",
  "days_since_last_access": 94,
  "accesses_7d": 0,
  "accesses_30d": 0,
  "accesses_90d": 0,
  "accesses_180d": 3,
  "total_meaningful_accesses": 3,
  "access_frequency": "VERY_LOW",
  "last_restore_at": null,
  "restores_30d": 0,
  "restores_90d": 0,
  "restores_180d": 0,
  "restore_success_rate": 1.0,
  "avg_restore_duration_seconds": null,
  "restore_risk": "LOW",
  "risk_explainability": ["Low restore activity: No recent restores detected."]
}
```

---

## 6. High-Performance Batch Aggregation (N+1 Query Prevention)

- Single-object queries: `GET /api/v1/objects/{object_id}/usage-profile`
- Multi-object batch aggregation: `ObjectUsageProfileService.batch_build_usage_profiles` executes **one single conditional SQL aggregation query** using PostgreSQL `CASE/COUNT/MAX/GROUP BY` primitives over target object IDs, eliminating $N+1$ query overhead across large datasets.

---

## 7. Data Retention & Privacy Strategy

- **Raw Access Events Retention**: Configured for 180 days (`TELEMETRY_THRESHOLDS.raw_event_retention_days`).
- **Aggregated Profile Retention**: Retained for 730 days (2 years).
- **Data Minimization Rules**: No employee names, personal email addresses, phone numbers, IP addresses, or document text content are collected or stored.
- **Client Idempotency**: `AccessEvent` and `RestoreEvent` support `idempotency_key` unique constraints to eliminate duplicate event recording.
