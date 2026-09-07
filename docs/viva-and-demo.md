# Demonstration Guide & Viva Voce Q&A Reference

Walkthrough scripts for classroom evaluation and 40 academic viva questions with concise answers.

---

## 🎬 1. 5-Minute Classroom Demo Script

1. **Launch Environment (30 seconds)**:
   - Open terminal and run: `python backend/scripts/start_demo.py`
   - Point out: `"Environment is DEMO mode, zero AWS account or internet connection required."`

2. **Open Dashboard (1 minute)**:
   - Open browser at `http://localhost:5173`.
   - Point out **System Health Card**: Application: HEALTHY, Database: HEALTHY, Provider: DEMO STORAGE.
   - Point out **KPI Cards**: Total Storage Bytes, Total Objects, Potential Monthly Savings ($).

3. **Inspect Explainable Recommendation (1.5 minutes)**:
   - Scroll to **Pending Approvals Queue**.
   - Click on object `demo/DEMO_ARCHIVE_COLD.dat`.
   - Highlight:
     - Recommended Action: `ARCHIVE`
     - Reason String: `"Object age exceeds 180 days with zero recent access."`
     - Evidence metrics (Age=200d, Accesses=0).
     - Estimated Monthly Savings: `$0.95/month`.

4. **Approve, Execute & Rollback Migration (1.5 minutes)**:
   - Click **Approve**. Show status updates to `APPROVED`.
   - Click **Execute Migration**. Show storage class changes from `STANDARD` to `ARCHIVE` in real time.
   - Point out: `"Notice the Realized Savings Ledger updated."`
   - Click **Rollback Migration**. Show storage class restored from `ARCHIVE` to `STANDARD` instantly.

5. **Verify Legal Hold Safety (30 seconds)**:
   - Select object `demo/DEMO_LEGAL_HOLD.pdf`.
   - Point out Action is `HOLD` and execution is strictly blocked due to active legal hold.

---

## 🎬 2. 10-Minute Detailed Technical Demo Script

1. **Demo Launcher & Smoke Test (1 min)**: Run `python backend/scripts/start_demo.py`.
2. **Dashboard Overview & Health Observability (1.5 min)**: Explain multi-tenant architecture and storage provider badge (`DEMO STORAGE` vs `AWS S3`).
3. **Metadata & Telemetry Ingestion (1.5 min)**: Demonstrate `POST /api/v1/sync` syncing storage objects without payload inspection.
4. **Policy Engine & Legal Holds (1.5 min)**: Inspect retention schedules and legal hold overrides.
5. **Explainable Recommendation Engine (1.5 min)**: Show rule evaluation priorities and evidence JSON payloads.
6. **Approval & High-Impact Safety Gates (1 min)**: Demonstrate approval queue and high-impact flags on large objects or delete candidates.
7. **Zero-Download Migration & Rollback (1.5 min)**: Execute tiering migration and instant rollback reversal.
8. **Delete Candidate Simulation Safety Mode (30 sec)**: Demonstrate `DELETE_SIMULATION_SUCCESS` preserving physical payloads.

---

## ❓ 3. 40 Academic Viva Voce Questions & Answers

### Q1: What is the main objective of the Storage Lifecycle Optimizer?
**A**: To automate cloud storage cost reduction by analyzing object access patterns and moving inactive files to cheaper storage tiers while protecting compliance via legal holds, retention rules, human approvals, and rollback pipelines.

### Q2: Why is manual storage lifecycle management inadequate in modern software companies?
**A**: Short-lived development environments create millions of unmonitored objects. Manual inspection is non-scalable, error-prone, and risks accidental deletion of compliance-critical data.

### Q3: What is the difference between Hot, Cool, and Archive storage tiers?
**A**: Standard/Hot ($0.023/GB/mo) is for active data; Infrequent Access/Cool ($0.0125/GB/mo) is for data accessed once or twice a month; Archive/Glacier ($0.004/GB/mo) is for cold backup data with retrieval latency.

### Q4: Why does this project use PostgreSQL instead of a NoSQL database?
**A**: PostgreSQL provides ACID compliance, strong relational foreign key constraints across multi-tenant entities, transactional ledgers, and complex SQL indexing for audit logging.

### Q5: Why is FastAPI chosen for the backend API framework?
**A**: FastAPI offers high performance (built on Starlette/uvicorn), native asynchronous support, Pydantic data validation, and automatic OpenAPI interactive documentation.

### Q6: How does the application prevent AWS credentials from leaking?
**A**: AWS credentials exist only in backend environment variables (`.env`). The `ResolvedCredentials` class masks secret keys (`AKIA***`), and API responses redact credential fields.

### Q7: Does the system require an active AWS account for demonstration?
**A**: No. The default mode is `LOCAL_S3_COMPATIBLE` (Demo Storage), allowing full local demonstration without internet or cloud accounts.

### Q8: What happens if an AWS S3 connection is missing credentials when AWS mode is selected?
**A**: `ConnectorFactory` raises an explicit `AWSConfigurationError` and fails safely. It **never** silently falls back to local demo storage.

### Q9: What is a zero-download migration?
**A**: Storage class tiering (`STANDARD` $\rightarrow$ `GLACIER`) executes via cloud provider copy/update APIs directly in object storage without transferring byte payloads across the network to the application server.

### Q10: How is physical payload deletion protected during demonstration?
**A**: Recommendations of type `DELETE_CANDIDATE` return status `DELETE_SIMULATION_SUCCESS` in dry-run mode, recording audit events without executing physical delete commands.

