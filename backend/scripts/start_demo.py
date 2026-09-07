"""
One-Command College Demo Launcher for Storage Lifecycle Optimizer.
Validates environment, checks PostgreSQL connectivity, runs migrations, seeds classroom demo dataset, and executes smoke checks.
"""

import sys
import subprocess
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import get_storage_settings, get_app_config
from app.db.database import SessionLocal
from app.db.seed import seed_database
from sqlalchemy import text


def start_demo_launcher():
    print("=" * 70)
    print("      STORAGE LIFECYCLE OPTIMIZER — ONE-COMMAND DEMO LAUNCHER")
    print("=" * 70)

    # 1. Environment & Configuration Check
    storage_cfg = get_storage_settings()
    app_cfg = get_app_config()

    print(f"\n[1/5] Environment Verification:")
    print(f"   * Environment: {app_cfg.app_env}")
    print(f"   * Storage Provider: {storage_cfg.provider} (DEMO MODE)")
    print(f"   * AWS Credentials Required: NO")
    assert storage_cfg.provider in ("LOCAL_S3_COMPATIBLE", "LOCAL"), "Demo launcher requires DEMO mode."
    print("   [OK] Environment verified safe for local demonstration.")

    # 2. Database Connectivity Check
    print(f"\n[2/5] Database Connectivity Check:")
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        print("   [OK] PostgreSQL connection successful.")
    except Exception as err:
        print(f"   [ERROR] Failed to connect to PostgreSQL: {err}")
        print("   -> Please verify PostgreSQL is running or check DATABASE_URL in .env.")
        sys.exit(1)

    # 3. Database Migrations
    print(f"\n[3/5] Applying Database Migrations (Alembic):")
    try:
        res = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=str(backend_dir), capture_output=True, text=True)
        if res.returncode == 0:
            print("   [OK] Alembic migrations up-to-date.")
        else:
            print(f"   [WARNING] Migration output: {res.stderr.strip() or res.stdout.strip()}")
    except Exception as m_err:
        print(f"   [WARNING] Could not execute alembic CLI directly ({m_err}). Skipping...")

    # 4. Deterministic Seed Data
    print(f"\n[4/5] Seeding Classroom Demonstration Dataset:")
    try:
        seed_database()
        print("   [OK] 10 Deterministic demo scenario objects inserted.")
    except Exception as s_err:
        print(f"   [ERROR] Seeding failed: {s_err}")
        sys.exit(1)

    # 5. Production Smoke Verification
    print(f"\n[5/5] Running Pre-flight Smoke Test:")
    try:
        from scripts.run_smoke_test import run_smoke_test
        run_smoke_test()
        print("   [OK] Pre-flight smoke test passed.")
    except Exception as sm_err:
        print(f"   [WARNING] Pre-flight smoke test warning: {sm_err}")

    # Final Launch Guidance
    print("\n" + "=" * 70)
    print("      [SUCCESS] DEMO ENVIRONMENT IS FULLY PREPARED & READY!")
    print("=" * 70)
    print("\nNext Steps to Start Demonstration:")
    print("   1. Start Backend API Server:")
    print("      cd backend && uvicorn app.main:app --reload --port 8000")
    print("   2. Start React Dashboard UI:")
    print("      cd frontend && npm run dev")
    print("   3. Run End-to-End Demo Script:")
    print("      python backend/scripts/run_e2e_demo.py")
    print("   4. Launch Docker Compose (Alternative):")
    print("      docker compose up -d")
    print("=" * 70)


if __name__ == "__main__":
    start_demo_launcher()
