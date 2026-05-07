"""Azure OpenAI provider — CRUD + adapter URL / header construction."""

from __future__ import annotations

import pytest

from app.models_db.provider_model import ProviderModel, ProviderType
from app.services.providers.openai_family import OpenAiFamilyProvider


def _make_model(**overrides) -> ProviderModel:
    """Build an unpersisted ORM object for adapter unit tests."""
    defaults = dict(
        id="00000000-0000-0000-0000-000000000000",
        user_id="00000000-0000-0000-0000-000000000000",
        name="azure test",
        provider_type=ProviderType.azure,
        endpoint_url="https://openai-eastus2-rai.openai.azure.com/",
        model_name="gpt-4o-eastus2-rai",
        api_version="2025-01-01-preview",
        api_key_encrypted="azure-secret-key",
        extra_headers_encrypted=None,
    )
    defaults.update(overrides)
    m = ProviderModel(**defaults)
    return m


# --------------------------------------------------------------------------- #
# CRUD via API
# --------------------------------------------------------------------------- #


def test_create_azure_model(client, auth_headers):
    r = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={
            "name": "Azure GPT-4o EastUS2",
            "provider_type": "azure",
            "endpoint_url": "https://openai-eastus2-rai.openai.azure.com/",
            "model_name": "gpt-4o-eastus2-rai",
            "api_version": "2025-01-01-preview",
            "api_key": "azure-secret-abc",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider_type"] == "azure"
    assert body["endpoint_url"] == "https://openai-eastus2-rai.openai.azure.com/"
    assert body["model_name"] == "gpt-4o-eastus2-rai"
    assert body["api_version"] == "2025-01-01-preview"
    assert body["has_api_key"] is True


def test_azure_requires_endpoint(client, auth_headers):
    r = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={
            "name": "Azure bad",
            "provider_type": "azure",
            "model_name": "gpt-4o",
            "api_version": "2025-01-01-preview",
        },
    )
    assert r.status_code == 422


def test_azure_requires_api_version(client, auth_headers):
    r = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={
            "name": "Azure no version",
            "provider_type": "azure",
            "endpoint_url": "https://x.openai.azure.com/",
            "model_name": "gpt-4o",
        },
    )
    assert r.status_code == 422


def test_azure_api_key_encrypted_at_rest(client, auth_headers):
    import sqlite3

    r = client.post(
        "/api/v1/models",
        headers=auth_headers["headers"],
        json={
            "name": "Azure enc",
            "provider_type": "azure",
            "endpoint_url": "https://x.openai.azure.com/",
            "model_name": "gpt-4o",
            "api_version": "2025-01-01-preview",
            "api_key": "azure-key-do-not-leak",
        },
    )
    assert r.status_code == 201
    mid = r.json()["id"]
    with sqlite3.connect("./data/test.db") as con:
        row = con.execute(
            "SELECT api_key_encrypted, api_version FROM provider_models WHERE id = ?",
            (mid,),
        ).fetchone()
    assert "azure-key-do-not-leak" not in (row[0] or "")
    assert row[1] == "2025-01-01-preview"


# --------------------------------------------------------------------------- #
# Adapter URL + header construction (unit tests on the adapter)
# --------------------------------------------------------------------------- #


def test_azure_endpoint_construction():
    prov = OpenAiFamilyProvider()
    m = _make_model()
    url = prov._endpoint(m)  # type: ignore[attr-defined]
    assert url == (
        "https://openai-eastus2-rai.openai.azure.com/openai/deployments/"
        "gpt-4o-eastus2-rai/chat/completions?api-version=2025-01-01-preview"
    )


def test_azure_endpoint_accepts_full_deployment_url():
    """If the user pastes the whole URL, honour it and just append api-version."""
    prov = OpenAiFamilyProvider()
    m = _make_model(
        endpoint_url=(
            "https://openai-eastus2-rai.openai.azure.com/openai/deployments/"
            "gpt-4o-eastus2-rai/chat/completions"
        ),
    )
    url = prov._endpoint(m)  # type: ignore[attr-defined]
    assert url.endswith("?api-version=2025-01-01-preview")
    assert "/openai/deployments/gpt-4o-eastus2-rai/chat/completions" in url


def test_azure_headers_use_api_key_not_bearer():
    prov = OpenAiFamilyProvider()
    m = _make_model()
    h = prov._headers(m)  # type: ignore[attr-defined]
    assert h.get("api-key") == "azure-secret-key"
    assert "authorization" not in h
    assert h["content-type"] == "application/json"


def test_openai_headers_still_bearer():
    """Regression: non-Azure providers must keep Authorization: Bearer."""
    prov = OpenAiFamilyProvider()
    m = _make_model(
        provider_type=ProviderType.openai,
        endpoint_url=None,
        api_version=None,
    )
    h = prov._headers(m)  # type: ignore[attr-defined]
    assert h.get("authorization", "").startswith("Bearer ")
    assert "api-key" not in h


def test_azure_endpoint_requires_api_version_at_runtime():
    prov = OpenAiFamilyProvider()
    m = _make_model(api_version=None)
    with pytest.raises(ValueError, match="api_version"):
        prov._endpoint(m)  # type: ignore[attr-defined]


def test_azure_body_omits_model_field():
    """Azure identifies the model via the URL — sending 'model' isn't required."""
    prov = OpenAiFamilyProvider()
    m = _make_model()
    body = prov._body(  # type: ignore[attr-defined]
        m,
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        temperature=None,
        max_tokens=None,
        stream=False,
    )
    assert "model" not in body
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_openai_body_includes_model_field():
    prov = OpenAiFamilyProvider()
    m = _make_model(provider_type=ProviderType.openai, endpoint_url=None, api_version=None)
    body = prov._body(  # type: ignore[attr-defined]
        m,
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        temperature=None,
        max_tokens=None,
        stream=False,
    )
    assert body["model"] == "gpt-4o-eastus2-rai"
