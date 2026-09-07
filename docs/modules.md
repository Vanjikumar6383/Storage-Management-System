# System Modules Documentation

Detailed technical specification for all 16 core modules in the Storage Lifecycle Optimizer platform.

---

## 1. Tenant Organization & Membership Module
- **Purpose**: Manages multi-tenant isolation, user accounts, memberships, roles, and subscription tier limits.
- **Input**: User registration details, organization names, role assignments (`OWNER`, `OPERATOR`, `VIEWER`).
- **Processing**: Enforces tenant boundary checks on every API request.
- **Output**: Tenant organization contexts and member authorization roles.
- **Safety**: Isolates data records by `organization_id`. Cross-tenant queries are blocked.

---

## 2. Storage Connector Module
- **Purpose**: Abstract interface for executing storage provider operations (`test_connection`, `list_storage_locations`, `list_objects`, `get_object_metadata`, `copy_object_storage_class`).
- **Input**: Connection parameters, bucket names, object keys, target storage classes.
- **Processing**: Routes requests to `LocalS3Connector` or `AWSS3Connector`.
- **Output**: Standardized metadata objects (`NormalizedObjectMetadata`) and boolean execution flags.
- **Safety**: Executes zero-download migrations without downloading object payload bytes across network boundaries.

---

## 3. Connector Factory Module (`ConnectorFactory`)
- **Purpose**: Dynamically resolves and instantiates the correct storage connector for a given storage connection or storage object.
- **Input**: Database session and `connection_id` or `object_id`.
- **Processing**: Reads `StorageConnection.provider` and instantiates `LocalS3Connector` or `AWSS3Connector`.
- **Output**: Concrete connector instance (`BaseStorageConnector`), `StorageLocation`, and `StorageConnection`.
- **Safety**: Strict non-fallback policy. If AWS configuration is missing when `AWS_S3` is selected, raises `AWSConfigurationError` instead of silently falling back to local storage.

---

## 4. Metadata Ingestion & Sync Job Module
- **Purpose**: Scans connected storage locations and syncs storage object metadata into the PostgreSQL database.
- **Input**: Connection ID, bucket name, pagination tokens.
- **Processing**: Iterates through object keys, sizes, storage classes, and last modified timestamps, updating or inserting `StorageObject` records idempotently.
- **Output**: Updated `StorageObject` inventory records and `SyncJob` execution status logs.
- **Safety**: Zero payload inspection; reads header metadata only.

---

## 5. Telemetry & Access Profiling Module
- **Purpose**: Ingests read access and restore events to compile `ObjectUsageProfile` summaries.
- **Input**: Access event logs, timestamped read requests, restore event logs.
- **Processing**: Filters operational metadata requests (e.g. `head_object`) vs meaningful payload reads. Computes 30d, 90d, 180d, 365d access counts and restore counts.
- **Output**: `ObjectUsageProfile` data structures.
- **Safety**: Idempotent event ingestion preventing duplicate event counting.

---

## 6. Policy Engine Module (`PolicyEngineService`)
- **Purpose**: Evaluates retention schedules and active legal holds against storage objects.
- **Input**: Organization ID, Object ID, reference timestamp.
- **Processing**: Evaluates policy hierarchy (Object-specific > Location-specific > Organization-wide). Checks active legal hold records in `legal_holds`.
- **Output**: `PolicyDecision` containing `can_transition`, `can_delete`, `active_holds`, and `effective_policy`.
- **Safety**: Active legal holds return `HOLD` and block all lifecycle transitions or deletions.

---

## 7. Explainable Recommendation Engine Module (`RecommendationService`)
- **Purpose**: Evaluates object metadata, telemetry profiles, and policy decisions against rule thresholds to generate explainable recommendations.
- **Input**: Storage object, usage profile, policy decision, reference timestamp.
- **Processing**: Evaluates rules in priority order (`HOLD` $\rightarrow$ `DELETE_CANDIDATE` $\rightarrow$ `ARCHIVE` $\rightarrow$ `INFREQUENT_ACCESS` $\rightarrow$ `KEEP`).
- **Output**: `RecommendationResult` with recommendation type, recommended class, reason string, risk level, estimated savings, and `RuleEvaluationResult` evidence list.
- **Safety**: Immutable recommendation records ensuring complete auditability.

---

## 8. Cost & Savings Engine Module (`CostEstimationService`)
- **Purpose**: Calculates current storage costs, potential monthly savings, and retrieval risk penalties.
- **Input**: Object size in bytes, current storage class, target storage class, restore frequency.
- **Processing**: Applies unit rates ($0.023/GB/mo for Standard, $0.0125/GB/mo for IA, $0.004/GB/mo for Archive) and computes monthly cost differentials.
- **Output**: `StorageCostEstimate` structures.
- **Safety**: Non-negative savings constraints prevent negative savings representations.

