# Storage Lifecycle Optimizer — Requirements Specification Document

> **Document Version**: 1.0.0  
> **Status**: APPROVED & VALIDATED  
> **Project Scope**: Multi-Tenant Cloud Storage Lifecycle Optimization, Compliance Invariants, Legacy Coexistence & Safe Rollback Control Plane  

---

## 1. Executive Summary & Operational Scenario

### 1.1 The Operational Challenge
A modern enterprise software company operates **hundreds of short-lived development environments** (e.g., ephemeral CI/CD pipelines, feature-branch test sandboxes, QA testing clusters, and staging environments). These environments produce massive quantities of object storage data—including container images, build logs, database snapshots, package caches, test reports, and ML training checkpoints.

### 1.2 The Root Cause
1. **Manual Tier Selection**: Storage classes are selected manually by individual developers and DevOps engineers. In over 70% of cases, developers simply default to high-cost `STANDARD` / `HOT` storage tiers.
2. **Abandoned Ephemeral Storage**: When ephemeral development environments are destroyed or merged, the underlying storage objects are rarely tagged, relocated, or deleted. 
3. **Data Accumulation & Cost Sprawl**: Massive storage volumes remain indefinitely in top-tier storage at $0.023/GB/month, leading to compounding cloud waste.
4. **Compliance & Deletion Risk**: Manual ad-hoc cleanup or blind cron-job deletions create severe risks: accidental destruction of data under regulatory audit, violation of active legal holds, or premature deletion before statutory retention expiry.

### 1.3 System Mission
The **Storage Lifecycle Optimizer** provides an automated, explainable, policy-driven control plane that:
- Automatically analyzes object age, access frequency, current storage class, retention rules, and restore telemetry.
- Delivers mathematically explainable lifecycle recommendations.
- Strictly protects compliance through absolute legal hold and retention precedence.
- Requires explicit human operator confirmation for high-impact actions (e.g., `DELETE`, `ARCHIVE`) while capturing mandatory override reasons.
- Operates non-destructively alongside legacy workflows (coexistence mode).
- Guarantees instant single-click rollback for any executed tier transition.
- **Strictly avoids collecting personal data** that is not essential to the solution (Zero-PII guarantee).

---

## 2. Core Architectural Principles & Privacy Guarantee

### 2.1 Privacy by Design & Zero-PII Invariant
- **No Unnecessary Personal Data**: The platform strictly prohibits storing or collecting employee names, personal email addresses, phone numbers, home addresses, IP addresses, or file contents.
- **Opaque Identifiers**: All resources are tracked using system-generated opaque identifiers (`org_xxxx`, `env_xxxx`, `obj_xxxx`).
- **Telemetry Only**: The system processes operational storage metadata only:
  - Object size (bytes/MB)
  - Object age (days since creation)
  - Access count telemetry (last 30d, 90d)
  - Days since last access
  - Historical restore events (last 90d)
  - Storage class (`HOT`, `COOL`, `COLD`, `ARCHIVE`)
  - Retention duration and active legal hold flags
- **Payload Safety**: Object file contents are **NEVER downloaded, stored, read, or inspected**.

### 2.2 Realistic Infrastructure Assumptions
- The solution does **not assume unlimited data, compute, or cloud budget**.
- Operates locally and in lightweight containers using PostgreSQL 16 and Python FastAPI with local S3 simulation (`LocalS3Connector`) or AWS S3 (`AWSS3Connector`).
- Storage tier transitions are executed using provider-side zero-download copy operations, eliminating data egress and compute buffering overhead.

---

## 3. Functional Requirements (FR)

