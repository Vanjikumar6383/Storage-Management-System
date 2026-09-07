# Storage Configuration & Security Guide

This document outlines the storage configuration system for the Storage Lifecycle Optimizer, explaining the default **Demo Storage Mode** and optional **Real AWS S3 Mode**.

---

## 1. Overview & Provider Modes

The system operates under a provider-independent architecture managed via `ConnectorFactory`. Two modes are supported:

| Mode | Provider Code | Description | Cloud Credentials Required? |
|---|---|---|---|
| **Demo Storage Mode (Default)** | `LOCAL_S3_COMPATIBLE` | Self-contained demo environment operating on local storage / simulated objects. | **NO** — Zero AWS account or internet connection required. |
| **Production AWS S3 Mode** | `AWS_S3` | Real production integration connecting directly to AWS S3 buckets using `AWSS3Connector`. | **YES** — Valid AWS IAM credentials and bucket configuration required. |

---

## 2. Default Demo Storage Mode

By default, the application runs entirely in **Demo Storage Mode**:

```ini
STORAGE_PROVIDER=LOCAL_S3_COMPATIBLE
S3_ENDPOINT_URL=http://localhost:9000
S3_REGION=us-east-1
S3_ACCESS_KEY=
S3_SECRET_KEY=
```

### Guarantees in Demo Mode:
- **No Cloud Setup Needed**: Runs out of the box for college evaluations, local testing, and demonstration.
- **Complete Feature Availability**: Ingests metadata, calculates costs, generates lifecycle recommendations, executes tier migrations/rollbacks in PostgreSQL, and renders control-plane dashboard metrics.
- **Safety Banner**: Displays `"Demo Storage Mode — lifecycle actions operate on demo storage only."`

---

## 3. Switching to Production AWS S3 Mode

To connect to a real AWS S3 bucket:

1. Edit your `.env` file (never commit real credentials to git):
   ```ini
   STORAGE_PROVIDER=AWS_S3
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_SESSION_TOKEN=... (optional, if using temporary credentials)
   AWS_REGION=ap-south-1
   AWS_S3_BUCKET=my-production-storage-bucket
   ```
2. Restart the backend service.
3. The dashboard will show `STORAGE: AWS S3` and the safety banner: `"Production Cloud Mode — lifecycle actions can modify real AWS S3 objects."`

### Switching Back to Demo Mode:
Simply set `STORAGE_PROVIDER=LOCAL_S3_COMPATIBLE` in `.env` and restart.

---

## 4. Strict Non-Fallback Guarantee

If `STORAGE_PROVIDER=AWS_S3` is selected but required AWS credentials or bucket configuration are missing or incomplete:
- The system **FAILS SAFELY** with a human-readable error: `"AWS S3 provider selected but AWS credentials/configuration are missing. Please configure: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_S3_BUCKET"`.
- It will **NEVER** silently fall back to `LocalS3Connector` or demo storage.
- Credentials and secret keys are **NEVER** printed in error messages, tracebacks, or logs.

---

## 5. AWS IAM Least-Privilege Specification

When connecting real AWS credentials, follow the principle of least privilege. **Do NOT use AWS Root Account keys.**

### Minimal Required IAM Policy JSON

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "StorageDiscoveryAndMetadata",
      "Effect": "Allow",
      "Action": [
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:HeadObject",
        "s3:GetObjectAttributes"
      ],
      "Resource": "*"
    },
    {
      "Sid": "StorageClassTieringAndRollback",
      "Effect": "Allow",
      "Action": [
        "s3:CopyObject",
        "s3:GetObjectTagging",
        "s3:PutObjectTagging"
      ],
      "Resource": "arn:aws:s3:::my-production-storage-bucket/*"
    }
  ]
}
```

> [!WARNING]
> Do NOT grant `s3:DeleteObject`. Physical deletion remains strictly disabled in dry-run/simulation safety mode across all storage operations.

---

## 6. Troubleshooting

- **Error: `AWS S3 provider selected but AWS credentials/configuration are missing.`**
  - Check `.env` and ensure `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `AWS_S3_BUCKET` are exported.
- **Error: `InvalidAccessKeyId` / `SignatureDoesNotMatch`**
  - Verify AWS IAM access key and secret key validity and system clock synchronization.
- **Dashboard shows `STORAGE: DEMO STORAGE` unexpectedly**
  - Confirm `STORAGE_PROVIDER=LOCAL_S3_COMPATIBLE` in `.env`.
