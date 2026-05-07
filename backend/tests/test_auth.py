"""Auth flow: register / login / refresh / rotation-reuse / logout / me."""

from __future__ import annotations


def _register(client, email="bob@example.com", pw="hunter22-strongpass"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pw, "display_name": "Bob"},
    )


def test_register_success(client):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "bob@example.com"
    assert body["user"]["role"] == "user"
    assert body["access"]
    assert body["refresh"]
    assert body["access"] != body["refresh"]


def test_register_duplicate_email(client):
    _register(client)
    r = _register(client)
    assert r.status_code == 409


def test_register_weak_password(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short"},
    )
    assert r.status_code == 422


def test_login_success(client):
    _register(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "hunter22-strongpass"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "bob@example.com"


def test_login_wrong_password(client):
    _register(client)
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrong-password-1"},
    )
    assert r.status_code == 401


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_with_token(client, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


def test_refresh_rotates(client, auth_headers):
    old_refresh = auth_headers["refresh"]
    r = client.post("/api/v1/auth/refresh", json={"refresh": old_refresh})
    assert r.status_code == 200
    body = r.json()
    assert body["refresh"] != old_refresh
    # Old refresh should now be invalid
    r2 = client.post("/api/v1/auth/refresh", json={"refresh": old_refresh})
    assert r2.status_code == 401


def test_refresh_reuse_revokes_family(client, auth_headers):
    r1 = client.post("/api/v1/auth/refresh", json={"refresh": auth_headers["refresh"]})
    assert r1.status_code == 200
    r2 = client.post("/api/v1/auth/refresh", json={"refresh": r1.json()["refresh"]})
    assert r2.status_code == 200
    # Present the ORIGINAL refresh again → reuse detected → whole family revoked
    r_bad = client.post("/api/v1/auth/refresh", json={"refresh": auth_headers["refresh"]})
    assert r_bad.status_code == 401
    # Latest live refresh should also now be revoked
    r3 = client.post("/api/v1/auth/refresh", json={"refresh": r2.json()["refresh"]})
    assert r3.status_code == 401


def test_logout_revokes_refresh(client, auth_headers):
    r = client.post("/api/v1/auth/logout", json={"refresh": auth_headers["refresh"]})
    assert r.status_code == 204
    # Refresh should now be dead
    r2 = client.post("/api/v1/auth/refresh", json={"refresh": auth_headers["refresh"]})
    assert r2.status_code == 401


def test_invalid_bearer_token(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
