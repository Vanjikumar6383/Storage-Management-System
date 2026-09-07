# Database Design & Entity Relationship Documentation

Documentation of the PostgreSQL relational schema, entities, fields, indexes, and relationships for the Storage Lifecycle Optimizer platform.

---

## 1. Entity Relationship Diagram (Text ERD)

```
┌─────────────────┐       ┌────────────────────────┐
│  organizations  │───────│  storage_connections   │
└────────┬────────┘       └───────────┬────────────┘
         │                            │
         │                            ▼
         │                ┌────────────────────────┐
         ├────────────────│   storage_locations    │
         │                └───────────┬────────────┘
         │                            │
         │                            ▼
         │                ┌────────────────────────┐
         ├────────────────│    storage_objects     │
         │                └───────────┬────────────┘
         │                            │
         │         ┌──────────────────┼──────────────────┐
         │         ▼                  ▼                  ▼
         │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
         ├─-│ telemetry_...│  │retention_... │  │ legal_holds  │
         │  └──────────────┘  └──────────────┘  └──────────────┘
         │                            │
         │                            ▼
         │                ┌────────────────────────┐
         ├────────────────│    recommendations     │
         │                └───────────┬────────────┘
         │                            │
         │                            ▼
         │                ┌────────────────────────┐
         ├────────────────│   approval_requests    │
         │                └───────────┬────────────┘
         │                            │
         │                            ▼
         │                ┌────────────────────────┐
         ├────────────────│    migration_events    │
         │                └───────────┬────────────┘
         │                            │
         │                            ▼
         │                ┌────────────────────────┐
         ├────────────────│    rollback_events     │
         │                └────────────────────────┘
         │
         ├────────────────┌────────────────────────┐
         │                │       audit_logs       │
         │                └────────────────────────┘
         │
         └────────────────┌────────────────────────┐
                          │     savings_ledger     │
                          └────────────────────────┘
```

---

## 2. Table Specifications & Entities

### 2.1 `organizations`
Primary multi-tenant isolation boundary entity.
- `id` (UUID, PK)
- `name` (VARCHAR(255), Not Null)
- `slug` (VARCHAR(255), Unique, Not Null)
- `created_at` (TIMESTAMPTZ, Default NOW())
- `updated_at` (TIMESTAMPTZ, Default NOW())

### 2.2 `storage_connections`
Stores storage provider connection profiles.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `name` (VARCHAR(255), Not Null)
- `provider` (VARCHAR(50), Not Null) — `LOCAL_S3_COMPATIBLE` or `AWS_S3`
- `credential_reference` (VARCHAR(255), Not Null)
- `config` (JSONB, Default `{}`)
- `created_at` (TIMESTAMPTZ)

### 2.3 `storage_locations`
Represents storage buckets or containers.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `storage_connection_id` (UUID, FK -> `storage_connections.id`, Not Null)
- `name` (VARCHAR(255), Not Null) — Bucket name
- `region` (VARCHAR(100), Default 'us-east-1')
- `created_at` (TIMESTAMPTZ)

### 2.4 `storage_objects`
Inventory entity tracking individual storage files.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `storage_location_id` (UUID, FK -> `storage_locations.id`, Not Null, Index)
- `object_key` (TEXT, Not Null) — S3 key path
- `object_size_bytes` (BIGINT, Not Null)
- `storage_class` (VARCHAR(50), Not Null) — `STANDARD`, `INFREQUENT_ACCESS`, `ARCHIVE`
- `created_at` (TIMESTAMPTZ, Not Null)
- `last_modified_at` (TIMESTAMPTZ, Not Null)
- **Indexes**: Composite index on `(organization_id, storage_class)`

### 2.5 `telemetry_events`
Tracks read access and restore telemetry events.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `object_id` (UUID, FK -> `storage_objects.id`, Not Null, Index)
- `event_type` (VARCHAR(50), Not Null) — `READ_ACCESS`, `RESTORE_REQUEST`
- `timestamp` (TIMESTAMPTZ, Not Null, Index)
- `metadata_payload` (JSONB, Default `{}`)