---

## 9. Human Approval Workflow Module
- **Purpose**: Manages operator authorization for recommended tiering actions.
- **Input**: Recommendation ID, decision (`APPROVE` or `REJECT`), operator reason.
- **Processing**: Creates or updates `ApprovalRequest` records. Marks high-impact recommendations (`DELETE_CANDIDATE` or size > 50 GB) with `is_high_impact = True`.
- **Output**: `ApprovalOutSchema` objects and updated recommendation statuses.
- **Safety**: Prevents execution of recommendations that have not been approved by a human operator.

---

## 10. Execution Engine Module (`ApprovalExecutionService`)
- **Purpose**: Executes approved storage tier migrations after passing pre-execution safety gates.
- **Input**: Recommendation ID, Organization ID.
- **Processing**: Evaluates safety gate (re-verifies legal holds, retention policies, access freshness, and object existence). Calls `ConnectorFactory` to execute provider-side migration.
- **Output**: `ExecutionResult` and new `MigrationEvent` record.
- **Safety**: Re-evaluates safety checks at execution time to catch stale recommendations. Simulated execution (`DELETE_SIMULATION_SUCCESS`) for delete candidates.

---

## 11. Rollback Engine Module
- **Purpose**: Reverts completed storage tier migrations to their original storage class.
- **Input**: Migration Event ID, Organization ID, rollback reason.
- **Processing**: Retrieves `MigrationEvent`, calls connector to restore `source_storage_class`, updates `StorageObject.storage_class`, reverses realized savings ledger entry, and creates `RollbackEvent`.
- **Output**: `RollbackResult` with restored storage class and status `SUCCESS`.
- **Safety**: Idempotent rollback prevention; cannot roll back an already-restored migration.

---

## 12. Savings Ledger Module (`SavingsLedgerService`)
- **Purpose**: Maintains a financial ledger tracking potential, approved, and realized monthly savings over time.
- **Input**: Migration events, rollback events, recommendation state changes.
- **Processing**: Adds realized savings on migration execution and subtracts savings on migration rollback.
- **Output**: `SavingsLedger` historical records and dashboard summaries.
- **Safety**: Precise floating-point rounding preventing financial rounding drift.

---

## 13. Synthetic Benchmark Framework Module (`IndustryDatasetGenerator`)
- **Purpose**: Benchmarks lifecycle optimization quality, cost reduction, safety preservation, and retrieval risk against synthetic dev environment datasets.
- **Input**: Benchmark parameters (number of dev environments, short-lived environment counts, seed).
- **Processing**: Simulates lifecycle distributions, evaluates recommendations against ground truth, and calculates accuracy metrics.
- **Output**: Benchmark metric reports (Precision, Recall, Cost Reduction Ratio, Safety Rate).
- **Safety**: 100% synthetic data generation with zero real user data.

---

## 14. Control-Plane Dashboard Module
- **Purpose**: React single-page application rendering storage overview, system health, breakdown charts, and approval queues.
- **Input**: Dashboard API summary endpoints (`GET /api/v1/organizations/{id}/dashboard`).
- **Processing**: Formats storage bytes to human-readable GB/TB, renders storage class breakdown bars, displays storage provider badges (`DEMO STORAGE` vs `AWS S3`), and manages approval queues.
- **Output**: Interactive visual dashboard interface.
- **Safety**: Read-only rendering with clear safety banners.

---

## 15. Audit Logging Module (`AuditLog`)
- **Purpose**: Records immutable, structured audit log events for all system actions.
- **Input**: Action name, resource type, resource ID, outcome code, metadata payload.
- **Processing**: Inserts timestamped `AuditLog` records into PostgreSQL.
- **Output**: Auditable event logs queryable via API or SQL.
- **Safety**: Secret keys and sensitive credentials are sanitized before logging.

---

## 16. Observability & Configuration Module (`AppConfig`)
- **Purpose**: Manages application settings, CORS policies, security headers, correlation IDs, and health check endpoints.
- **Input**: Environment variables (`APP_ENV`, `STORAGE_PROVIDER`, `CORS_ALLOWED_ORIGINS`).
- **Processing**: Intercepts HTTP requests, attaches `X-Request-ID` correlation header, injects security headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`), and exposes `/health/liveness` and `/health/readiness`.
- **Output**: Configured FastAPI application instance and health status JSON payloads.
- **Safety**: Sanitizes exception responses to prevent internal stack trace or secret exposure.
