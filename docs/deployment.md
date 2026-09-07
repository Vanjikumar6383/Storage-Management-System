# Production & Demo Deployment Guide

This guide details how to deploy the Storage Lifecycle Optimizer in both **College Demo Mode** (default) and **Production AWS Mode**.

---

## Deployment Architecture Modes

```
A. COLLEGE DEMO MODE (DEFAULT - ZERO CLOUD DEPENDENCIES)
   React Control Plane (Vite / Nginx) -> FastAPI Backend -> PostgreSQL DB -> Local S3 / Demo Storage

B. PRODUCTION AWS MODE (OPTIONAL REAL CLOUD INTEGRATION)
   React Control Plane (Vite / Nginx) -> FastAPI Backend -> PostgreSQL DB -> AWSS3Connector -> AWS S3
```

---

## Mode A: Deployment via Docker Compose (College Demo Mode)

### Prerequisites
- Docker & Docker Compose installed.

### Step-by-Step Instructions

1. **Clone the Repository**:
   ```bash
   git clone <repo-url>
   cd "Storage management 1"
   ```

2. **Verify `.env` Configuration**:
   ```ini
   STORAGE_PROVIDER=LOCAL_S3_COMPATIBLE
   APP_ENV=DEMO
   ```

3. **Start Containers**:
   ```bash
   docker compose up -d
   ```

4. **Verify Deployment**:
   - Backend Control Plane: `http://localhost:8000/health/readiness`
   - Interactive Swagger API Documentation: `http://localhost:8000/docs`
   - React Dashboard UI: `http://localhost:5173`

---

## Mode B: Optional AWS Production Deployment

1. **Configure Environment Variables in `.env`**:
   ```ini
   STORAGE_PROVIDER=AWS_S3
   APP_ENV=PRODUCTION
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=ap-south-1
   AWS_S3_BUCKET=my-production-storage-bucket
   ```

2. **Restart Services**:
   ```bash
   docker compose restart backend
   ```

3. **Verify AWS Integration**:
   - Check `http://localhost:8000/health/readiness`. The status badge on the dashboard will display `STORAGE: AWS S3`.
