"""Test /health endpoint."""
from fastapi.testclient import TestClient
from src.api.app import app


def test_health_endpoint_returns_m0_contract():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "enterprise-agent-api",
        "version": "0.2.0",
        "environment": "dev",
    }
