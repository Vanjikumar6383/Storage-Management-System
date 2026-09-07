# Credential Security & Redaction Specification

## Overview
The **Credential Security Model** ([backend/app/connectors/credentials.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/connectors/credentials.py)) governs credential resolution, tenant isolation, and secret redaction across the Storage Lifecycle Optimizer platform.

---

## 1. Zero Secret Leakage Policy

1. **No Insecure Fallback Credentials**: Hardcoded credentials in production-style fallbacks are prohibited. Connectors fail explicitly if required credentials are missing.
2. **Centralized Error Redaction**: `CredentialResolver.sanitize_text` sanitizes error messages, stack traces, and exception strings before writing to logs, `ConnectionSyncLog.error_summary`, or audit records.
3. **Config Sanitization**: `CredentialResolver.redact_config` redacts sensitive fields (`secret_key`, `password`, `token`, `api_key`, `connection_string`) from JSON config dictionaries prior to logging or returning API responses.
4. **Zero Payload Ingestion**: File contents, byte streams, and object bodies are never read, ingested, or stored.

---

## 2. Credential Resolution Workflow (`CredentialResolver`)

```
+-------------------------------------------------------------------------+
|                  StorageConnection Record (PostgreSQL)                  |
|  - provider (StorageProviderEnum)                                       |
|  - credential_reference ("env:TEST_MINIO_CREDENTIAL_REF")               |
|  - config (JSONB: endpoint_url, region, etc.)                           |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                        CredentialResolver.resolve                       |
+-------------------------------------------------------------------------+
                                    |
                                    +---> LOCAL_S3_COMPATIBLE: Parses endpoint, access_key, secret_key
                                    |
                                    +---> Unsupported Cloud Provider: Validates metadata structure,
                                          raises UnsupportedProviderError before SDK initialization
```

---

## 3. Redaction Patterns & Sanitization Mechanics

The sanitization utility automatically strips:
- Explicit connector secret values (`self.secret_key`, `self.access_key`).
- Key-value patterns: `secret_key=...`, `aws_secret_access_key=...`, `password=...`, `token=...`, `api_key=...`.
- HTTP Authorization headers: `Bearer eyJ...` $\rightarrow$ `Bearer [REDACTED_TOKEN]`.
