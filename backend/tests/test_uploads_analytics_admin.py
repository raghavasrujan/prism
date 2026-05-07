"""Uploads + analytics + admin coverage."""

from __future__ import annotations

import io

from app.services.providers.base import ProviderResponse
from app.services.providers.mock import MockProvider


def test_upload_image(client, auth_headers):
    files = {"file": ("logo.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")}
    r = client.post("/api/v1/uploads", headers=auth_headers["headers"], files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "image"
    assert body["mime_type"].startswith("image/")
    assert body["size_bytes"] > 0
    assert len(body["sha256"]) == 64

    aid = body["id"]
    r2 = client.get(f"/api/v1/uploads/{aid}", headers=auth_headers["headers"])
    assert r2.status_code == 200
    assert r2.content.startswith(b"\x89PNG")


def test_upload_too_large_rejected(client, auth_headers):
    # 11MB > 10MB image cap
    payload = b"x" * (11 * 1024 * 1024)
    files = {"file": ("big.png", io.BytesIO(payload), "image/png")}
    r = client.post("/api/v1/uploads", headers=auth_headers["headers"], files=files)
    assert r.status_code == 413


def test_delete_upload(client, auth_headers):
    files = {"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post("/api/v1/uploads", headers=auth_headers["headers"], files=files)
    aid = r.json()["id"]
    r2 = client.delete(f"/api/v1/uploads/{aid}", headers=auth_headers["headers"])
    assert r2.status_code == 204
    r3 = client.get(f"/api/v1/uploads/{aid}", headers=auth_headers["headers"])
    assert r3.status_code == 404


def test_upload_other_user_forbidden(client, auth_headers):
    files = {"file": ("secret.txt", io.BytesIO(b"top secret"), "text/plain")}
    r = client.post("/api/v1/uploads", headers=auth_headers["headers"], files=files)
    aid = r.json()["id"]

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "spy@example.com", "password": "sneaking-around-88"},
    )
    other = {"Authorization": f"Bearer {reg.json()['access']}"}
    r2 = client.get(f"/api/v1/uploads/{aid}", headers=other)
    assert r2.status_code == 404


def test_analytics_usage_series(client, auth_headers):
    m = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={
            "name": "gpt-mock",
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "sk-test",
            "price_input_per_mtok_usd": 0.15,
            "price_output_per_mtok_usd": 0.60,
        },
    ).json()
    conv = client.post(
        "/api/v1/conversations",
        headers=auth_headers["headers"],
        json={"title": "a", "provider_model_id": m["id"]},
    ).json()

    MockProvider.set_script(
        [
            ProviderResponse(content="ok1", input_tokens=10, output_tokens=5, finish_reason="stop"),
            ProviderResponse(content="ok2", input_tokens=20, output_tokens=8, finish_reason="stop"),
        ]
    )
    for txt in ["one", "two"]:
        client.post(
            f"/api/v1/conversations/{conv['id']}/messages",
            headers=auth_headers["headers"],
            json={"content": txt},
        )

    r = client.get("/api/v1/analytics/usage?group_by=model", headers=auth_headers["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["input_tokens"] == 30
    assert body["totals"]["output_tokens"] == 13
    assert body["totals"]["request_count"] == 2


def test_analytics_by_model(client, auth_headers):
    m = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={"name": "m", "provider_type": "openai", "model_name": "gpt-4o-mini", "api_key": "sk"},
    ).json()
    conv = client.post(
        "/api/v1/conversations",
        headers=auth_headers["headers"],
        json={"title": "a", "provider_model_id": m["id"]},
    ).json()
    MockProvider.set_script(
        [ProviderResponse(content="ok", input_tokens=3, output_tokens=2, finish_reason="stop")]
    )
    client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=auth_headers["headers"],
        json={"content": "hi"},
    )

    r = client.get("/api/v1/analytics/models", headers=auth_headers["headers"])
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["request_count"] == 1
    assert rows[0]["input_tokens"] == 3
    assert rows[0]["output_tokens"] == 2


def test_admin_requires_admin_role(client, auth_headers):
    r = client.get("/api/v1/admin/users", headers=auth_headers["headers"])
    assert r.status_code == 403


def _promote_to_admin(email: str):
    """Direct DB path (there is no public 'first-user-becomes-admin' endpoint)."""
    from app.db import get_sessionmaker
    from app.models_db.user import User, UserRole

    session = get_sessionmaker()()
    try:
        u = session.query(User).filter(User.email == email).one()
        u.role = UserRole.admin
        session.commit()
    finally:
        session.close()


def test_admin_list_users(client, auth_headers):
    _promote_to_admin(auth_headers["user"]["email"])
    # Re-login to get an access token that carries the new role
    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": auth_headers["user"]["email"], "password": "hunter22-strongpass"},
    )
    admin_h = {"Authorization": f"Bearer {r_login.json()['access']}"}

    # Add a second user
    client.post(
        "/api/v1/auth/register",
        json={"email": "eve@example.com", "password": "another-strong-pass-99"},
    )

    r = client.get("/api/v1/admin/users", headers=admin_h)
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 2


def test_admin_disable_user(client, auth_headers):
    _promote_to_admin(auth_headers["user"]["email"])
    r_login = client.post(
        "/api/v1/auth/login",
        json={"email": auth_headers["user"]["email"], "password": "hunter22-strongpass"},
    )
    admin_h = {"Authorization": f"Bearer {r_login.json()['access']}"}

    r_reg = client.post(
        "/api/v1/auth/register",
        json={"email": "target@example.com", "password": "will-be-locked-out"},
    )
    target = r_reg.json()["user"]

    r = client.patch(
        f"/api/v1/admin/users/{target['id']}",
        headers=admin_h,
        json={"is_active": False},
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # Login attempt now fails
    r_fail = client.post(
        "/api/v1/auth/login",
        json={"email": "target@example.com", "password": "will-be-locked-out"},
    )
    assert r_fail.status_code == 403
