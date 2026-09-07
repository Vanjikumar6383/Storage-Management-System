# Database Schema & Technical Documentation

## Overview
The **Storage Lifecycle Optimizer** database foundation is built on PostgreSQL, designed specifically as a high-performance, multi-tenant SaaS control plane.

---

## Complete Table Schema & Entity Relationships

```
+-------------------+           +--------------------------------+          +-------------------------+
|   organizations   |<---------1|    organization_memberships    |n--------1|          users          |
+-------------------+           +--------------------------------+          +-------------------------+
          ^
          | 1
          +---------------------+-------------------------+-------------------------+
          | n                   | 1                       | n                       | n
+-------------------+   +---------------+   +-------------------+   +-------------------------+
|   subscriptions   |   |environments   |   |storage_connections|   |    retention_policies   |
+-------------------+   +---------------+   +-------------------+   +-------------------------+
                                                            ^
                                                            | 1
                                                            | n
                                                    +-------------------+
                                                    | storage_locations |
                                                    +-------------------+
                                                              ^
                                                              | 1
                                                              | n
                                                    +-------------------+
                                                    |  storage_objects  |
                                                    +-------------------+
                                                              ^
                                                              | 1
                      +-------------------+-------------------+-------------------+
                      | n                 | n                 | n                 | n
               +--------------+   +---------------+   +---------------+   +---------------+
               | access_events|   | restore_events|   |  legal_holds  |   |recommendations|
               +--------------+   +---------------+   +---------------+   +---------------+
                                                                                  ^
                                                                                  | 1
                                                                                  | n
                                                                          +-------------------+
                                                                          | approval_requests |
                                                                          +-------------------+
```

### Table Definitions

1. **`organizations`**
   - Core tenant identifier entity.
   - Columns: `id` (UUID PK), `name` (VARCHAR), `slug` (VARCHAR UNIQUE), `created_at`, `updated_at`.

2. **`users`** & **`organization_memberships`**
   - Minimal RBAC identity structure.
   - `users`: `id` (UUID PK), `email` (VARCHAR UNIQUE), `is_active`, `created_at`, `updated_at`.
   - `organization_memberships`: `id` (UUID PK), `organization_id` (FK), `user_id` (FK), `role` (`OWNER`, `ADMIN`, `OPERATOR`, `VIEWER`), `created_at`, `updated_at`.

3. **`subscriptions`**
   - Extensible SaaS subscription tracking.
   - Columns: `id` (UUID PK), `organization_id` (FK UNIQUE), `plan`, `status`, `limits` (JSONB), `created_at`, `updated_at`.

4. **`storage_connections`**
   - External cloud storage provider connection registry.
   - Columns: `id` (UUID PK), `organization_id` (FK), `name`, `provider` (`AWS_S3`, `AZURE_BLOB`, `GOOGLE_CLOUD_STORAGE`, `LOCAL_S3_COMPATIBLE`), `credential_reference` (reference key only - NO raw secrets), `config` (JSONB), `created_at`, `updated_at`.

5. **`environments`**
   - Storage environments (development, testing, staging, temp CI).
   - Columns: `id` (UUID PK), `organization_id` (FK), `storage_connection_id` (FK), `name`, `status`, `last_activity_at`, `expires_at`, `created_at`, `updated_at`.

6. **`storage_locations`**
   - Bucket, container, or namespace abstractions.
   - Columns: `id` (UUID PK), `organization_id` (FK), `storage_connection_id` (FK), `name`, `region`, `created_at`, `updated_at`.

7. **`storage_objects`**
   - Core storage object metadata repository.
   - Columns: `id` (UUID PK), `organization_id` (FK), `storage_location_id` (FK), `environment_id` (FK nullable), `object_key`, `object_size_bytes` (BIGINT), `object_type`, `storage_class`, `current_state`, `created_at`, `last_modified_at`, `last_accessed_at`, `access_count_30d`, `access_count_90d`, `version_count`, `discovered_at`, `updated_at`.

