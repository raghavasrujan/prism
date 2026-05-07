"""In-memory mock provider — used by tests to run the full agent loop
without touching real LLM APIs.

Programme the queue via ``MockProvider.set_script([...])`` before invoking.
Each script entry is one call: a ``ProviderResponse`` (or a callable that
receives the messages and returns one).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from app.models_db.provider_model import ProviderModel
from app.services.providers.base import ProviderResponse, ProviderStreamEvent

Programmed = ProviderResponse | Callable[[list[dict[str, Any]]], ProviderResponse]


class MockProvider:
    _script: list[Programmed] = []
    _calls: list[dict[str, Any]] = []

    @classmethod
    def set_script(cls, script: list[Programmed]) -> None:
        cls._script = list(script)
        cls._calls = []

    @classmethod
    def calls(cls) -> list[dict[str, Any]]:
        return list(cls._calls)

    async def chat(
        self,
        model: ProviderModel,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        MockProvider._calls.append(
            {"messages": messages, "tools": tools, "model": model.model_name}
        )
        if not MockProvider._script:
            return ProviderResponse(
                content="[mock] no script configured",
                provider_snapshot=f"mock:{model.model_name}",
                input_tokens=1,
                output_tokens=1,
                finish_reason="stop",
            )
        item = MockProvider._script.pop(0)
        resp = item(messages) if callable(item) else item
        if not resp.provider_snapshot:
            resp.provider_snapshot = f"mock:{model.model_name}"
        return resp

    async def chat_stream(
        self,
        model: ProviderModel,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ProviderStreamEvent]:
        resp = await self.chat(
            model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        for ch in resp.content:
            yield ProviderStreamEvent(kind="token", delta=ch)
        for tc in resp.tool_calls:
            import json as _json

            yield ProviderStreamEvent(
                kind="tool_call.delta",
                tool_call_id=tc.get("id"),
                tool_name=tc.get("name"),
                arguments_delta=_json.dumps(tc.get("arguments") or {}),
            )
        yield ProviderStreamEvent(
            kind="finish",
            finish_reason=resp.finish_reason,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
        )
