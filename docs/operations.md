# Operations & Maintenance Guide

This runbook documents operational procedures for managing, backing up, restoring, monitoring, and maintaining the Storage Lifecycle Optimizer platform.

---

## 1. Database Operations

### PostgreSQL Backup
To create a complete PostgreSQL database dump:

```bash
docker exec -t storage_optimizer_db pg_dump -U postgres storage_optimizer_dev > backup_$(date +%Y%m%d_%H%M%S).sql
```

### PostgreSQL Restore
To restore from a database dump:

```bash
docker exec -i storage_optimizer_db psql -U postgres storage_optimizer_dev < backup_20260826_100000.sql
```

---

## 2. Environment Configuration & Restart

The application is controlled via `.env` environment variables.

### Restart Backend Service
```bash
docker compose restart backend
```

### Apply Database Migrations (Alembic)
```bash
docker compose exec backend alembic upgrade head
```

---

## 3. Log Inspection & Monitoring

Structured logs are printed to stdout with timestamp, log level, logger name, and correlation `request_id`.

### View Real-Time Logs
```bash
docker compose logs -f backend
```

### Inspect Audit Trail Logs
All lifecycle decisions, approvals, migrations, and rollbacks generate structured `AuditLog` records queryable via API or SQL:

```sql
SELECT timestamp, organization_id, action, resource_type, outcome 
FROM audit_logs 
ORDER BY timestamp DESC 
LIMIT 20;
```

---

## 4. Health Checks

- **Liveness Endpoint**: `GET /health/liveness` (Confirms Python process is running)
- **Readiness Endpoint**: `GET /health/readiness` (Confirms PostgreSQL connectivity and storage configuration validity)
- **System Info**: `GET /info` (Returns environment name, version, and storage provider)

---

## 5. Emergency Shutdown & Demo Reset

### Emergency Stop
To safely stop all containers without losing persistent database data:

```bash
docker compose down
```

### Demo Data Reset
To reset database tables to clean initial seed data:

```bash
docker compose down -v
docker compose up -d
```