8. **`access_events`** & **`restore_events`**
   - Access telemetry and cold-storage restore operation tracking.
   - `access_events`: `id`, `organization_id`, `object_id`, `event_type`, `event_timestamp`, `source`, `metadata` (JSONB).
   - `restore_events`: `id`, `organization_id`, `object_id`, `requested_at`, `completed_at`, `status`, `source_storage_class`, `target_storage_class`, `restore_duration_seconds`, `failure_reason`.

9. **`retention_policies`** & **`legal_holds`**
   - Governance and compliance immutability layers.
   - `retention_policies`: `id`, `organization_id`, `environment_id`, `storage_location_id`, `name`, `retention_duration_days`, `effective_date`, `status`, `priority`, `created_at`, `updated_at`.
   - `legal_holds`: `id`, `organization_id`, `object_id`, `status`, `reason_reference`, `created_at`, `released_at`.

10. **`recommendations`** & **`approval_requests`**
    - Explainable cost optimization recommendations and human-in-the-loop approvals.
    - `recommendations`: `id`, `organization_id`, `object_id`, `recommendation_type` (`KEEP`, `MOVE_TO_INFREQUENT_ACCESS`, `ARCHIVE`, `DELETE_CANDIDATE`, `HOLD`), `current_storage_class`, `recommended_storage_class`, `reason`, `evidence` (JSONB), `estimated_savings`, `risk_level`, `status`, `created_at`, `expires_at`.
    - `approval_requests`: `id`, `organization_id`, `recommendation_id`, `requested_action`, `status`, `requested_at`, `decided_at`, `decision`, `override_reason`.

11. **`migration_events`** & **`rollback_events`**
    - Migration auditability and rollback tracking.
    - `migration_events`: `id`, `organization_id`, `object_id`, `recommendation_id`, `source_storage_class`, `destination_storage_class`, `requested_at`, `started_at`, `completed_at`, `status`, `error_message`, `rollback_status`.
    - `rollback_events`: `id`, `organization_id`, `migration_id`, `reason`, `requested_at`, `completed_at`, `status`, `error_message`.

12. **`audit_logs`** & **`storage_cost_snapshots`**
    - Append-only system audit log and historical cost snapshot tracking.
    - `audit_logs`: `id`, `organization_id`, `action`, `resource_type`, `resource_id`, `actor_id`, `timestamp`, `outcome`, `metadata` (JSONB).
    - `storage_cost_snapshots`: `id`, `organization_id`, `storage_location_id`, `storage_class`, `storage_bytes`, `estimated_cost`, `snapshot_date`.

---

## Multi-Tenant Isolation Strategy

1. **Foreign Key Integrity**: Every organization-owned table mandates `organization_id NOT NULL` referencing `organizations(id)` with `ON DELETE CASCADE`.
2. **Scoped Query Pattern**: Application queries enforce `WHERE organization_id = :org_id`.
3. **PostgreSQL Row Level Security (RLS) Readiness**:
   ```sql
   ALTER TABLE storage_objects ENABLE ROW LEVEL SECURITY;
   CREATE POLICY tenant_isolation_policy ON storage_objects
       USING (organization_id = current_setting('app.current_organization_id')::uuid);
   ```

---

## Indexing Strategy

Targeted compound and single-column indexes optimized for control-plane query patterns:
- `(organization_id, environment_id)` on `storage_objects`
- `(organization_id, storage_location_id)` on `storage_objects`
- `(organization_id, last_accessed_at)` on `storage_objects`
- `(organization_id, storage_class)` on `storage_objects`
- `(organization_id, current_state)` on `storage_objects`
- `(object_id, status)` on `legal_holds`
- `(organization_id, priority)` on `retention_policies`
- `(organization_id, status)` on `recommendations`
- `(organization_id, timestamp)` on `audit_logs`

---

## Privacy & Data Minimization

- **Zero File Content Ingestion**: File data, byte streams, and object contents are never transmitted or stored.
- **Zero Personal Identifier Collection**: User identities are limited strictly to internal UUIDs and technical email handles. Personal names, phone numbers, billing addresses, or employee profiles are excluded.
- **Zero Raw Secrets Storage**: Storage connection credentials use reference aliases (e.g. `env:AWS_CRED_REF`), preventing credential exposure in database dumps or logs.
