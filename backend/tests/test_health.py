"""
test_health.py — health endpoints must keep passing (deliverable #5).
"""
from fastapi.testclient import TestClient

import main


def test_health_full():
    client = TestClient(main.app)
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "reposcope-api"
    assert "openrouter_keys" in data["checks"]


def test_health_simple_and_root():
    client = TestClient(main.app)
    assert client.get("/health").json() == {"status": "ok"}
    # Root redirects to /api/health for browsers
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (302, 307)