| ID | Category | Requirement Description | Verification Method |
| :--- | :--- | :--- | :--- |
| **FR-01** | Multi-Tenancy | The system must strictly isolate tenant organizations. Every storage connection, environment, storage location, object, and recommendation must be foreign-key bound to `organization_id`. Cross-tenant queries are blocked. | Automated Pytest Unit Tests (`test_database.py`, `test_tenant_isolation`) |
| **FR-02** | Telemetry Ingestion | Ingest operational telemetry including object age, 30d access count, 90d access count, recency of access, and 90d restore events. Ingestion must be idempotent. | Telemetry Tests (`test_telemetry.py`) |
| **FR-03** | Explainable Engine | Generate explainable lifecycle recommendations (`KEEP`, `MOVE_TO_INFREQUENT_ACCESS`, `ARCHIVE`, `DELETE_CANDIDATE`, `HOLD`). Each recommendation must include human-readable rationale, structured JSON evidence, rule ID, and estimated monthly savings. | Recommendation Engine Tests (`test_recommendation_engine.py`) |
| **FR-04** | Legal Hold Invariant | An active legal hold (`status = 'ACTIVE'`) strictly overrides all deletion, tier demotion, and cleanup recommendations. Output must always be `HOLD`. | Edge Case 1 & Policy Tests (`test_edge_and_failure_cases.py`) |
| **FR-05** | Retention Hierarchy | Enforce deterministic retention policy precedence: `OBJECT_OVERRIDE` > `STORAGE_LOCATION` > `ENVIRONMENT` > `ORGANIZATION_DEFAULT`. Strictest retention duration wins in case of conflict. | Edge Case 3 & Precedence Tests (`test_policy_engine.py`) |
| **FR-06** | Retrieval Safeguard | Prevent archival demotion or promote cold objects to warm tiers if repeated restore events (`restore_events_90d > 0`) or active access occurs, preventing excessive per-GB retrieval surcharges. | Edge Case 2 Tests (`test_edge_and_failure_cases.py`) |
| **FR-07** | Human Approval Gate | All high-impact actions (`ARCHIVE`, `DELETE_CANDIDATE`) must enter a `PENDING` approval queue. An action cannot be executed without explicit operator confirmation (`APPROVE` / `REJECT`). | Approval Workflow Tests (`test_approval_execution.py`) |
| **FR-08** | Override Reason Capture | When approving or overriding a recommendation, the operator's decision reason must be captured and permanently stored in the audit record. | Approval Workflow Tests (`test_approval_execution.py`) |
| **FR-09** | Zero-Download Tiering | Tier transitions must be executed provider-side (e.g. S3 CopyObject with updated storage class) without pulling byte payloads into memory or incurring egress fees. | AWS S3 Connector Tests (`test_aws_s3_connector.py`) |
| **FR-10** | Single-Click Rollback | Any executed migration must support instant single-click rollback. Restores original storage class, updates status to `ROLLED_BACK`, logs audit event, and adjusts savings ledger. | Rollback Demo (`run_legacy_coexistence_and_rollback_demo.py`) |
| **FR-11** | Zero-Delete Dry Run | Recommendations of type `DELETE_CANDIDATE` run in `SIMULATION_ONLY` mode. Physical object deletion is simulated safely (`DELETE_SIMULATION_SUCCESS`) without payload loss. | Production Readiness Tests (`test_production_readiness.py`) |
| **FR-12** | Immutable Audit Trail | Every system action (telemetry sync, recommendation generation, approval decision, migration execution, rollback) must be recorded in `audit_logs` with timestamps, actor role, and outcome. | Audit Log Tests (`test_approval_execution.py`) |
| **FR-13** | Cost Snapshots | Record baseline storage volume vs. optimized volume and calculate monthly savings using verifiable per-GB cloud pricing rates. | Cost Engine Tests (`test_cost_engine.py`) |
| **FR-14** | Legacy Coexistence | Operate alongside legacy unmanaged workflows in non-destructive shadow monitoring mode without interrupting ongoing development jobs. | Coexistence Demo (`run_legacy_coexistence_and_rollback_demo.py`) |
| **FR-15** | Stakeholder Signoff | Provide an interactive validation dashboard with persona acceptance scorecards (FinOps, DevOps, Compliance, CTO) and feedback submission. | Stakeholder API & UI (`/api/v1/validation`) |

