# Storage Class Migration Rollback Mechanism

## Overview
Every successful storage migration (`migration_events.status == 'SUCCESS'`) maintains an immutable rollback lineage. The **Rollback Engine** enables operators to safely return an object from its target storage class back to its original source storage class.

---

## 1. Rollback Rules & Prerequisites

1. **Successful Migration Required**: Rollback is permitted **only** for migrations with `status == 'SUCCESS'`.
2. **Known Source Destination**: Rollback targets `migration_events.source_storage_class`. Rollback to an unknown destination is strictly blocked.
3. **Idempotency**: If a migration has already been rolled back (`rollback_status == 'ROLLED_BACK'`), subsequent rollback requests return `status = "ALREADY_EXECUTED"`.
4. **Tenant Isolation**: Rollback requests verify `migration.organization_id == organization_id`.

---

## 2. Rollback Execution Workflow

```
1. Request Rollback (POST /api/v1/migrations/{migration_id}/rollback)
2. Create RollbackEvent (status = 'PENDING')
3. Invoke Provider-Side Copy (LocalS3Connector: target_class = source_storage_class)
4. Update StorageObject (storage_class = source_storage_class)
5. Update MigrationEvent (rollback_status = 'ROLLED_BACK')
6. Update RollbackEvent (status = 'SUCCESS', completed_at = now())
7. Record Audit Log (action = 'ROLLBACK_SUCCEEDED')
```

---

## 3. Rollback API Endpoints

- `POST /api/v1/migrations/{migration_id}/rollback`
