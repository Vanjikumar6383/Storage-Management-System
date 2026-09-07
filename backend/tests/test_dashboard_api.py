import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import SessionLocal
from app.models import Organization

client = TestClient(app)

@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_dashboard_endpoints(db_session):
    demo_org = db_session.query(Organization).filter_by(slug="demo-organization").first()
    
    # 1. List Organizations
    res_orgs = client.get("/api/v1/organizations")
    assert res_orgs.status_code == 200
    assert len(res_orgs.json()) >= 1

    # 2. Dashboard Summary
    res_sum = client.get(f"/api/v1/organizations/{demo_org.id}/dashboard-summary")
    assert res_sum.status_code == 200
    data = res_sum.json()
    assert "total_storage_bytes" in data
    assert "estimated_monthly_cost_usd" in data
    assert "storage_by_class" in data

    # 3. List Objects
    res_objs = client.get(f"/api/v1/organizations/{demo_org.id}/objects")
    assert res_objs.status_code == 200
    assert "items" in res_objs.json()

    # 4. List Recommendations
    res_recs = client.get(f"/api/v1/organizations/{demo_org.id}/recommendations")
    assert res_recs.status_code == 200
    assert "items" in res_recs.json()

    # 5. List Migrations
    res_migs = client.get(f"/api/v1/organizations/{demo_org.id}/migrations")
    assert res_migs.status_code == 200
    assert isinstance(res_migs.json(), list)

    # 6. List Audit Logs
    res_aud = client.get(f"/api/v1/organizations/{demo_org.id}/audit-logs")
    assert res_aud.status_code == 200
    assert "items" in res_aud.json()

    # 7. List Policies & Legal Holds
    res_pols = client.get(f"/api/v1/organizations/{demo_org.id}/policies")
    assert res_pols.status_code == 200
    assert "policies" in res_pols.json()
    assert "legal_holds" in res_pols.json()
