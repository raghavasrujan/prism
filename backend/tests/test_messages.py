"""Non-streaming chat via MockProvider — verifies the full agent loop
including tool calls and usage accounting.
"""

from __future__ import annotations

from app.services.providers.base import ProviderResponse
from app.services.providers.mock import MockProvider


def _create_model(client, headers, *, pricing=True):
    body = {
        "name": "gpt-mock",
        "provider_type": "openai",
        "model_name": "gpt-4o-mini",
        "api_key": "sk-test",
    }
    if pricing:
        body["price_input_per_mtok_usd"] = 0.15
        body["price_output_per_mtok_usd"] = 0.60
    r = client.post("/api/v1/models", json=body, headers=headers)
    return r.json()


def _create_conv(client, headers, model_id, **overrides):
    body = {"title": "test", "provider_model_id": model_id}
    body.update(overrides)
    return client.post("/api/v1/conversations", json=body, headers=headers).json()


def _create_python_adder(client, headers):
    return client.post(
        "/api/v1/tools",
        headers=headers,
        json={
            "name": "adder",
            "description": "Adds two numbers",
            "impl_type": "python_inline",
            "code": "def run(args):\n    return {'sum': args['a'] + args['b']}\n",
            "args_schema": {
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
            "timeout_ms": 4000,
        },
    ).json()


def test_send_simple_message(client, auth_headers):
    MockProvider.set_script(
        [
            ProviderResponse(
                content="Hi Alice, how can I help?",
                input_tokens=8,
                output_tokens=6,
                finish_reason="stop",
                provider_snapshot="mock:gpt-4o-mini",
            )
        ]
    )
    m = _create_model(client, auth_headers["headers"])
    conv = _create_conv(client, auth_headers["headers"], m["id"])

    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=auth_headers["headers"],
        json={"content": "Hello!"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["assistant_message"]["content"][0]["text"] == "Hi Alice, how can I help?"
    assert body["assistant_message"]["input_tokens"] == 8
    assert body["assistant_message"]["output_tokens"] == 6
    # Cost: 8*0.15/1M + 6*0.60/1M = 0.0000012 + 0.0000036 = 0.0000048
    cost = float(body["assistant_message"]["cost_usd"])
    assert cost > 0
    assert body["usage"]["message_count"] == 1


def test_send_message_with_tool_call(client, auth_headers):
    m = _create_model(client, auth_headers["headers"])
    tool = _create_python_adder(client, auth_headers["headers"])
    conv = _create_conv(
        client, auth_headers["headers"], m["id"], tool_ids=[tool["id"]]
    )

    # First model call: request a tool call
    # Second model call: final answer using the tool result
    MockProvider.set_script(
        [
            ProviderResponse(
                content="",
                tool_calls=[
                    {"id": "call_1", "name": "adder", "arguments": {"a": 2, "b": 40}}
                ],
                input_tokens=10,
                output_tokens=4,
                finish_reason="tool_calls",
                provider_snapshot="mock:gpt-4o-mini",
            ),
            ProviderResponse(
                content="The answer is 42.",
                input_tokens=20,
                output_tokens=6,
                finish_reason="stop",
                provider_snapshot="mock:gpt-4o-mini",
            ),
        ]
    )

    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=auth_headers["headers"],
        json={"content": "What is 2 + 40?"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body["tool_messages"]) == 1
    tm = body["tool_messages"][0]
    assert tm["tool_name"] == "adder"
    assert "42" in tm["content"][0]["text"] or "sum" in tm["content"][0]["text"]
    assert body["assistant_message"]["content"][0]["text"] == "The answer is 42."


def test_conversation_usage_aggregates(client, auth_headers):
    m = _create_model(client, auth_headers["headers"])
    conv = _create_conv(client, auth_headers["headers"], m["id"])

    # Two turns
    MockProvider.set_script(
        [
            ProviderResponse(
                content="first", input_tokens=10, output_tokens=5, finish_reason="stop"
            ),
            ProviderResponse(
                content="second", input_tokens=15, output_tokens=8, finish_reason="stop"
            ),
        ]
    )

    client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=auth_headers["headers"],
        json={"content": "one"},
    )
    client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=auth_headers["headers"],
        json={"content": "two"},
    )

    r = client.get(
        f"/api/v1/conversations/{conv['id']}/usage", headers=auth_headers["headers"]
    )
    assert r.status_code == 200
    body = r.json()
    assert body["input_tokens"] == 25
    assert body["output_tokens"] == 13
    assert body["message_count"] == 2
    assert len(body["by_model"]) == 1
    assert body["by_model"][0]["message_count"] == 2


def test_list_messages(client, auth_headers):
    m = _create_model(client, auth_headers["headers"])
    conv = _create_conv(client, auth_headers["headers"], m["id"])

    MockProvider.set_script(
        [ProviderResponse(content="pong", input_tokens=1, output_tokens=1, finish_reason="stop")]
    )
    client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=auth_headers["headers"],
        json={"content": "ping"},
    )

    r = client.get(
        f"/api/v1/conversations/{conv['id']}/messages", headers=auth_headers["headers"]
    )
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_correlation_ids_shared_within_turn(client, auth_headers):
    """user + assistant messages of one turn must share the same request_id."""
    m = _create_model(client, auth_headers["headers"])
    conv = _create_conv(client, auth_headers["headers"], m["id"])
    MockProvider.set_script(
        [ProviderResponse(content="ok", input_tokens=1, output_tokens=1, finish_reason="stop")]
    )
    r = client.post(
        f"/api/v1/conversations/{conv['id']}/messages",
        headers=auth_headers["headers"],
        json={"content": "hi"},
    )
    body = r.json()
    assert body["user_message"]["request_id"] == body["assistant_message"]["request_id"]
    assert body["request_id"] == body["assistant_message"]["request_id"]
