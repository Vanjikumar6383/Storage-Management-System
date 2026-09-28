"""
Edge Cases and Failure Scenarios Demonstration Script.
Executes and validates the 5 core edge/failure scenarios in the Storage Lifecycle Optimizer:
1. Active Legal Hold on Expired Object (Blocks deletion & tiering)
2. Restore Thrashing / Retrieval Cost Protection (Protects against retrieval penalty fees)
3. Conflicting Hierarchical Retention Policies (Strictest policy precedence)
4. Migration Execution & Single-Click Rollback Pipeline (Zero-download tiering & rollback)
5. Ephemeral Development Environment Decommissioning (Short-lived dev environment lifecycle)
"""

import sys
import json
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import SessionLocal
from app.models import Organization
from app.services.edge_cases_service import EdgeCasesVerificationService


def run_edge_cases_demonstration():
    print("=" * 75)
    print("   STORAGE LIFECYCLE OPTIMIZER — EDGE & FAILURE CASES DEMONSTRATION")
    print("=" * 75)

    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(slug="demo-organization").first()
        if not org:
            org = db.query(Organization).first()
        if not org:
            print("[ERROR] No organization found in database. Please run seed script first.")
            sys.exit(1)

        print(f"\nTarget Organization: {org.name} (Slug: {org.slug}, ID: {org.id})\n")

        service = EdgeCasesVerificationService()
        results = service.run_all_edge_cases(db, org.id)

        print("-" * 75)
        for i, case in enumerate(results["cases"], 1):
            print(f"[{i}/5] {case['name']} ({case['case_id']})")
            print(f"      Description: {case['description']}")
            if "expected_action" in case:
                print(f"      Expected Action: {case['expected_action']}")
            if "actual_action" in case:
                print(f"      Actual Decision: {case['actual_action']}")
            if "reason" in case and case["reason"]:
                print(f"      Explainable Reason: {case['reason']}")
            if "rollback_status" in case:
                print(f"      Rollback Status: {case['rollback_status']} (Restored to {case['final_storage_class']})")
            print(f"      Status: [{'PASSED' if case['status'] == 'PASSED' else 'FAILED'}]")
            print("-" * 75)

        print(f"\nSUMMARY: {results['passed_cases']}/{results['total_cases']} Edge & Failure Cases PASSED!")
        print("=" * 75)
        if results["overall_status"] != "PASSED":
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run_edge_cases_demonstration()
