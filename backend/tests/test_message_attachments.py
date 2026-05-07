"""Attachments plugged into message sends — the attachment_ids -> content-part wiring."""

from __future__ import annotations

import io

from app.db import get_sessionmaker
from app.models_db.attachment import Attachment
from app.services.providers.base import ProviderResponse
from app.services.providers.mock import MockProvider

_PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-but-good-enough-for-a-test"


def _create_model(client, headers):
    body = {
        "name": "gpt-mock",
        "provider_type": "openai",
        "model_name": "gpt-4o-mini",
        "api_key": "sk-test",
    }
    return client.post("/api/v1/models", json=body, headers=headers).json()


def _create_conv(client, headers, model_id):
    body = {"title": "test", "provider_model_id": model_id}
    return client.post("/api/v1/conversations", json=body, headers=headers).json()


def _upload(client, headers, filename, data, content_type):
    files = {"file": (filename, io.BytesIO(data), content_type)}
    r = client.post("/api/v1/uploads", headers=headers, files=files)
    assert r.status_code == 201, r.text
    return r.json()


def _last_user_content(calls):
    last_call = calls[-1]
    user_entries = [m for m in last_call["messages"] if m["role"] == "user"]
    return user_entries[-1]["content"]


def test_send_message_with_image_attachment_becomes_image_url_part(client, auth_headers):
    headers = auth_headers["headers"]
    MockProvider.set_script(
        [ProviderResponse(content="I see an image.", input_tokens=5, output_tokens=4, finish_reason="stop")]
    )
    model = _create_model(client, headers)
    conv = _create_conv(client, headers, model["id"])
    upload = _upload(client, headers, "logo.png", _PNG_BYTES, "image/png")
    assert upload["kind"] == "image"

    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=headers,
        json={"content": "describe this", "attachment_ids": [upload["id"]]},
    )
    assert r.status_code == 201, r.text
    body = r.json()

    content = _last_user_content(MockProvider.calls())
    assert isinstance(content, list)
    text_parts = [p for p in content if p["type"] == "text"]
    image_parts = [p for p in content if p["type"] == "image_url"]
    assert any(p["text"] == "describe this" for p in text_parts)
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"].startswith("data:image/")

    # The persisted copy stays lightweight — no base64 blob in the DB.
    persisted = client.get(
        f"/api/v1/conversations/{conv['id']}/messages", headers=headers
    ).json()
    user_msg = next(m for m in persisted if m["role"] == "user")
    persisted_image = next(p for p in user_msg["content"] if p["type"] == "image_url")
    assert persisted_image["image_url"]["url"] == f"attachment://{upload['id']}"

    session = get_sessionmaker()()
    try:
        att = session.get(Attachment, upload["id"])
        assert att.message_id == body["user_message"]["id"]
    finally:
        session.close()


def test_send_message_with_generic_file_becomes_text_mention(client, auth_headers):
    headers = auth_headers["headers"]
    MockProvider.set_script(
        [ProviderResponse(content="Noted.", input_tokens=3, output_tokens=2, finish_reason="stop")]
    )
    model = _create_model(client, headers)
    conv = _create_conv(client, headers, model["id"])
    upload = _upload(client, headers, "report.txt", b"hello world", "text/plain")
    assert upload["kind"] == "file"

    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=headers,
        json={"content": "", "attachment_ids": [upload["id"]]},
    )
    assert r.status_code == 201, r.text

    # Single text part (the file mention, no leading empty user text) collapses
    # to a plain string — see `_parts_to_openai_content`.
    content = _last_user_content(MockProvider.calls())
    assert isinstance(content, str)
    assert "report.txt" in content


def test_attachment_from_other_user_is_ignored(client, auth_headers):
    headers = auth_headers["headers"]
    MockProvider.set_script(
        [ProviderResponse(content="ok", input_tokens=1, output_tokens=1, finish_reason="stop")]
    )
    model = _create_model(client, headers)
    conv = _create_conv(client, headers, model["id"])

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "mallory@example.com", "password": "not-my-attachment-88"},
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access']}"}
    other_upload = _upload(client, other_headers, "secret.png", _PNG_BYTES, "image/png")

    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=headers,
        json={"content": "hi", "attachment_ids": [other_upload["id"]]},
    )
    assert r.status_code == 201, r.text

    content = _last_user_content(MockProvider.calls())
    assert isinstance(content, str) or all(p["type"] != "image_url" for p in content)


def test_stream_message_with_image_attachment_resolves_and_links(client, auth_headers):
    headers = auth_headers["headers"]
    MockProvider.set_script(
        [ProviderResponse(content="streamed", input_tokens=2, output_tokens=2, finish_reason="stop")]
    )
    model = _create_model(client, headers)
    conv = _create_conv(client, headers, model["id"])
    upload = _upload(client, headers, "photo.png", _PNG_BYTES, "image/png")

    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages/stream",
        headers=headers,
        json={"content": "what is this", "attachment_ids": [upload["id"]]},
    )
    assert r.status_code == 200

    content = _last_user_content(MockProvider.calls())
    assert any(p["type"] == "image_url" for p in content)

    session = get_sessionmaker()()
    try:
        att = session.get(Attachment, upload["id"])
        assert att.message_id is not None
    finally:
        session.close()
