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

### Run Automated End-to-End Demo
```bash
python backend/scripts/run_e2e_demo.py
```

### Run Production Readiness Smoke Test
```bash
python backend/scripts/run_smoke_test.py
```

### Run Final Release Verification Suite (10 Checks)
```bash
python backend/scripts/final_verify.py
```

### Run Full Test Suites
```bash
# Backend Pytest Suite (121 tests)
cd backend && pytest -v

# Frontend Vitest Suite (7 tests)
cd frontend && npm test

# Frontend Production Build
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

## 📚 10. Complete Documentation Index

- [`docs/college-project-report.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/college-project-report.md) — 31-Section BE/BTech Academic Project Report
- [`docs/modules.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/modules.md) — System Modules & Component Breakdown
- [`docs/database-design.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/database-design.md) — Database Schema, ER Diagram & Mappings
- [`docs/recommendation-algorithm.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/recommendation-algorithm.md) — Recommendation Rules & Decision Flow
- [`docs/viva-and-demo.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/viva-and-demo.md) — Demo Scripts & 40 Academic Viva Q&As
- [`docs/presentation-outline.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/presentation-outline.md) — 15-Slide Presentation Deck Structure
- [`docs/operations.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/operations.md) — Operational Runbook & Maintenance
- [`docs/deployment.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/deployment.md) — Production Deployment Guide
- [`docs/tech-stack.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/tech-stack.md) — Technology Stack & Licensing
- [`docs/limitations.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/limitations.md) — Scope & Design Boundaries
- [`docs/step-15-final-report.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/step-15-final-report.md) — Final Release Report
