# Storage Lifecycle Optimizer

> **Enterprise-Grade Multi-Tenant Storage Lifecycle Optimizer & Cost Reduction Control Plane**  
> An explainable, policy-driven storage governance platform that analyzes storage objects, evaluates access telemetry, enforces retention and legal holds, and executes safe tier migrations with human approvals and full rollbacks.

---

## 🌟 1. Project Overview

The **Storage Lifecycle Optimizer** automates enterprise cloud storage cost reduction while protecting data compliance and preventing accidental deletion. It evaluates storage objects across multi-tenant environments, calculates potential monthly savings, provides explainable lifecycle recommendations, requires human operator approval for tiering actions, and executes zero-download migrations with complete rollback capabilities.

---

## 💡 2. Problem Statement

Modern enterprise software environments generate hundreds of short-lived development buckets and millions of unmonitored storage objects:
- **Continuous Cost Growth**: Unused files remain indefinitely in high-cost tier storage (`STANDARD` at $0.023/GB/month).
- **Manual Overhead**: Manual identification of cold or stale objects across multi-tenant locations is error-prone.
- **Compliance & Deletion Risks**: Blindly deleting objects creates severe compliance violations, legal hold breaches, and data loss risks.

---

## 🛡️ 3. Proposed Solution

The **Storage Lifecycle Optimizer** provides a zero-risk control plane:
1. **Explainable Recommendations**: Generates human-readable rationale (`MOVE_TO_INFREQUENT_ACCESS`, `ARCHIVE`, `DELETE_CANDIDATE`, `KEEP`, `HOLD`) backed by verifiable evidence structures.
2. **Policy & Legal Hold Safety**: Evaluates retention rules and legal hold overrides to prevent invalid migrations or compliance breaches.
3. **Human Approval Workflow**: Requires explicit operator review (`PENDING` $\rightarrow$ `APPROVED` $\rightarrow$ `EXECUTED`).
4. **Safe Tier Migration & Rollback**: Executes provider-side zero-download migrations (`LocalS3Connector` or `AWSS3Connector`) and supports instant single-click rollback.
5. **Zero-Delete Safety Guarantee**: Recommendations of type `DELETE_CANDIDATE` return `DELETE_SIMULATION_SUCCESS` in dry-run mode without deleting physical object payloads.

---

## 🏗️ 4. System Architecture

```
                       React Control Plane (Vite / Nginx)
                                      │
                                      ▼
                         FastAPI REST API Server
                                      │
                 ┌────────────────────┼────────────────────┐
                 ▼                    ▼                    ▼
           Recommendation       Policy & Legal        Cost & Savings
              Engine              Hold Engine             Engine
                 │                    │                    │
                 └─────────┬──────────┴──────────┬─────────┘
                           ▼                     ▼
                 ApprovalExecutionService    Audit Trail
                           │
                           ▼
                    ConnectorFactory
                           │
                 ┌─────────┴─────────┐
                 ▼                   ▼
          LocalS3Connector     AWSS3Connector
                 │                   │
                 ▼                   ▼
           Demo Storage           AWS S3
                 │
                 ▼
            PostgreSQL DB
```

---

## 🛠️ 5. Technology Stack

- **Frontend**: React 18, TypeScript 5, Vite 5, TailwindCSS, Lucide Icons
- **Backend**: Python 3.14, FastAPI, Uvicorn, SQLAlchemy 2, Pydantic V2, Alembic
- **Database**: PostgreSQL 16
- **Storage Connectors**: `LocalS3Connector` (Demo Storage), `AWSS3Connector` (AWS S3)
- **Testing**: Pytest (Backend 121 tests), Vitest (Frontend 7 tests)
- **Containerization**: Docker & Docker Compose

---

## ⚡ 6. Quick Start (College Demo Mode — Default)

No AWS account, AWS credentials, or internet connection required.

### 1. One-Command Demo Environment Setup
```bash
python backend/scripts/start_demo.py
```

### 2. Start Backend API Server
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 3. Start React Dashboard UI
```bash
cd frontend
npm run dev
```

### 4. Access Interactive Interfaces
- **React Control Panel**: `http://localhost:5173`
- **FastAPI Interactive Docs**: `http://localhost:8000/docs`
- **Readiness Health Check**: `http://localhost:8000/health/readiness`

---

## 🧪 7. Verification & Demo Scripts

### 🌟 Run 100% Master Project Verification (10 Checks)
```bash
python backend/scripts/run_complete_project_verification.py
```

