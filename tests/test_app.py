from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analysis_penalizes_mistake():
    response = client.post(
        "/api/v1/analysis",
        json={"mistakes": [{"mistake_id": "RISK_001", "severity": "critical", "round": 1}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["overall_score"] < 100
    assert data["priority_fix"]["mistake_id"] == "RISK_001"


def test_demo():
    response = client.get("/api/v1/analysis/demo")
    assert response.status_code == 200
    assert len(response.json()["mistakes"]) == 3
