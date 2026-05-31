# tests/test_mastery_endpoint.py
from fastapi.testclient import TestClient

from backend.app.main import app


def test_mastery_endpoint_anonymous():
    client = TestClient(app)
    r = client.get("/api/v1/students/me/mastery")
    assert r.status_code == 200
    body = r.json()
    assert "topics" in body
    assert "mastery_by_skill" in body
    assert isinstance(body["topics"], list)
    assert isinstance(body["mastery_by_skill"], dict)