### 2.6 `retention_policies`
Compliance retention schedule rules.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `object_id` (UUID, FK -> `storage_objects.id`, Nullable, Index)
- `name` (VARCHAR(255), Not Null)
- `retention_duration_days` (INTEGER, Not Null)
- `effective_date` (TIMESTAMPTZ, Not Null)
- `status` (VARCHAR(50), Default 'ACTIVE')
- `priority` (INTEGER, Default 100)

### 2.7 `legal_holds`
Active legal hold overrides preventing modification or deletion.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `object_id` (UUID, FK -> `storage_objects.id`, Not Null, Index)
- `status` (VARCHAR(50), Default 'ACTIVE')
- `reason_reference` (TEXT, Not Null)
- `created_at` (TIMESTAMPTZ, Default NOW())
- `released_at` (TIMESTAMPTZ, Nullable)

### 2.8 `recommendations`
Explainable lifecycle recommendations generated by the recommendation engine.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `object_id` (UUID, FK -> `storage_objects.id`, Not Null, Index)
- `recommendation_type` (VARCHAR(50), Not Null) — `KEEP`, `MOVE_TO_INFREQUENT_ACCESS`, `ARCHIVE`, `DELETE_CANDIDATE`, `HOLD`
- `current_storage_class` (VARCHAR(50), Not Null)
- `recommended_storage_class` (VARCHAR(50), Not Null)
- `reason` (TEXT, Not Null)
- `risk_level` (VARCHAR(50), Default 'LOW')
- `estimated_savings` (NUMERIC(12, 4), Default 0.0)
- `status` (VARCHAR(50), Default 'PENDING')
- `evaluated_at` (TIMESTAMPTZ, Default NOW())

### 2.9 `approval_requests`
Operator human approval workflow authorizations.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `recommendation_id` (UUID, FK -> `recommendations.id`, Not Null, Index)
- `status` (VARCHAR(50), Default 'PENDING') — `PENDING`, `APPROVED`, `REJECTED`, `EXECUTED`
- `is_high_impact` (BOOLEAN, Default False)
- `decision_reason` (TEXT, Nullable)
- `decided_at` (TIMESTAMPTZ, Nullable)

### 2.10 `migration_events`
Executions of tier migrations.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `object_id` (UUID, FK -> `storage_objects.id`, Not Null, Index)
- `recommendation_id` (UUID, FK -> `recommendations.id`, Not Null)
- `source_storage_class` (VARCHAR(50), Not Null)
- `destination_storage_class` (VARCHAR(50), Not Null)
- `status` (VARCHAR(50), Default 'EXECUTING') — `SUCCESS`, `FAILED`, `ROLLED_BACK`
- `started_at` (TIMESTAMPTZ, Default NOW())
- `completed_at` (TIMESTAMPTZ, Nullable)

### 2.11 `rollback_events`
Restorations of original storage classes.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `migration_id` (UUID, FK -> `migration_events.id`, Not Null)
- `restored_storage_class` (VARCHAR(50), Not Null)
- `status` (VARCHAR(50), Default 'SUCCESS')
- `reason` (TEXT, Nullable)
- `created_at` (TIMESTAMPTZ, Default NOW())

### 2.12 `audit_logs`
Immutable audit log trail.
- `id` (UUID, PK)
- `organization_id` (UUID, FK -> `organizations.id`, Not Null, Index)
- `action` (VARCHAR(100), Not Null)
- `resource_type` (VARCHAR(100), Not Null)
- `resource_id` (VARCHAR(255), Not Null)
- `outcome` (VARCHAR(50), Not Null)
- `timestamp` (TIMESTAMPTZ, Default NOW(), Index)
- `metadata_payload` (JSONB, Default `{}`)

---

## 3. Database Indexes & Performance Optimization
- All tenant queries are indexed on `organization_id`.
- Fast object lookup is enabled by composite index `idx_storage_objects_org_class (organization_id, storage_class)`.
- Telemetry event lookups are optimized via `idx_telemetry_org_obj_time (organization_id, object_id, timestamp)`.