### ⚡ Run 5 Operational Edge & Failure Scenarios
```bash
python backend/scripts/run_edge_cases_demo.py
```

### 🔄 Run Legacy Coexistence & Rollback Demonstration
```bash
python backend/scripts/run_legacy_coexistence_and_rollback_demo.py
```

### 📊 Generate Realistic Multi-Tenant Benchmark Dataset (Zero PII)
```bash
python backend/scripts/generate_realistic_dataset.py
```

### Run Automated End-to-End Demo
```bash
python backend/scripts/run_e2e_demo.py
```

### Run Production Readiness Smoke Test
```bash
python backend/scripts/run_smoke_test.py
```

### Run Full Test Suites
```bash
# Backend Pytest Suite (122 tests including edge cases)
cd backend && pytest -v

# Frontend Vitest Suite (7 tests)
cd frontend && npm test

# Frontend Production Build (Vite + TypeScript)
cd frontend && npm run build
```

---

## ☁️ 8. Optional AWS S3 Configuration

To connect real AWS S3 storage:

1. Update `.env`:
   ```ini
   STORAGE_PROVIDER=AWS_S3
   APP_ENV=PRODUCTION
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=ap-south-1
   AWS_S3_BUCKET=my-production-bucket
   ```
2. Restart backend server:
   ```bash
   docker compose restart backend
   ```

> [!WARNING]
> AWS credentials are backend-only secrets. Never commit `.env` or put AWS keys in frontend code.

---

## 🐳 9. Docker Deployment

Launch PostgreSQL, FastAPI backend, and Nginx frontend in containerized DEMO mode:

```bash
docker compose up -d
```

---

---

## 🗄️ 10. Database Schema & Entity Relationship Specification

The platform utilizes a strictly partitioned multi-tenant relational schema on PostgreSQL 16 managed through Alembic and SQLAlchemy 2:

```
┌──────────────────┐       ┌────────────────────────┐
│  organizations   │───────│  storage_connections   │
└────────┬─────────┘       └───────────┬────────────┘
         │                             │
         │                             ▼
         │                 ┌────────────────────────┐
         ├─────────────────│   storage_locations    │
         │                 └───────────┬────────────┘
         │                             │
         │                             ▼
         │                 ┌────────────────────────┐
         ├─────────────────│    storage_objects     │
         │                 └───────────┬────────────┘
         │                             │
         │          ┌──────────────────┼──────────────────┐
         │          ▼                  ▼                  ▼
         │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
         ├───│  telemetry   │   │  retention   │   │ legal_holds  │
         │   └──────────────┘   └──────────────┘   └──────────────┘
         │                             │
         │                             ▼
         │                 ┌────────────────────────┐
         ├─────────────────│    recommendations     │
         │                 └───────────┬────────────┘
         │                             │
         │                             ▼
         │                 ┌────────────────────────┐
         ├─────────────────│   approval_requests    │
         │                 └───────────┬────────────┘
         │                             │
         │                             ▼
         │                 ┌────────────────────────┐
         ├─────────────────│    migration_events    │
         │                 └───────────┬────────────┘
         │                             │
         │                             ▼
         │                 ┌────────────────────────┐
         ├─────────────────│    rollback_events     │
         │                 └────────────────────────┘
         │
         ├─────────────────┌────────────────────────┐
         │                 │       audit_logs       │ (Immutable Ledger)
         │                 └────────────────────────┘
         │
         └─────────────────┌────────────────────────┐
                           │     savings_ledger     │ (FinOps Cost Tracking)
                           └────────────────────────┘
```

### Core Relational Entities
1. **`organizations`**: Multi-tenant isolation boundary (`id`, `name`, `slug`, `created_at`).
2. **`storage_connections`**: Provider credentials and connection metadata (`provider_type`, `auth_type`, `is_active`).
3. **`storage_locations`**: S3 buckets / regional endpoints mapped to environments (`bucket_name`, `region`, `environment_tier`).
4. **`storage_objects`**: Ingested object inventory (`object_key`, `size_bytes`, `storage_class`, `last_modified`, `etag`).
5. **`legal_holds`**: Immutable regulatory hold blockers (`hold_identifier`, `reason`, `status`, `created_at`).
6. **`retention_policies`**: Hierarchical retention rules (`min_retention_days`, `target_tier`, `precedence_rank`).
7. **`recommendations`**: Explainable 5-state lifecycle actions (`type`, `projected_monthly_savings`, `roi_ratio`, `evidence_json`).
8. **`approval_requests`**: Human confirmation gate records (`status`, `operator_id`, `override_reason`, `decided_at`).
9. **`migration_events`**: Provider-side copy execution logs (`source_tier`, `target_tier`, `execution_latency_ms`).
10. **`rollback_events`**: Reverse migration records ensuring instant reversion (`original_tier`, `restoration_status`).
11. **`audit_logs`**: Append-only compliance log (`actor`, `action`, `target_urn`, `sanitized_payload`, `timestamp`).
12. **`savings_ledger`**: Cumulative financial savings tracking (`organization_id`, `realized_monthly_savings_usd`, `period`).

