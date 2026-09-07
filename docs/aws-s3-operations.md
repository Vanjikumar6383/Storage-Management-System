# AWS S3 Operational Runbook & Troubleshooting Guide

## Overview
This runbook provides step-by-step procedures for operating, configuring, monitoring, and troubleshooting the AWS S3 storage connector within the Storage Lifecycle Optimizer platform.

---

## 1. Connecting an AWS S3 Account

To connect an AWS S3 account to an organization:

1. **Prerequisite**: Ensure the target AWS IAM Role or User has the minimum permissions defined in [docs/aws-iam-least-privilege.md](file:///d:/tools%20docx/projects/Storage%20management%201/docs/aws-iam-least-privilege.md).
2. **REST API Registration**:
   `POST /api/v1/connections`
   ```json
   {
     "name": "AWS Production Analytics",
     "provider": "AWS_S3",
     "credential_reference": "env:AWS_PROD_CREDENTIALS",
     "config": {
       "region": "us-west-2",
       "access_key": "AKIA...",
       "secret_key": "...",
       "session_token": null
     }
   }
   ```
3. **Connection Testing**:
   `POST /api/v1/connections/{connection_id}/test`
   Verifies S3 connectivity via `AWSS3Connector.test_connection()`. Returns HTTP 200 with `{ "status": "CONNECTED" }` or HTTP 400 with sanitized error text.

---

## 2. Triggering & Monitoring Metadata Sync Jobs

1. **Trigger Sync Job**:
   `POST /api/v1/connections/{connection_id}/sync`
2. **Sync Execution Pipeline**:
   - `ConnectorFactory` instantiates `AWSS3Connector`.
   - `AWSS3Connector.list_storage_locations()` discovers S3 buckets.
   - `AWSS3Connector.list_objects()` executes `ListObjectsV2` pagination.
   - `MetadataIngestionService` upserts `StorageLocation` and `StorageObject` records in PostgreSQL.
3. **Check Sync Logs**:
   `GET /api/v1/connections/{connection_id}/logs`
   - Review `status` (`SUCCESS` or `FAILED`).
   - Confirm `objects_scanned`, `objects_updated`, `bytes_scanned`.
   - `error_summary` is guaranteed to be secret-redacted.

---

## 3. Storage-Class Migration Execution & Rollback

1. **Human Approval Workflow**:
   - Recommendations must be explicitly approved (`status = APPROVED`).
2. **Pre-Execution Safety Gate**:
   - Evaluates 11 safety criteria (tenant verification, policy check, active legal hold check, retention check, fresh access check).
3. **Execution**:
   - Executes `AWSS3Connector.copy_object_storage_class(bucket, key, target_class)`.
   - On success, updates `StorageObject.storage_class` in PostgreSQL, creates `MigrationEvent`, and records realized savings in `SavingsLedgerService`.
4. **Rollback**:
   - `POST /api/v1/approvals/execute-recommendation/{recommendation_id}/rollback`
   - Executes reverse `CopyObject` migration back to original storage class.
   - Updates PostgreSQL and records counterfactual reversal in savings ledger.

---

## 4. Troubleshooting Common Failures

| Symptom | Root Cause | Resolution |
|---|---|---|
| `Unable to locate credentials` | Missing `access_key` / `secret_key` in connection config or environment | Verify AWS credentials in `StorageConnection.config` or environment variables |
| `AccessDenied` / `403 Forbidden` | Missing IAM permissions for `s3:ListBucket` or `s3:CopyObject` | Ensure target IAM policy attaches permissions from [docs/aws-iam-least-privilege.md](file:///d:/tools%20docx/projects/Storage%20management%201/docs/aws-iam-least-privilege.md) |
| `NoSuchBucket` / `404 Not Found` | Bucket deleted or region mismatch | Verify bucket name and `region` parameter in connection config |
| `STALE_RECOMMENDATION` | Object read event recorded after recommendation generation | Re-evaluate recommendation engine to produce updated recommendation |
| `BLOCKED (Legal Hold)` | Active legal hold attached to object or location | Release legal hold in Governance tab before approving migration |
