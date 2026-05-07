"""Provider models CRUD."""

from __future__ import annotations


def _make(client, headers, **overrides):
    body = {
        "name": "OpenAI GPT-4o mini",
        "provider_type": "openai",
        "model_name": "gpt-4o-mini",
        "api_key": "sk-test-not-real-abc",
        "supports_vision": True,
        "supports_tools": True,
        "default_system_prompt": "Be concise.",
    }
    body.update(overrides)
    return client.post("/api/v1/models", json=body, headers=headers)


def test_create_and_list_openai(client, auth_headers):
    r = _make(client, auth_headers["headers"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider_type"] == "openai"
    assert body["has_api_key"] is True

    r2 = client.get("/api/v1/models", headers=auth_headers["headers"])
    assert r2.status_code == 200
    items = r2.json()
    assert len(items) == 1
    assert items[0]["name"] == "OpenAI GPT-4o mini"


def test_endpoint_required_for_ollama(client, auth_headers):
    r = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={
            "name": "Local Ollama",
            "provider_type": "ollama",
            "model_name": "llama3.2",
        },
    )
    assert r.status_code == 422


def test_endpoint_ok_for_ollama(client, auth_headers):
    r = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={
            "name": "Local Ollama",
            "provider_type": "ollama",
            "endpoint_url": "http://localhost:11434",
            "model_name": "llama3.2",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["endpoint_url"] == "http://localhost:11434"


def test_duplicate_name_rejected(client, auth_headers):
    r1 = _make(client, auth_headers["headers"])
    assert r1.status_code == 201
    r2 = _make(client, auth_headers["headers"])
    assert r2.status_code == 409


def test_users_isolated(client, auth_headers):
    _make(client, auth_headers["headers"])

    # Second user
    r_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "carol@example.com",
            "password": "wonderland-88-strong",
            "display_name": "Carol",
        },
    )
    assert r_reg.status_code == 201
    other = {"Authorization": f"Bearer {r_reg.json()['access']}"}

    r = client.get("/api/v1/models", headers=other)
    assert r.status_code == 200
    assert r.json() == []


def test_update_model(client, auth_headers):
    r = _make(client, auth_headers["headers"])
    mid = r.json()["id"]
    r2 = client.patch(
        f"/api/v1/models/{mid}",
        headers=auth_headers["headers"],
        json={"name": "OpenAI Fast", "supports_vision": False},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["name"] == "OpenAI Fast"
    assert body["supports_vision"] is False


def test_delete_model(client, auth_headers):
    r = _make(client, auth_headers["headers"])
    mid = r.json()["id"]
    r2 = client.delete(f"/api/v1/models/{mid}", headers=auth_headers["headers"])
    assert r2.status_code == 204
    r3 = client.get("/api/v1/models", headers=auth_headers["headers"])
    assert r3.json() == []


def test_api_key_encrypted_at_rest(client, auth_headers):
    """The stored ciphertext must NOT equal the plaintext key."""
    import sqlite3

    r = _make(client, auth_headers["headers"], api_key="sk-super-secret-plaintext")
    assert r.status_code == 201
    with sqlite3.connect("./data/test.db") as con:
        row = con.execute(
            "SELECT api_key_encrypted FROM provider_models WHERE id = ?", (r.json()["id"],)
        ).fetchone()
    assert row is not None
    stored = row[0]
    assert stored is not None
    assert "sk-super-secret-plaintext" not in stored