---

## 🌐 11. Complete REST API Endpoint Catalog

All endpoints are versioned under `/api/v1` with OpenAPI 3.0 interactive documentation at `http://localhost:8000/docs`:

| Module | HTTP Method | Endpoint Path | Function & Security Boundary |
| :--- | :---: | :--- | :--- |
| **Storage Connections** | `GET` | `/api/v1/storage-connections` | List all active storage provider connectors |
| | `POST` | `/api/v1/storage-connections` | Register provider credentials (credentials auto-masked) |
| | `GET` | `/api/v1/storage-connections/{id}/health` | Probe provider health and API responsiveness |
| **Telemetry Ingestion** | `POST` | `/api/v1/telemetry/sync` | Trigger non-destructive metadata sync sweep |
| | `GET` | `/api/v1/telemetry/objects` | Query object inventory with multi-criteria filters |
| | `GET` | `/api/v1/telemetry/summary` | Aggregate storage distribution across tiers |
| **Policy Engine** | `GET` | `/api/v1/policies` | Retrieve organization, environment & location policies |
| | `POST` | `/api/v1/policies` | Create hierarchical lifecycle rule with precedence rank |
| | `POST` | `/api/v1/policies/legal-holds` | Apply absolute legal hold blocker on object/prefix |
| | `DELETE` | `/api/v1/policies/legal-holds/{id}` | Release legal hold with mandatory compliance audit note |
| **Recommendations** | `POST` | `/api/v1/recommendations/evaluate` | Execute 5-state decision engine with explainable evidence |
| | `GET` | `/api/v1/recommendations` | List pending recommendations with projected ROI |
| **Approvals & Rollback** | `POST` | `/api/v1/approvals/{id}/decide` | Approve/Reject with mandatory operator override reason |
| | `POST` | `/api/v1/approvals/batch-execute` | Execute zero-download copy migration for approved items |
| | `POST` | `/api/v1/approvals/{id}/rollback` | Trigger instant single-click reverse tier migration (< 60s) |
| **Coexistence & CI/CD** | `POST` | `/api/v1/environments/{id}/teardown` | Idempotent ephemeral environment decommission webhook |
| **Stakeholder Validation**| `GET` | `/api/v1/validation/matrix` | Cross-persona compliance & verification matrix |
| | `GET` | `/api/v1/validation/metrics` | Real-time accuracy, savings, and safety invariant scores |
| **Cost & FinOps** | `GET` | `/api/v1/costs/savings-summary` | Realized vs. projected monthly financial savings |
| | `GET` | `/api/v1/costs/tier-distribution` | Financial distribution by cloud storage tier |

---

## 🔬 12. Granular Technical Documentation: Unit Testing & Error Boundaries

### 12.1 Unit & Integration Testing Architecture
The test suite consists of **124+ automated backend tests** spanning 22 specialized test modules:

```
backend/tests/
├── test_approval_execution.py          # Operator workflows, approvals, and rollback execution
├── test_aws_s3_connector.py             # Live AWS boto3 connector, CopyObject, and backoff
├── test_aws_s3_production_validation.py # Live cloud validation and error code handling
├── test_connector_capabilities.py      # Provider feature matrix & tier compatibility
├── test_connector_factory.py           # Factory instantiation & fallback routing
├── test_connectors.py                  # Storage connector interfaces & method signatures
├── test_cost_engine.py                 # Multi-tier cost calculation and savings projection
├── test_credentials.py                 # Credential resolution & secret masking
├── test_dashboard_api.py               # Control plane telemetry aggregation
├── test_database.py                    # Multi-tenant isolation & transaction rollback
├── test_edge_and_failure_cases.py      # Transient network, rate limits & conflict resolution
├── test_health.py                      # Liveness, readiness, and connectivity probes
├── test_industry_experiment.py         # 10,000-object benchmark experiment verification
├── test_ingestion.py                   # Non-destructive metadata list operations
├── test_organization_registration.py   # Multi-tenancy creation & role assignment
├── test_policy_engine.py               # Deterministic 4-level precedence evaluation
├── test_production_readiness.py        # End-to-end smoke tests and health checks
├── test_recommendation_engine.py       # 5-state classifier, restore thrashing guards
├── test_storage_class_mapping.py       # Cross-provider tier normalization
├── test_storage_configuration.py       # Pydantic v2 environment settings validation
├── test_sync_api.py                    # Sync endpoint idempotency & error handling
└── test_telemetry.py                   # Telemetry parsing, sliding windows & recency
```