### Q11: What is explainability in the recommendation engine?
**A**: Every recommendation includes a human-readable reason string and a structured `RuleEvaluationResult` list detailing the exact metrics and rule priorities evaluated.

### Q12: How does a legal hold affect lifecycle recommendations?
**A**: An active legal hold overrides all other rules (Priority 1), forcing the action to `HOLD` and blocking tiering or deletion.

### Q13: What is the purpose of the Policy Engine?
**A**: To evaluate retention schedules and legal holds, resolving policy precedence (Object > Location > Organization) before recommendations or migrations execute.

### Q14: Why is human operator approval required before migration?
**A**: To maintain human-in-the-loop safety, preventing automated scripts from executing unexpected data movements on critical enterprise files.

### Q15: What is a High-Impact approval request?
**A**: Approval requests involving `DELETE_CANDIDATE` actions or files larger than 50 GB are flagged as high-impact to alert operators.

### Q16: How does the rollback pipeline work?
**A**: It retrieves the original `MigrationEvent`, calls the connector to restore `source_storage_class`, updates the database record, reverses realized savings ledger entries, and logs a rollback audit event.

### Q17: Is rollback idempotent?
**A**: Yes. Attempting to roll back an already-restored migration returns status `ALREADY_EXECUTED` without duplicate execution.

### Q18: What are the four states of the savings ledger?
**A**: Estimated Current Cost, Potential Monthly Savings, Approved Monthly Savings, and Realized Monthly Savings.

### Q19: How are unit costs defined in the cost estimation service?
**A**: Standardized pricing thresholds: $0.023/GB/mo (Standard), $0.0125/GB/mo (IA), $0.004/GB/mo (Archive), $0.00099/GB/mo (Deep Archive).

### Q20: What is retrieval risk penalty?
**A**: Archiving files that are frequently restored incurs cloud retrieval fees. The cost engine calculates estimated retrieval risk ($/GB) to prevent premature archival.

### Q21: What is the role of `ConnectorFactory`?
**A**: To encapsulate connector creation, resolving `LocalS3Connector` or `AWSS3Connector` dynamically based on tenant configuration.

### Q22: What is `NormalizedObjectMetadata`?
**A**: A provider-independent data structure standardizing object key, size, storage class, and last modified date across S3, Azure, and GCP.

### Q23: How does the system achieve multi-tenant isolation?
**A**: Every table contains `organization_id` foreign keys, and API endpoints enforce SQL tenant filtering.

### Q24: What correlation header is used for request tracking?
**A**: `X-Request-ID`. If omitted by the client, the middleware generates a unique `req-<hex>` correlation ID attached to all logs.

### Q25: What production security headers are injected by backend middleware?
**A**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.

### Q26: What health endpoints are exposed?
**A**: `/health/liveness` (process status) and `/health/readiness` (PostgreSQL connectivity and storage provider status).

### Q27: How does the React frontend communicate with the FastAPI backend?
**A**: Via RESTful JSON endpoints using standard `fetchJson` client wrappers with CORS support.

### Q28: What is Vite and why is it used for the frontend?
**A**: Vite is a modern frontend build tool offering fast Hot Module Replacement (HMR) and optimized rollup production bundles.

### Q29: What containerization technology is provided?
**A**: Docker container definitions (`Dockerfile`, `Dockerfile.frontend`) and `docker-compose.yml` linking Postgres, Backend, and Frontend.

### Q30: What is the purpose of the Synthetic Benchmark Framework?
**A**: To evaluate recommendation algorithms objectively against synthetic datasets representing hundreds of dev environments.

### Q31: What metrics does the benchmark framework measure?
**A**: Cost Reduction Ratio, Recommendation Precision & Recall, Safety Preservation Rate, and Retrieval Risk Overhead.

### Q32: What is the ground truth in the synthetic benchmark?
**A**: Pre-calculated optimal lifecycle states derived from synthetic environment generator specifications.

### Q33: How does the system handle pagination during object metadata sync?
**A**: Uses provider continuation tokens (e.g. AWS S3 `ContinuationToken`) to fetch inventory batches without exceeding memory limits.

### Q34: What is Alembic?
**A**: A lightweight database migration tool for SQLAlchemy used to manage database schema updates incrementally.

### Q35: How does the application handle unhandled exceptions in production?
**A**: Intercepts unhandled exceptions and returns sanitized JSON `{ "error": { "code": "INTERNAL_SERVER_ERROR", ... } }` without exposing stack traces.

### Q36: What is a legal hold release?
**A**: Updating a legal hold status to `RELEASED` with `released_at` timestamp, allowing subsequent lifecycle evaluation to proceed.

### Q37: Why are operational metadata requests (e.g., `HEAD`) excluded from access telemetry?
**A**: `HEAD` requests are administrative metadata reads. Including them as data access events would incorrectly mark cold files as active.

### Q38: How does the project document system limitations?
**A**: [`docs/limitations.md`](file:///d:/tools%20docx/projects/Storage%20management%201/docs/limitations.md) documents boundaries such as non-implemented Azure/GCP cloud SDK adapters and static pricing assumptions.

### Q39: What script verifies all 10 release checks automatically?
**A**: `python backend/scripts/final_verify.py`.

### Q40: What is the current status of the project?
**A**: **COLLEGE DEMO READY** — 100% verified across 121 backend unit tests, 7 frontend tests, Vite production build, CLI demo scripts, and security credential scans.
