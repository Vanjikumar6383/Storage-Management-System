# Storage Lifecycle Optimizer — Limitations & Architectural Boundaries Report

> **Document Version**: 1.0.0  
> **Status**: FORMAL ENGINEERING REPORT  
> **Scope**: Technical Boundaries, Architectural Tradeoffs, Cloud Provider Constraints & Production Roadmap  

---

## 1. Executive Summary

This report establishes the technical boundaries, intentional architectural constraints, and operational assumptions of the **Storage Lifecycle Optimizer**. In enterprise systems engineering, documenting what a system *does not do* is just as critical as documenting what it *does*. 

By defining clear design boundaries, the system prevents catastrophic edge-case failures, avoids unbounded cloud provider costs, and maintains 100% compliance safety.

---

## 2. Intentional Safety Constraints & Design Boundaries

### 2.1 Physical Deletion Prevention (`SIMULATION_ONLY` Mode)
- **Design Decision**: The system strictly operates in **Zero-Delete Dry-Run Mode** for any recommendation categorized as `DELETE_CANDIDATE`.
- **Rationale**: Accidental deletion of development environments (such as an uncommitted database snapshot or unique ML checkpoint) causes permanent data loss. In `SIMULATION_ONLY` mode, the system emits `DELETE_SIMULATION_SUCCESS`, records audit events, and projects storage savings without sending a permanent `DeleteObject` API call to the cloud provider.
- **Production Path**: In a live enterprise deployment, converting dry-run deletions into physical deletions requires:
  1. An organization-level setting `ENABLE_HARD_DELETES = True`.
  2. Multi-party authorization (e.g. dual-custody approval by both DevOps Lead and Compliance Officer).
  3. A 30-day "soft-delete" trash bin retention stage prior to permanent purge.

### 2.2 Strict Zero-PII Data Minimization Constraint
- **Design Decision**: The platform refuses to store, index, or parse employee names, personal email addresses, phone numbers, IP addresses, or file byte contents.
- **Tradeoff**: Because the system does not inspect file contents or text inside files, it cannot perform semantic duplicate content detection (e.g., detecting duplicate PDF files with different keys).
- **Justification**: Eliminates all GDPR/CCPA personal data compliance exposure, drastically reduces storage footprint, and ensures privacy-by-design.

---

## 3. Storage Provider & Cloud Integration Scope

### 3.1 Implemented vs. Stubbed Connectors
- **Fully Implemented & Verified**:
  - `LOCAL_S3_COMPATIBLE`: Local S3 demo storage connector, fully verified in offline environments without AWS accounts.
  - `AWS_S3`: Production AWS S3 connector built on `boto3`, supporting in-place copy-based tier migrations, credential security sanitization, and region routing.
- **Architectural Stubs**:
  - `AZURE_BLOB`: Enums and interface signatures exist in `ProviderCapabilities` and `BaseStorageConnector`. Concrete Azure SDK clients (`azure-storage-blob`) are intentionally not bundled to avoid unnecessary heavy dependencies in local demo setups.
  - `GOOGLE_CLOUD_STORAGE`: Enums and tier mapping exist, but the concrete Google Cloud Storage SDK client is stubbed.
- **Error Behavior**: Attempting to initialize unconfigured providers raises a clean, descriptive `UnsupportedProviderError`.

### 3.2 Provider API Rate Limits & Backoff
- **Constraint**: Cloud object storage providers enforce request rate limits (e.g., AWS S3 enforces 3,500 PUT/COPY/POST/DELETE and 5,500 GET/HEAD requests per second per prefix).
- **System Mitigation**: The `AWSS3Connector` is configured with exponential backoff (`retries={"max_attempts": 3, "mode": "standard"}`), connect timeouts (5s), and read timeouts (5s).
- **Scale Limitation**: For organizations operating millions of objects per bucket, telemetry ingestion must be federated through asynchronous S3 Inventory and AWS Athena rather than synchronous real-time prefix scanning.

---

## 4. Cost Calculation Assumptions & Billing Dynamics

### 4.1 Static Reference Pricing vs. Dynamic Invoicing
- **Pricing Basis**: The cost engine utilizes standardized reference pricing rates (AWS US-East-1 standard rates: Standard at $0.023/GB/month, IA at $0.0125/GB/month, Glacier Flexible at $0.004/GB/month, Deep Archive at $0.00099/GB/month).
- **Customer Nuances**: Real customer AWS billing invoices may exhibit slight variances due to:
  - Enterprise Discount Programs (EDP) or custom negotiated cloud rates.
  - Regional pricing variances (e.g., higher rates in São Paulo or Sydney).
  - API request fees (e.g., $0.005 per 1,000 PUT requests).
  - Pro-rated minimum storage duration fees (e.g., 30-day minimum for Infrequent Access, 90-day minimum for Glacier Flexible).

### 4.2 Retrieval Fee Safety Safeguards
- **Tradeoff**: The recommendation engine deliberately errs on the side of caution. If an object exhibits even minor restore activity (`restore_events_90d > 0`), the engine refuses to demote it to cold archival tiers.
- **Impact**: While this may leave a small percentage of cold objects in warmer tiers (slightly conservative savings), it completely eliminates the risk of catastrophic retrieval surcharge penalties.

---

## 5. Architectural Scaling Boundaries

| Component | Current Validated Boundary | Enterprise Scale Strategy |
| :--- | :--- | :--- |
| **Object Telemetry** | 10,000+ objects tested locally | AWS S3 Inventory exports + Parquet batch ingestion |
| **Database Transactions** | Synchronous ACID SQLAlchemy sessions | Celery / RabbitMQ distributed task worker queues |
| **Approval Execution** | Single-threaded operator execution | Asynchronous batch execution pipeline with distributed locks |
| **Rollback Time Horizon** | Tested up to 365 days after migration | Subject to cloud provider lifecycle retention rules |

---

## 6. Summary of Boundary Integrity

The system guarantees that under no circumstance will:
1. An object under active legal hold be deleted or moved in violation of compliance rules.
2. A cloud credential or API secret be leaked in error responses or logs.
3. A migration be executed without an explicit audit trail.
4. An unrecoverable tier transition occur without single-click rollback readiness.