---

## 4. Non-Functional Requirements (NFR)

- **NFR-01 (Security & Secret Sanitization)**: Cloud credentials, secret keys, and passwords must never be stored in plain text, written to application logs, or exposed via API responses. All errors pass through centralized sanitization masks.
- **NFR-02 (Performance & Indexing)**: Database queries must utilize composite indexes on `(organization_id, environment_id)`, `(organization_id, storage_location_id)`, `(organization_id, last_accessed_at)`, and `(organization_id, storage_class)`. Telemetry queries complete in $< 50\text{ms}$.
- **NFR-03 (Fault Tolerance & Safe Failure)**: In the event of network disconnection or storage provider API errors (`503 SlowDown`, `403 Forbidden`), transactions must roll back cleanly. The object state remains unaltered, and a sanitized failure event is audited.
- **NFR-04 (Zero Data Lock-in)**: Storage abstractions interface through `BaseStorageConnector`, decoupling application logic from AWS S3, Azure Blob, Google Cloud Storage, or local S3-compatible systems.
- **NFR-05 (Auditing & Compliance)**: Audit trail records are tamper-evident, append-only, and queryable by organization ID and time window.

---

## 5. Precedence Hierarchy & Safety Invariants

```
                        [ Object Evaluated ]
                                 │
                                 ▼
                     Active Legal Hold Exists? ──(YES)──► [ HOLD ] (Strict Regulatory Block)
                                 │
                                (NO)
                                 ▼
                    Restore Risk / Thrashing? ──(YES)──► [ HOLD / KEEP WARM ] (Prevent Fees)
                                 │
                                (NO)
                                 ▼
                      Retention Status Check
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
          [ Retention Active ]        [ Retention Expired ]
                   │                           │
                   ▼                           ▼
          Block Deletion (KEEP)         0 Access in 180d?
                   │                           │
                   ▼                   ┌───────┴───────┐
          Eligible for Tiering         ▼               ▼
          (Infrequent / Archive)     (YES)            (NO)
                                       │               │
                                       ▼               ▼
                           [ DELETE_CANDIDATE ]     [ TIER ]
                           (High-Impact Gate)
```

---

## 6. Verification & Traceability Matrix

| Requirement | Implementation Artifact | Automated Test / Demo | Status |
| :--- | :--- | :--- | :--- |
| **Scenario: Short-Lived Dev Envs** | `backend/app/models/storage.py` (`Environment`) | `generate_realistic_dataset.py` (500 Envs) | **VERIFIED** |
| **Privacy (Zero PII)** | `import random.py`, `Data/storage_lifecycle_dataset_cleaned.csv` | Code Audit & CSV Schema Validation | **VERIFIED** |
| **Explainable Recommendations** | `backend/app/services/recommendation_engine.py` | `test_recommendation_engine.py` (15 Tests) | **VERIFIED** |
| **Legal Hold Controls** | `backend/app/services/policy_engine.py` | `test_policy_engine.py` (15 Tests) | **VERIFIED** |
| **Human Confirmation & Overrides** | `backend/app/services/approval_execution.py` | `test_approval_execution.py` (12 Tests) | **VERIFIED** |
| **Legacy Coexistence & Rollback** | `backend/scripts/run_legacy_coexistence_and_rollback_demo.py` | CLI Demo Script (Exit 0) | **VERIFIED** |
| **At Least 3 Edge/Failure Cases** | `backend/app/services/edge_cases_service.py` | `run_edge_cases_demo.py` (5/5 Passed) | **VERIFIED** |
| **Measurable Cost Experiment** | `backend/app/services/industry_experiment.py` | `test_industry_experiment.py` (12 Tests) | **VERIFIED** |
| **Stakeholder Validation Console** | `frontend/src/pages/StakeholderValidation.tsx`, `validation.py` | Vitest Suite & REST API Tests | **VERIFIED** |
| **Limitations Report** | `docs/limitations.md` | Formal Technical Analysis Report | **VERIFIED** |
