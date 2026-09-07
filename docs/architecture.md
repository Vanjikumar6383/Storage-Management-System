# System Architecture & Component Design

The **Storage Lifecycle Optimizer** is built on a multi-tenant, explainable control-plane architecture separating control logic from storage execution.

```
                    React Control Plane (Vite / Nginx)
                                   │
                                   ▼
                      FastAPI Control Plane API
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

## Component Responsibilities

1. **FastAPI Control Plane API**: Serves SaaS endpoints with multi-tenant isolation, request correlation IDs (`X-Request-ID`), security HTTP headers, and CORS control.
2. **Recommendation Engine**: Evaluates object metadata, access patterns, and policy constraints to generate explainable lifecycle actions (`MOVE_TO_INFREQUENT_ACCESS`, `ARCHIVE`, `DELETE_CANDIDATE`, `KEEP`, `HOLD`).
3. **Policy & Legal Hold Engine**: Enforces organization/location retention policies and active legal holds.
4. **Approval & Execution Service**: Evaluates pre-execution safety gates (legal hold checks, access event freshness, object existence), manages approval requests, executes migrations via `ConnectorFactory`, and handles rollbacks.
5. **Cost & Savings Engine**: Calculates storage costs, potential savings, approved savings, and realized savings ledgers using provider-independent pricing specifications.
6. **ConnectorFactory & Connectors**: Routes operations to `LocalS3Connector` (Demo Mode) or `AWSS3Connector` (AWS Mode). Enforces a zero-download guarantee.
7. **Audit Logging & Observability**: Logs all lifecycle decisions, approvals, migrations, and rollbacks with sanitized parameters.
