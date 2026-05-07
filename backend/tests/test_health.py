"""Health / readiness."""

from __future__ import annotations


def test_live(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"


def test_request_id_header_echoed(client):
    r = client.get("/health/live")
    assert "X-Request-Id" in r.headers
    assert len(r.headers["X-Request-Id"]) >= 32


def test_incoming_request_id_preserved(client):
    rid = "test-fixed-request-id-abc123"
    r = client.get("/health/live", headers={"X-Request-Id": rid})
    assert r.headers["X-Request-Id"] == rid
