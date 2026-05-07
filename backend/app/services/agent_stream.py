"""Streaming variant of the agent runner (SSE).

Emits ``ProviderStreamEvent``-shaped payloads as SSE events. Persists the same
message rows the non-streaming path does, and honours the cancel bus.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.context import bind
from app.logging_config import get_logger
from app.models_db.conversation import Conversation
from app.models_db.message import FinishReason, MessageRole
from app.models_db.provider_model import ProviderModel
from app.repositories import messages as msg_repo
from app.security import new_uuid
from app.services import cancel_bus
from app.services.agent_runner import (
    _attachment_content_parts,
    _build_history,
    _content_to_parts,
    _estimate_cost,
    _finish_reason,
    _link_attachments,
    _run_tool,
    _tool_schemas_for,
)
from app.services.providers import get_provider

_log = get_logger(__name__)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def stream_turn(
    db: Session,
    *,
    conv: Conversation,
    model: ProviderModel,
    user_content: str | list[dict],
    parent_message_id: str | None = None,
    attachment_ids: list[str] | None = None,
) -> AsyncIterator[str]:
    request_id = new_uuid()
    cancel_event = cancel_bus.register(request_id)
    bind(request_id=request_id, conversation_id=conv.id)

    attachment_parts = _attachment_content_parts(db, conv.user_id, attachment_ids or [])
    parts = _content_to_parts(user_content)
    if attachment_parts and isinstance(user_content, str) and not user_content.strip():
        parts = []
    parts = parts + attachment_parts
    user_msg = msg_repo.add_user_message(
        db,
        conversation_id=conv.id,
        request_id=request_id,
        content=parts,
        parent_message_id=parent_message_id,
    )
    _link_attachments(db, attachment_ids or [], user_msg.id)
    yield _sse("stream.start", {"request_id": request_id, "user_message_id": user_msg.id})

    tool_schemas, custom_by_name, mcp_by_name = _tool_schemas_for(db, conv.id)
    provider = get_provider(model)

    parent_for_step = user_msg.id
    accumulated_text = ""
    in_toks_total = 0
    out_toks_total = 0
    start = time.perf_counter()
    finish_reason_final = "stop"
    aborted = False

    # Single-pass streaming (tool loop not fully streaming — after the first
    # finish, if tool_calls, run them and then a second non-streaming call.)
    history = _build_history(db, conv, model)

    try:
        pending_tool_calls: dict[str, dict[str, Any]] = {}
        async for ev in provider.chat_stream(
            model, messages=history, tools=tool_schemas or None
        ):
            if cancel_event.is_set():
                aborted = True
                finish_reason_final = "cancelled"
                yield _sse("stream.cancelled", {"request_id": request_id})
                break

            if ev.kind == "token" and ev.delta:
                accumulated_text += ev.delta
                yield _sse("token", {"delta": ev.delta})
            elif ev.kind == "tool_call.delta":
                # ev.tool_call_id is now always the stable id resolved by index
                # in openai_family.py.  The `or new_uuid()` guard is kept as a
                # last-resort fallback so unknown providers still work — but
                # crucially we must NOT call new_uuid() if id is simply None due
                # to a delta arriving before the first chunk; that would scatter
                # the accumulated arguments across phantom dict entries.
                # A stable fallback key (same for every delta of the same call)
                # is provided by the tool name when the id is unavailable.
                fallback_key = ev.tool_name or "__anon__"
                tc_key = ev.tool_call_id or fallback_key
                tc = pending_tool_calls.setdefault(
                    tc_key,
                    {"id": ev.tool_call_id, "name": ev.tool_name, "arguments_str": ""},
                )
                # Backfill id and name as they arrive (first chunk may carry them).
                if ev.tool_call_id and not tc["id"]:
                    tc["id"] = ev.tool_call_id
                if ev.tool_name and not tc["name"]:
                    tc["name"] = ev.tool_name
                if ev.arguments_delta:
                    tc["arguments_str"] += ev.arguments_delta
                yield _sse(
                    "tool_call.delta",
                    {
                        "id": tc["id"],
                        "name": tc["name"],
                        "arguments_delta": ev.arguments_delta,
                    },
                )
            elif ev.kind == "finish":
                # finish_reason comes first (with no usage), then a second
                # usage-only finish event (finish_reason=None) follows when
                # stream_options: include_usage is set.  Accumulate tokens
                # from both events; only update finish_reason when it is set.
                if ev.finish_reason:
                    finish_reason_final = ev.finish_reason
                if ev.input_tokens:
                    in_toks_total += ev.input_tokens
                if ev.output_tokens:
                    out_toks_total += ev.output_tokens
            elif ev.kind == "error":
                _log.warning("stream.provider.error", error=ev.error)
                yield _sse("error", {"code": "provider_error", "message": ev.error or ""})
                finish_reason_final = "error"
                break
    except Exception as exc:  # pragma: no cover
        _log.exception("stream.exception", error=str(exc))
        yield _sse("error", {"code": "runner_error", "message": str(exc)})
        finish_reason_final = "error"

    duration_ms = int((time.perf_counter() - start) * 1000)

    # Assemble tool calls
    parsed_tool_calls: list[dict] = []
    for tc in pending_tool_calls.values() if not aborted else []:
        args: dict[str, Any] = {}
        s = tc.get("arguments_str") or ""
        if s:
            try:
                args = json.loads(s)
            except json.JSONDecodeError:
                args = {"__raw": s}
        parsed_tool_calls.append({"id": tc["id"], "name": tc["name"], "arguments": args})

    if parsed_tool_calls and not aborted:
        # Persist announcement, run tools, then do ONE final call for the reply.
        assistant_step = msg_repo.add_assistant_message(
            db,
            conversation_id=conv.id,
            request_id=request_id,
            parent_message_id=parent_for_step,
            content=[{"type": "text", "text": accumulated_text}],
            tool_calls=parsed_tool_calls,
            provider_snapshot=f"{model.provider_type.value}:{model.model_name}",
            input_tokens=in_toks_total or None,
            output_tokens=out_toks_total or None,
            cost_usd=_estimate_cost(model, in_toks_total or None, out_toks_total or None),
            latency_ms=duration_ms,
            finish_reason=FinishReason.tool_calls,
        )
        parent_for_step = assistant_step.id
        yield _sse("tool_call.start_batch", {"count": len(parsed_tool_calls)})

        for tc in parsed_tool_calls:
            if cancel_event.is_set():
                aborted = True
                finish_reason_final = "cancelled"
                yield _sse("stream.cancelled", {"request_id": request_id})
                break
            ok, text = await _run_tool(
                tc["name"] or "", tc.get("arguments") or {}, custom_by_name, mcp_by_name
            )
            tm = msg_repo.add_tool_result(
                db,
                conversation_id=conv.id,
                request_id=request_id,
                parent_message_id=parent_for_step,
                tool_call_id=tc["id"] or new_uuid(),
                tool_name=tc["name"] or "unknown",
                content=[{"type": "text", "text": text}],
            )
            parent_for_step = tm.id
            yield _sse(
                "tool_call.result",
                {"id": tc["id"], "name": tc["name"], "ok": ok, "output_preview": text[:1024]},
            )

        if not aborted:
            follow_history = _build_history(db, conv, model)
            follow_start = time.perf_counter()
            accumulated_text = ""
            try:
                async for ev in provider.chat_stream(
                    model, messages=follow_history, tools=None
                ):
                    if cancel_event.is_set():
                        aborted = True
                        finish_reason_final = "cancelled"
                        yield _sse("stream.cancelled", {"request_id": request_id})
                        break
                    if ev.kind == "token" and ev.delta:
                        accumulated_text += ev.delta
                        yield _sse("token", {"delta": ev.delta})
                    elif ev.kind == "finish":
                        finish_reason_final = ev.finish_reason or "stop"
                        in_toks_total += ev.input_tokens or 0
                        out_toks_total += ev.output_tokens or 0
            except Exception as exc:  # pragma: no cover
                yield _sse("error", {"code": "runner_error", "message": str(exc)})
                finish_reason_final = "error"
            duration_ms += int((time.perf_counter() - follow_start) * 1000)

    # Final assistant persistence
    assistant = msg_repo.add_assistant_message(
        db,
        conversation_id=conv.id,
        request_id=request_id,
        parent_message_id=parent_for_step,
        content=[{"type": "text", "text": accumulated_text}],
        tool_calls=None,
        provider_snapshot=f"{model.provider_type.value}:{model.model_name}",
        input_tokens=in_toks_total or None,
        output_tokens=out_toks_total or None,
        cost_usd=_estimate_cost(model, in_toks_total or None, out_toks_total or None),
        latency_ms=duration_ms,
        finish_reason=_finish_reason(finish_reason_final),
    )
    conv.active_leaf_message_id = assistant.id
    db.commit()

    cost = _estimate_cost(model, in_toks_total or None, out_toks_total or None) or Decimal("0")
    yield _sse(
        "usage",
        {
            "input_tokens": in_toks_total,
            "output_tokens": out_toks_total,
            "cost_usd": float(cost),
            "message_id": assistant.id,
            "latency_ms": duration_ms,
        },
    )
    yield _sse(
        "stream.end",
        {"finish_reason": finish_reason_final, "assistant_message_id": assistant.id},
    )

    cancel_bus.clear(request_id)
