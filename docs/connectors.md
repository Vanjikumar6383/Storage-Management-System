# Storage Connectors & Metadata Ingestion Specification

## Overview
The **Storage Connector & Metadata Ingestion Layer** discovers storage locations (buckets/containers) and object metadata from external storage environments and synchronizes them into PostgreSQL.

The entire control plane operates strictly on **object metadata** (`Key`, `Size`, `LastModified`, `StorageClass`, `ETag`). File contents and byte streams are never downloaded, stored, or inspected.

---

## 1. Connector Architecture

The system decouples core application logic from provider SDKs (AWS SDK / Boto3 / Azure SDK / GCP SDK) via a provider-independent connector interface:

```
+-------------------------------------------------------------------------+
|                         Storage Provider Layer                          |
|  [AWS S3]       [Azure Blob]       [Google Cloud]      [Local S3 / MinIO]
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                  BaseStorageConnector Interface (boto3)                 |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|           Normalized Data Transfer Models (Pydantic Schemas)            |
|       NormalizedStorageLocation  /  NormalizedObjectMetadata            |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                      MetadataIngestionService                           |
|                       (Idempotent PostgreSQL)                           |
+-------------------------------------------------------------------------+
```

---

## 2. Connector Interface (`BaseStorageConnector`)

The abstract base class ([backend/app/connectors/base.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/connectors/base.py)) defines standard provider-agnostic operations:

- `test_connection() -> bool`: Verifies endpoint connectivity and credential validity.
- `list_storage_locations() -> list[NormalizedStorageLocation]`: Discovers buckets/containers.
- `list_objects(location_name: str, cursor: Optional[str]) -> tuple[list[NormalizedObjectMetadata], Optional[str]]`: Discovers objects with pagination.
- `get_object_metadata(location_name: str, object_key: str) -> NormalizedObjectMetadata`: Fetches HEAD metadata for a single object.
- `get_storage_class(location_name, object_key) -> str`: Returns storage tier string.
- `get_object_size(location_name, object_key) -> int`: Returns byte count.
- `copy_object_storage_class(location_name: str, object_key: str, target_storage_class: str) -> bool`: Executes provider-side zero-download storage class migration.

---

## 3. Connector Factory (`ConnectorFactory`)

Implemented in [backend/app/connectors/factory.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/connectors/factory.py):

- **Provider Resolution**: Inspects `storage_connection.provider` (`StorageProviderEnum` or string) to resolve the appropriate `BaseStorageConnector`.
- **Currently Supported Providers**:
  - `LOCAL_S3_COMPATIBLE` $\rightarrow$ Instantiates `LocalS3Connector` using configured connection endpoint, access key, secret key, and region.
  - `AWS_S3` $\rightarrow$ Instantiates `AWSS3Connector` using AWS IAM credentials, region, and optional endpoint override.
- **Unsupported Cloud Providers**:
  - `AZURE_BLOB`, `GOOGLE_CLOUD_STORAGE` $\rightarrow$ Explicitly raise `UnsupportedProviderError`.
- **Explicit No-Fallback Safety**: The factory **never** silently falls back to `LocalS3Connector` when an unsupported provider is requested. Unimplemented cloud adapters fail safely with explicit error messages.
- **Application Integration**: Background sync jobs (`run_connection_sync`), lifecycle migration execution, and rollback routines acquire connectors strictly via `ConnectorFactory`.

---

## 4. Normalized Metadata Models

Provider-specific SDK objects are translated into standardized Pydantic domain models prior to leaving the connector layer:

```json
{
  "external_object_id": "s3://demo-analytics-bucket/logs/2026/app.log",
  "storage_location": "demo-analytics-bucket",
  "object_key": "logs/2026/app.log",
  "object_size_bytes": 10240,
  "storage_class": "STANDARD",
  "last_modified_at": "2026-08-17T05:00:00Z",
  "etag": "a1b2c3d4e5f6",
  "version_id": null,
  "content_type": "text/plain"
}
```

---

## 5. Local S3-Compatible Connector (`LocalS3Connector`)

- Implemented in [backend/app/connectors/s3_connector.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/connectors/s3_connector.py) using `boto3`.
- Configured via `storage_connection.config` or environment variables:
  - `S3_ENDPOINT_URL` (default: `http://localhost:9000`)
  - `S3_ACCESS_KEY` (default: `minioadmin`)
  - `S3_SECRET_KEY` (default: `minioadmin`)
  - `S3_REGION` (default: `us-east-1`)
- Employs `ListObjectsV2` continuation tokens for high-volume bucket pagination.
- Only executes `head_bucket`, `list_buckets`, `list_objects_v2`, `head_object`, `copy_object` calls.

---

## 6. Ingestion Process & Idempotency

Implemented in [backend/app/services/ingestion.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/services/ingestion.py):

1. **Storage Location Upsert**: Resolves location by `(storage_connection_id, name)`. Inserts if missing; updates region if modified.
2. **Object Metadata Upsert**: Resolves object by natural unique key `(storage_location_id, object_key)`:
   - **Insert**: If object key does not exist in PostgreSQL, inserts new `StorageObject` record (`discovered_at = now()`, `updated_at = now()`).
   - **Update**: If record exists but `object_size_bytes`, `storage_class`, or `last_modified_at` has changed, updates fields and sets `updated_at = now()`.
   - **Skip**: If record exists and metadata is unchanged, skips insertion to prevent duplicate data churn.

---

## 7. Error Handling & Security Model

- **Credential Redaction**: Error handling logic automatically redacts access/secret keys from exception logs and `ConnectionSyncLog.error_summary`.
- **Zero Content Access**: No object read streams (`GetObject` / `response['Body']`) are ever initiated.
- **Graceful Failure Tracking**: Sync job failures update `connection_sync_logs` table with `status = 'FAILED'` without breaking database state or leaking credentials.

---

## 8. Multi-Cloud Roadmap

- **AWS S3 Connector**: Extends `BaseStorageConnector` using IAM assume-role credentials and AWS STS.
- **Azure Blob Connector**: Extends `BaseStorageConnector` using Azure SDK for Python (`azure-storage-blob`). Maps Blob Tiers (`Hot`, `Cool`, `Cold`, `Archive`) to normalized storage classes.
- **Google Cloud Storage Connector**: Extends `BaseStorageConnector` using GCP Client Library (`google-cloud-storage`). Maps Storage Classes (`STANDARD`, `NEARLINE`, `COLDLINE`, `ARCHIVE`).
