"""Provider adapter interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models_db.provider_model import ProviderModel


@dataclass
class ProviderResponse:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str = "stop"
    provider_snapshot: str = ""
    raw: dict | None = None


@dataclass
class ProviderStreamEvent:
    """Emitted by ``chat_stream``."""

    kind: str  # "token" | "tool_call.start" | "tool_call.delta" | "finish" | "usage" | "error"
    delta: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    arguments_delta: str | None = None
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None


class ProviderAdapter(Protocol):
    async def chat(
        self,
        model: ProviderModel,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse: ...

    async def chat_stream(
        self,
        model: ProviderModel,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ProviderStreamEvent]: ...
