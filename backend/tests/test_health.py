"""Smoke test for the scaffold health endpoint."""

from fastapi.testclient import TestClient

from main import create_app


def test_health_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
