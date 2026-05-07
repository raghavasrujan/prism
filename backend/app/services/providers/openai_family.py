"""Adapter for OpenAI + OpenAI-compatible + Ollama (all speak /v1/chat/completions).

Anthropic and Gemini are wire-different and live in their own modules.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.logging_config import get_logger
from app.models_db.provider_model import ProviderModel, ProviderType
from app.services.providers.base import ProviderResponse, ProviderStreamEvent

_log = get_logger(__name__)


class OpenAiFamilyProvider:
    """OpenAI · openai_compatible · Ollama (all Chat-Completions-shaped)."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def _endpoint(self, model: ProviderModel) -> str:
        if model.provider_type == ProviderType.openai:
            base = model.endpoint_url or "https://api.openai.com"
            base = base.rstrip("/")
            if base.endswith("/v1"):
                return f"{base}/chat/completions"
            return f"{base}/v1/chat/completions"

        if model.provider_type == ProviderType.azure:
            base = (model.endpoint_url or "").rstrip("/")
            if not base:
                raise ValueError("endpoint_url required for provider_type=azure")
            if not model.api_version:
                raise ValueError("api_version required for provider_type=azure")
            # If the user pasted a full deployment URL, keep it as-is.
            if "/openai/deployments/" in base:
                return f"{base}?api-version={model.api_version}"
            return (
                f"{base}/openai/deployments/{model.model_name}"
                f"/chat/completions?api-version={model.api_version}"
            )

        # openai_compatible / ollama
        base = (model.endpoint_url or "").rstrip("/")
        if not base:
            raise ValueError(f"endpoint_url required for provider_type={model.provider_type}")
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _headers(self, model: ProviderModel) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if model.api_key_encrypted:
            if model.provider_type == ProviderType.azure:
                # Azure OpenAI uses api-key, NOT Authorization: Bearer.
                headers["api-key"] = model.api_key_encrypted
            else:
                headers["authorization"] = f"Bearer {model.api_key_encrypted}"
        if model.extra_headers_encrypted:
            headers.update({k.lower(): v for k, v in model.extra_headers_encrypted.items()})
        return headers

    def _body(
        self,
        model: ProviderModel,
        *,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
    ) -> dict:
        body: dict[str, Any] = {"messages": messages, "stream": stream}
        # Azure identifies the model via the URL (deployment name).
        if model.provider_type != ProviderType.azure:
            body["model"] = model.model_name
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            # Azure requires max_completion_tokens; other providers use max_tokens.
            if model.provider_type == ProviderType.azure:
                body["max_completion_tokens"] = max_tokens
            else:
                body["max_tokens"] = max_tokens
        if stream and model.provider_type not in {ProviderType.ollama}:
            # Ask OpenAI / Azure to include token-usage in the final SSE chunk.
            # Without this flag, usage is omitted from streaming responses and
            # every message ends up with NULL input_tokens / output_tokens.
            body["stream_options"] = {"include_usage": True}
        return body

    async def chat(
        self,
        model: ProviderModel,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        url = self._endpoint(model)
        headers = self._headers(model)
        body = self._body(
            model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0, transport=self._transport) as client:
            resp = await client.post(url, json=body, headers=headers)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if resp.status_code >= 400:
            _log.warning(
                "provider.error",
                provider=model.provider_type.value,
                status=resp.status_code,
                body=resp.text[:500],
            )
            raise RuntimeError(f"provider HTTP {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        raw_content = msg.get("content")
        content = raw_content if isinstance(raw_content, str) else ""
        tool_calls_raw = msg.get("tool_calls") or []
        tool_calls: list[dict] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            args_str = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_str)
            except (TypeError, ValueError):
                args = {"__raw": args_str}
            tool_calls.append({"id": tc.get("id"), "name": fn.get("name"), "arguments": args})
        usage = data.get("usage") or {}
        return ProviderResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            finish_reason=choice.get("finish_reason") or "stop",
            provider_snapshot=f"{model.provider_type.value}:{model.model_name}",
            raw={"latency_ms": latency_ms},
        )

    async def chat_stream(
        self,
        model: ProviderModel,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ProviderStreamEvent]:
        url = self._endpoint(model)
        headers = self._headers(model)
        body = self._body(
            model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async with httpx.AsyncClient(timeout=None, transport=self._transport) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code >= 400:
                    err_text = (await resp.aread()).decode("utf-8", errors="replace")
                    yield ProviderStreamEvent(kind="error", error=f"HTTP {resp.status_code}: {err_text[:500]}")
                    return

                # OpenAI / Azure only send the tool-call id on the FIRST delta for
                # each tool call; subsequent deltas carry only the `index` field.
                # We track {index → id} so every delta for the same call shares one key.
                _tc_ids: dict[int, str] = {}

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_line = line[5:].strip()
                    if data_line == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data_line)
                    except json.JSONDecodeError:
                        continue

                    # ── Usage-only final chunk (stream_options: include_usage) ──────
                    # OpenAI/Azure send a trailing chunk with `choices: []` and a
                    # `usage` object AFTER the finish_reason chunk.  Handle it first
                    # so we don't fall through to the choice-based logic with an
                    # empty dict.
                    if not chunk.get("choices"):
                        usage = chunk.get("usage") or {}
                        if usage:
                            yield ProviderStreamEvent(
                                kind="finish",
                                finish_reason=None,   # already emitted; just carries usage
                                input_tokens=usage.get("prompt_tokens"),
                                output_tokens=usage.get("completion_tokens"),
                            )
                        continue

                    choice = chunk["choices"][0]
                    delta = choice.get("delta") or {}
                    if "content" in delta and delta["content"]:
                        yield ProviderStreamEvent(kind="token", delta=delta["content"])
                    if delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            fn = tc.get("function") or {}
                            idx: int = tc.get("index") or 0
                            # Stash the id the first time we see this index.
                            if tc.get("id"):
                                _tc_ids[idx] = tc["id"]
                            yield ProviderStreamEvent(
                                kind="tool_call.delta",
                                # Resolved id is now stable for all deltas of this call.
                                tool_call_id=_tc_ids.get(idx),
                                tool_name=fn.get("name"),
                                arguments_delta=fn.get("arguments"),
                            )
                    fr = choice.get("finish_reason")
                    if fr:
                        # Some providers include usage in the finish-reason chunk;
                        # capture it if present (won't double-count when the
                        # usage-only chunk follows).
                        usage = chunk.get("usage") or {}
                        yield ProviderStreamEvent(
                            kind="finish",
                            finish_reason=fr,
                            input_tokens=usage.get("prompt_tokens"),
                            output_tokens=usage.get("completion_tokens"),
                        )
