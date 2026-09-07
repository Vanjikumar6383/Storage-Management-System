from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("HEALTHY", "DEGRADED", "ok")
    assert "environment" in data


def test_system_info():
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Storage Lifecycle Optimizer"
    assert data["version"] == "0.1.0"
