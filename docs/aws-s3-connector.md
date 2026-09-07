# Production AWS S3 Storage Connector Specification

## Overview
The **Production AWS S3 Connector** ([backend/app/connectors/aws_s3_connector.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/connectors/aws_s3_connector.py)) provides native cloud integration with Amazon Web Services Simple Storage Service (AWS S3) via the `boto3` SDK.

It extends `BaseStorageConnector` and integrates directly with:
- `ConnectorFactory` for provider resolution (`AWS_S3` $\rightarrow$ `AWSS3Connector`).
- `CredentialResolver` for AWS credential extraction, session token support, and centralized error redacting.
- `StorageClassMapper` for native-to-normalized class mapping (`STANDARD`, `STANDARD_IA`, `ONEZONE_IA`, `GLACIER_IR`, `GLACIER`, `DEEP_ARCHIVE`, `INTELLIGENT_TIERING`).
- `ProviderCapabilities` (`supports_copy_based_migration=True`, `supports_archive_restore=True`, `supports_immediate_archive_read=False`).

---

## 1. Zero-Download Guarantee

The connector strictly obeys the **Zero-Download Guarantee**:
- **Metadata Discovery**: Uses `list_objects_v2` (paginated with `ContinuationToken`) and `head_object` calls.
- **Lifecycle Migrations**: Uses provider-side S3 `CopyObject` with `MetadataDirective="REPLACE"` and `StorageClass` parameter.
- **Forbidden API Calls**: `GetObject` and byte stream readers are **never** invoked.

---

## 2. Authentication & Credential Resolution

`CredentialResolver.resolve(connection)` parses credentials from `StorageConnection.config` or `credential_reference`:
- `access_key` / `aws_access_key_id`
- `secret_key` / `aws_secret_access_key`
- `session_token` / `aws_session_token` (for temporary IAM assume-role credentials)
- `region` (defaults to `us-east-1`)
- `endpoint_url` (optional custom S3 endpoint override)

---

## 3. Storage Class Normalization

Native AWS S3 storage classes translate bidirectionally:

| AWS Native Class | Normalized Domain Class | Rollback Class |
|---|---|---|
| `STANDARD` | `STANDARD` | `STANDARD` |
| `STANDARD_IA` | `INFREQUENT_ACCESS` | `STANDARD_IA` |
| `ONEZONE_IA` | `INFREQUENT_ACCESS` | `STANDARD_IA` |
| `GLACIER_IR` | `ARCHIVE` | `GLACIER` |
| `GLACIER` | `ARCHIVE` | `GLACIER` |
| `DEEP_ARCHIVE` | `ARCHIVE` | `GLACIER` |
| `INTELLIGENT_TIERING` | `STANDARD` | `STANDARD` |

---

## 4. Secret Sanitization & Auditability

All exceptions caught during AWS S3 interactions pass through `CredentialResolver.sanitize_text`:
- Access key IDs (`AKIA...`), secret access keys, and session tokens are stripped from stack traces, logs, and database exception records.
- All tier migrations emit immutable `MigrationEvent` and `AuditLog` records prior to and following execution.
