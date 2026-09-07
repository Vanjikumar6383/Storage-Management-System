# Provider Capabilities & Capability Matrix Specification

## Overview
The **Provider Capabilities Abstraction** ([backend/app/connectors/capabilities.py](file:///d:/tools%20docx/projects/Storage%20management%201/backend/app/connectors/capabilities.py)) decouples business logic, recommendation generation, and lifecycle execution from cloud-provider specifics.

> [!IMPORTANT]
> **Provider Support Notice**: A cloud provider is **NOT** considered supported until a real connector implementation and its integration tests exist. `LOCAL_S3_COMPATIBLE` and `AWS_S3` are currently supported execution providers. Unimplemented cloud adapters (Azure Blob, GCS) explicitly fail safely.

---

## 1. Provider Capabilities Schema (`ProviderCapabilities`)

| Field | Type | Description |
|---|---|---|
| `provider` | `str` | Storage provider identifier |
| `supports_list_objects` | `bool` | Supports discovery of object metadata with pagination |
| `supports_get_metadata` | `bool` | Supports HEAD metadata retrieval |
| `supports_get_storage_class` | `bool` | Supports inspection of current storage tier/class |
| `supports_in_place_tiering` | `bool` | Supports changing storage class without copying object payload |
| `supports_copy_based_migration` | `bool` | Supports migration via CopyObject with storage class header |
| `supports_storage_class_migration` | `bool` | Supports zero-download lifecycle storage class migration |
| `supports_rollback` | `bool` | Supports restoring object back to original storage class |
| `supports_archive_restore` | `bool` | Requires asynchronous restore request before reading archived payload |
| `supports_immediate_archive_read` | `bool` | Supports immediate byte read from archive storage class |
| `supports_pagination` | `bool` | Supports continuation-token based object listing |
| `native_storage_classes` | `List[str]` | Supported provider-native storage tier names |

---

## 2. Provider Capability Matrix

| Capability / Feature | `LOCAL_S3_COMPATIBLE` | `AWS_S3` | `AZURE_BLOB` | `GOOGLE_CLOUD_STORAGE` |
|---|---|---|---|---|
| **In-Place Tiering** | ❌ False | ❌ False | ✅ True (`set_standard_blob_tier`) | ✅ True (`rewrite` / `patch`) |
| **Copy-Based Migration** | ✅ True | ✅ True (`CopyObject`) | ❌ False | ❌ False |
| **Lifecycle Migration** | ✅ True | ✅ True | ✅ True | ✅ True |
| **Rollback Capability** | ✅ True | ✅ True | ✅ True | ✅ True |
| **Archive Restore Req** | ❌ False | ✅ True (`RestoreObject`) | ✅ True (`Blob Rehydrate`) | ❌ False |
| **Immediate Archive Read** | ✅ True | ❌ False | ❌ False | ✅ True (High retrieval fee) |
| **Supported Status** | **SUPPORTED** | **SUPPORTED** | *Planned (Fail-safe)* | *Planned (Fail-safe)* |

---

## 3. Storage Class Mapping Matrix (`StorageClassMapper`)

The system normalizes all provider-native tiers into three domain storage classes: `STANDARD`, `INFREQUENT_ACCESS`, and `ARCHIVE`.

| Provider | Native Tier | Normalized Class | Reverse Mapping (`from_normalized`) | Lossy Notes |
|---|---|---|---|---|
| **AWS S3** | `STANDARD` | `STANDARD` | `STANDARD` | Baseline standard storage |
| **AWS S3** | `STANDARD_IA` | `INFREQUENT_ACCESS` | `STANDARD_IA` | Standard Infrequent Access |
| **AWS S3** | `ONEZONE_IA` | `INFREQUENT_ACCESS` | `STANDARD_IA` | Lacks multi-AZ durability |
| **AWS S3** | `GLACIER_IR` | `ARCHIVE` | `GLACIER` | Glacier Instant Retrieval |
| **AWS S3** | `GLACIER` | `ARCHIVE` | `GLACIER` | Flexible Glacier Archive |
| **AWS S3** | `DEEP_ARCHIVE` | `ARCHIVE` | `GLACIER` | Lowest cost deep archive |
| **AWS S3** | `INTELLIGENT_TIERING` | `STANDARD` | `STANDARD` | Auto-tiers internally; mapped to STANDARD baseline |
| **Azure Blob** | `Hot` | `STANDARD` | `Hot` | Azure Hot tier |
| **Azure Blob** | `Cool` | `INFREQUENT_ACCESS` | `Cool` | Azure Cool tier (30-day min) |
| **Azure Blob** | `Cold` | `INFREQUENT_ACCESS` | `Cool` | Azure Cold tier (90-day min) |
| **Azure Blob** | `Archive` | `ARCHIVE` | `Archive` | Azure Archive tier |
| **Google Cloud** | `STANDARD` | `STANDARD` | `STANDARD` | GCS Standard tier |
| **Google Cloud** | `NEARLINE` | `INFREQUENT_ACCESS` | `NEARLINE` | GCS Nearline tier (30-day min) |
| **Google Cloud** | `COLDLINE` | `INFREQUENT_ACCESS` | `NEARLINE` | GCS Coldline tier (90-day min) |
| **Google Cloud** | `ARCHIVE` | `ARCHIVE` | `ARCHIVE` | GCS Archive tier |
