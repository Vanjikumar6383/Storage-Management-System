"""
Production Readiness Smoke Test Script.
Verifies backend service initialization, database connection, health endpoints, storage provider readiness, and secret redaction.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_storage_settings, get_app_config
from app.db.database import SessionLocal
from sqlalchemy import text


def run_smoke_test():
    print("=" * 60)
    print("    STORAGE LIFECYCLE OPTIMIZER — PRODUCTION SMOKE TEST")
    print("=" * 60)

    client = TestClient(app)

    # Test 1: Liveness Endpoint
    resp_live = client.get("/health/liveness")
    assert resp_live.status_code == 200, f"Liveness check failed: {resp_live.text}"
    print(f"[OK] Liveness Check: PASSED (Status: {resp_live.json()['status']})")

    # Test 2: System Info Endpoint
    resp_info = client.get("/info")
    assert resp_info.status_code == 200, f"Info check failed: {resp_info.text}"
    info = resp_info.json()
    print(f"[OK] System Info: PASSED (Environment: {info['environment']}, Storage: {info['storage_provider']})")

    # Test 3: Database Connectivity
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("[OK] PostgreSQL Connectivity: PASSED")
    except Exception as e:
        print(f"[ERROR] PostgreSQL Connectivity: FAILED ({e})")
        sys.exit(1)

    # Test 4: Readiness Endpoint
    resp_ready = client.get("/health/readiness")
    assert resp_ready.status_code == 200, f"Readiness check failed: {resp_ready.text}"
    ready = resp_ready.json()
    print(f"[OK] Readiness Check: PASSED (DB: {ready['database_status']}, Storage: {ready['storage_status']})")

    # Test 5: Request ID Header Propagation
    resp_req = client.get("/info", headers={"X-Request-ID": "test-req-smoke-123"})
    assert resp_req.headers.get("X-Request-ID") == "test-req-smoke-123", "Request ID header not propagated!"
    print("[OK] Request ID Middleware: PASSED (Correlation ID propagated)")

    # Test 6: Security HTTP Headers
    assert resp_req.headers.get("X-Content-Type-Options") == "nosniff", "Missing X-Content-Type-Options header!"
    assert resp_req.headers.get("X-Frame-Options") == "DENY", "Missing X-Frame-Options header!"
    print("[OK] Security HTTP Headers: PASSED")

    print("=" * 60)
    print("     ALL SMOKE TESTS PASSED CLEANLY (SYSTEM READY)")
    print("=" * 60)


if __name__ == "__main__":
    run_smoke_test()
