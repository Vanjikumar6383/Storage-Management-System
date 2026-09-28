"""
Unit tests for Edge & Failure Cases in Storage Lifecycle Optimizer.
Verifies all 5 edge and failure cases:
1. Legal Hold on Expired Object (Enforces HOLD override)
2. Restore Thrashing / Retrieval Cost Protection (Guarantees retrieval cost safety)
3. Conflicting Retention Policies (Enforces hierarchical precedence)
4. Storage Migration Execution & Rollback Pipeline
5. Ephemeral Development Environment Decommissioning
"""

import pytest
from app.db.database import SessionLocal
from app.models import Organization, StorageLocation
from app.services.edge_cases_service import EdgeCasesVerificationService


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_edge_cases_all(db_session):
    org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    if not org:
        org = db_session.query(Organization).first()
    assert org is not None, "Organization required for edge case test"

    service = EdgeCasesVerificationService()
    results = service.run_all_edge_cases(db_session, org.id)

    assert results["total_cases"] == 5
    assert results["passed_cases"] == 5
    assert results["overall_status"] == "PASSED"
