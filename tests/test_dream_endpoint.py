# tests/test_dream_endpoint.py
from fastapi.testclient import TestClient

from backend.app.main import app


def test_dream_memory_endpoint_anonymous():
    client = TestClient(app)
    # No sessions for a fresh anon student → empty memory, 200
    r = client.get("/api/v1/dream/memory")
    assert r.status_code == 200
    assert "dreams" in r.json()
