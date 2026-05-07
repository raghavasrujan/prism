"""Conversations CRUD + share + usage aggregation."""

from __future__ import annotations


def _create_model(client, headers, name="OpenAI Fast"):
    return client.post(
        "/api/v1/models",
        headers=headers,
        json={
            "name": name,
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "sk-test",
        },
    )


def _create_conv(client, headers, model_id, **overrides):
    body = {"title": "First chat", "provider_model_id": model_id}
    body.update(overrides)
    return client.post("/api/v1/conversations", json=body, headers=headers)


def test_create_conversation(client, auth_headers):
    m = _create_model(client, auth_headers["headers"]).json()
    r = _create_conv(client, auth_headers["headers"], m["id"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "First chat"
    assert body["provider_model_id"] == m["id"]


def test_conversation_not_found(client, auth_headers):
    r = client.get("/api/v1/conversations/does-not-exist", headers=auth_headers["headers"])
    assert r.status_code == 404


def test_delete_conversation(client, auth_headers):
    m = _create_model(client, auth_headers["headers"]).json()
    r = _create_conv(client, auth_headers["headers"], m["id"])
    cid = r.json()["id"]
    r2 = client.delete(f"/api/v1/conversations/{cid}", headers=auth_headers["headers"])
    assert r2.status_code == 204
    r3 = client.get("/api/v1/conversations", headers=auth_headers["headers"])
    assert r3.json() == []


def test_share_and_unshare(client, auth_headers):
    m = _create_model(client, auth_headers["headers"]).json()
    r = _create_conv(client, auth_headers["headers"], m["id"])
    cid = r.json()["id"]

    r_share = client.post(f"/api/v1/conversations/{cid}/share", headers=auth_headers["headers"])
    assert r_share.status_code == 200
    slug = r_share.json()["slug"]
    assert len(slug) >= 20

    r_get = client.get(f"/api/v1/conversations/{cid}", headers=auth_headers["headers"])
    assert r_get.json()["is_shared"] is True
    assert r_get.json()["share_slug"] == slug

    r_unshare = client.delete(f"/api/v1/conversations/{cid}/share", headers=auth_headers["headers"])
    assert r_unshare.status_code == 204

    r_get2 = client.get(f"/api/v1/conversations/{cid}", headers=auth_headers["headers"])
    assert r_get2.json()["is_shared"] is False


def test_conversation_update_and_prompt_override(client, auth_headers):
    m = _create_model(client, auth_headers["headers"]).json()
    r = _create_conv(client, auth_headers["headers"], m["id"])
    cid = r.json()["id"]
    r2 = client.patch(
        f"/api/v1/conversations/{cid}",
        headers=auth_headers["headers"],
        json={
            "title": "Renamed",
            "system_prompt_override": "You are a squirrel expert.",
        },
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["title"] == "Renamed"
    assert body["system_prompt_override"] == "You are a squirrel expert."


def test_conversation_isolated_between_users(client, auth_headers):
    m = _create_model(client, auth_headers["headers"]).json()
    _create_conv(client, auth_headers["headers"], m["id"])

    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "eve@example.com", "password": "hunter22-strongpass", "display_name": "E"},
    )
    other = {"Authorization": f"Bearer {reg.json()['access']}"}
    r = client.get("/api/v1/conversations", headers=other)
    assert r.status_code == 200
    assert r.json() == []