### 12.2 Layered Error Boundaries & Fault-Tolerant Mitigations

```
                                  INCOMING OPERATION
                                          │
    ┌─────────────────────────────────────┴─────────────────────────────────────┐
    ▼                                                                           ▼
[ REST API / GATEWAY BOUNDARY ]                                 [ CONCURRENCY & LOCK BOUNDARY ]
• Global Exception Handlers                                     • Distributed Mutex Locks per Prefix
• Masked Error Response Payloads                                • Atomic PostgreSQL DB Transactions
• Zero Stack Traces / Secrets Exposed                           • Eliminates Race Conditions & Split-Brains
    │                                                                           │
    └─────────────────────────────────────┬─────────────────────────────────────┘
                                          │
    ┌─────────────────────────────────────┴─────────────────────────────────────┐
    ▼                                                                           ▼
[ CLOUD PROVIDER THROTTLING BOUNDARY ]                          [ PARTIAL BATCH FAILURE BOUNDARY ]
• Exponential Backoff with Full Jitter                          • Per-Item Fault Isolation in Batches
• Intercepts AWS 503 SlowDown & HTTP 429                        • Failed Keys Quarantined to Dead-Letter
• Max 5 Retries before Quarantine                               • 4,997/5,000 Batch Continues Unaffected
    │                                                                           │
    └─────────────────────────────────────┬─────────────────────────────────────┘
                                          │
                                          ▼
                         [ SAFETY INVARIANT ENFORCEMENT ]
                         • Priority 1 Legal Hold Override Check
                         • Restore-Thrashing Guard (restore_90d > 0)
                         • Simulation-Only Deletions (Zero Purges)
```

1. **API Boundary**: Standardized exception filters translate internal exceptions into clean RFC 7807 error models, ensuring zero database connection strings or AWS secret keys are ever reflected to clients.
2. **Concurrency Boundary**: Synchronous locking prevents simultaneous migrations on overlapping bucket prefixes.
3. **Throttling Boundary**: Exponential backoff with full jitter dynamically throttles request rates to stay within provider burst allowances.
4. **Partial Batch Boundary**: Multi-object batch migrations process items with independent error boundaries; a failure on object $k$ does not invalidate or abort objects $1 \dots k-1$ or $k+1 \dots n$.

---

## 📚 13. Complete Documentation Index

- [`docs/master-project-report.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/master-project-report.md) — Comprehensive Master Project Report (< 8,000 chars)
- [`docs/requirements-specification.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/requirements-specification.md) — Formal Requirements Specification, Zero-PII Invariant & Precedence Hierarchy
- [`docs/edge-and-failure-cases.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/edge-and-failure-cases.md) — 5 Operational Edge & Failure Scenarios with Proofs & Retrieval Safeguards
- [`docs/legacy-coexistence-and-rollback.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/legacy-coexistence-and-rollback.md) — Legacy Workflow Coexistence (Shadow Mode) & Instant Rollback Demonstration
- [`docs/cost-reduction-and-error-analysis.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/cost-reduction-and-error-analysis.md) — Baseline vs Target vs Measured Cost, Confusion Matrix & Error Analysis
- [`docs/stakeholder-validation-report.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/stakeholder-validation-report.md) — Formal Stakeholder Validation Signoff Report (FinOps, DevOps, Compliance, CTO)
- [`docs/limitations.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/limitations.md) — System Boundaries, Cloud Provider Constraints & Scale Roadmap
- [`docs/college-project-report.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/college-project-report.md) — 31-Section BE/BTech Academic Project Report
- [`docs/database-design.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/database-design.md) — Database Schema, ER Diagram & Mappings
- [`docs/viva-and-demo.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/viva-and-demo.md) — Demo Scripts & 40 Academic Viva Q&As

