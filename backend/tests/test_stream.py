"""SSE streaming end-to-end."""

from __future__ import annotations

import json

from app.services.providers.base import ProviderResponse
from app.services.providers.mock import MockProvider


def _model_and_conv(client, headers):
    m = client.post(
        "/api/v1/models",
        headers=headers,
        json={
            "name": "gpt-mock",
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "sk-test",
        },
    ).json()
    c = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"title": "s", "provider_model_id": m["id"]},
    ).json()
    return m, c


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    current: dict = {}
    for line in text.splitlines():
        if line.startswith("event:"):
            current["event"] = line[6:].strip()
        elif line.startswith("data:"):
            payload = line[5:].strip()
            try:
                current["data"] = json.loads(payload)
            except json.JSONDecodeError:
                current["data"] = payload
        elif line == "":
            if current:
                events.append(current)
                current = {}
    if current:
        events.append(current)
    return events


def test_stream_emits_tokens_and_usage(client, auth_headers):
    MockProvider.set_script(
        [
            ProviderResponse(
                content="Hello world!",
                input_tokens=4,
                output_tokens=3,
                finish_reason="stop",
                provider_snapshot="mock:gpt-4o-mini",
            )
        ]
    )
    _m, conv = _model_and_conv(client, auth_headers["headers"])
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages/stream",
        headers=auth_headers["headers"],
        json={"content": "hi"},
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    kinds = [e["event"] for e in events]
    assert "stream.start" in kinds
    assert kinds.count("token") == len("Hello world!")
    assert "usage" in kinds
    assert "stream.end" in kinds

    usage_ev = next(e for e in events if e["event"] == "usage")
    assert usage_ev["data"]["input_tokens"] == 4
    assert usage_ev["data"]["output_tokens"] == 3

    end_ev = next(e for e in events if e["event"] == "stream.end")
    assert end_ev["data"]["finish_reason"] == "stop"
    assert end_ev["data"]["assistant_message_id"]


def test_stream_end_persists_message(client, auth_headers):
    MockProvider.set_script(
        [ProviderResponse(content="persisted", input_tokens=1, output_tokens=1, finish_reason="stop")]
    )
    _m, conv = _model_and_conv(client, auth_headers["headers"])
    client.post(
        f"/api/v1/conversations/{conv['id']}/messages/stream",
        headers=auth_headers["headers"],
        json={"content": "ping"},
    )
    msgs = client.get(
        f"/api/v1/conversations/{conv['id']}/messages", headers=auth_headers["headers"]
    ).json()
    assert len(msgs) == 2
    assert msgs[1]["content"][0]["text"] == "persisted"
    assert msgs[1]["input_tokens"] == 1
    assert msgs[1]["output_tokens"] == 1


def test_cancel_endpoint_204_even_when_unknown(client, auth_headers):
    r = client.post(
        "/api/v1/messages/nonexistent-request-id/cancel",
        headers=auth_headers["headers"],
    )
    assert r.status_code == 204
