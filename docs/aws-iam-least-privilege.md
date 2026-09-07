# AWS IAM Least-Privilege Policy Specification

## Overview
The **Storage Lifecycle Optimizer** platform interacts with Amazon S3 strictly through metadata discovery APIs and gated provider-side `CopyObject` storage class migrations.

This document details the minimal IAM permissions required for secure production operation.

> [!IMPORTANT]
> - **Zero Payload Download**: `s3:GetObject` is **NOT** required for metadata discovery, access tracking, recommendations, or tiering migrations.
> - **Physical Delete Disabled**: `s3:DeleteObject` is **NOT** required for normal application workflows while physical deletion remains disabled in dry-run/simulation safety mode.

---

## 1. Minimal IAM Policy JSON

Attach the following policy to the IAM Role or User utilized by `CredentialResolver`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StorageOptimizerAccountDiscovery",
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::*"
    },
    {
      "Sid": "StorageOptimizerBucketMetadataDiscovery",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::*"
    },
    {
      "Sid": "StorageOptimizerObjectMetadataAndMigration",
      "Effect": "Allow",
      "Action": [
        "s3:GetObjectAttributes",
        "s3:GetObjectTagging",
        "s3:PutObjectTagging",
        "s3:CopyObject"
      ],
      "Resource": "arn:aws:s3:::*/*"
    }
  ]
}
```

---

## 2. Permission Breakdown by Workflow Phase

| Phase | Required AWS Actions | Purpose | Resource Scope |
|---|---|---|---|
| **Bucket Discovery** | `s3:ListAllMyBuckets`, `s3:GetBucketLocation` | Discovers available S3 buckets for the connection | `arn:aws:s3:::*` |
| **Metadata Ingestion** | `s3:ListBucket`, `s3:GetObjectAttributes` | Paginated listing via `ListObjectsV2` and `HeadObject` metadata retrieval | `arn:aws:s3:::*`, `arn:aws:s3:::*/*` |
| **Tier Migration** | `s3:CopyObject` | Zero-download provider-side storage class transition (`MetadataDirective="REPLACE"`) | `arn:aws:s3:::*/*` |
| **Rollback** | `s3:CopyObject` | Zero-download restoration back to original storage class | `arn:aws:s3:::*/*` |
| **Physical Delete** | *DISABLED (Not Required)* | `s3:DeleteObject` is explicitly excluded | None |

---

## 3. Recommended IAM AssumeRole Setup for Multi-Tenant / Multi-Account AWS

For enterprise environments with multi-account AWS architectures:
1. Create an IAM Role named `StorageLifecycleOptimizerRole` in each target AWS account.
2. Grant the above least-privilege policy to `StorageLifecycleOptimizerRole`.
3. Configure trust relationship allowing the Storage Optimizer control-plane IAM principal to invoke `sts:AssumeRole`.
4. Register the `credential_reference` in `StorageConnection` as `arn:aws:iam::<ACCOUNT_ID>:role/StorageLifecycleOptimizerRole`.
