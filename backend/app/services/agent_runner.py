"""Non-streaming agent runner.

Orchestrates: system prompt → user message → model call → optional tool loop →
final assistant message. Persists every message with correlation IDs, and rolls
up token / cost accounting.

Streaming variant lives in ``agent_stream.py`` (Phase 3c).
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models_db.attachment import Attachment, AttachmentKind
from app.models_db.conversation import Conversation
from app.models_db.custom_tool import CustomTool
from app.models_db.mcp_server import McpServer, McpToolCache
from app.models_db.message import FinishReason, Message, MessageRole
from app.models_db.provider_model import ProviderModel
from app.repositories import conversations as conv_repo
from app.repositories import custom_tools as tool_repo
from app.repositories import mcp as mcp_repo
from app.repositories import messages as msg_repo
from app.security import new_uuid
from app.services.mcp_client import McpHttpClient
from app.services.providers import get_provider
from app.services.storage_adapter import get_storage
from app.services.tool_executor import execute_tool

_log = get_logger(__name__)

MAX_TOOL_ITERATIONS = 6


@dataclass
class AgentTurnResult:
    request_id: str
    user_message: Message
    assistant_message: Message
    tool_messages: list[Message]
    usage: dict[str, Any]


def _content_to_parts(content: str | list[dict]) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content


def _parts_to_openai_content(parts: list[dict]) -> str | list[dict]:
    # If parts is a single text block, collapse to string (many providers prefer this).
    if len(parts) == 1 and parts[0].get("type") == "text":
        return parts[0].get("text", "")
    return parts


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f}KB"
    return f"{n / (1024 * 1024):.1f}MB"


def _attachment_content_parts(db: Session, user_id: str, attachment_ids: list[str]) -> list[dict]:
    """Turn newly-uploaded attachment ids into content parts appended to a
    user message.

    Images become a lightweight ``attachment://{id}`` reference — resolved to
    a real base64 data-URL only when a provider request is actually built
    (see ``_resolve_attachment_refs``) — so the database never stores image
    bytes twice. There's no generic "file" content type in the
    chat-completions wire format, so non-image files are represented as a
    short text mention instead of being silently dropped.
    """
    if not attachment_ids:
        return []
    rows = db.execute(select(Attachment).where(Attachment.id.in_(attachment_ids))).scalars().all()
    by_id = {a.id: a for a in rows}
    parts: list[dict] = []
    for aid in attachment_ids:
        att = by_id.get(aid)
        if att is None or att.user_id != user_id:
            continue
        if att.kind == AttachmentKind.image:
            parts.append({"type": "image_url", "image_url": {"url": f"attachment://{att.id}"}})
        else:
            parts.append(
                {"type": "text", "text": f"[Attached file: {att.filename} ({_human_size(att.size_bytes)})]"}
            )
    return parts


def _link_attachments(db: Session, attachment_ids: list[str], message_id: str) -> None:
    """Point each attachment row at the message it was sent with."""
    if not attachment_ids:
        return
    db.execute(update(Attachment).where(Attachment.id.in_(attachment_ids)).values(message_id=message_id))
    db.commit()


def _resolve_attachment_refs(db: Session, parts: list[dict] | None) -> list[dict]:
    """Expand ``attachment://{id}`` image references into real base64
    data-URLs right before a provider call. Keeps the persisted message copy
    lightweight — only the outbound wire payload ever carries actual bytes.
    """
    if not parts:
        return parts or []
    resolved: list[dict] = []
    for p in parts:
        if p.get("type") == "image_url":
            url = (p.get("image_url") or {}).get("url", "")
            if url.startswith("attachment://"):
                att = db.get(Attachment, url.removeprefix("attachment://"))
                if att is not None:
                    try:
                        data = get_storage().read(att.storage_path)
                    except FileNotFoundError:
                        continue  # attachment row survived but the file didn't — drop it
                    b64 = base64.b64encode(data).decode("ascii")
                    resolved.append(
                        {"type": "image_url", "image_url": {"url": f"data:{att.mime_type};base64,{b64}"}}
                    )
                continue
        resolved.append(p)
    return resolved


def _build_history(db: Session, conv: Conversation, model: ProviderModel) -> list[dict]:
    """Compose OpenAI-shape messages for the current visible thread."""
    history: list[dict] = []

    system_text = conv.system_prompt_override or model.default_system_prompt
    if system_text:
        history.append({"role": "system", "content": system_text})

    for m in msg_repo.list_for_conversation(db, conv.id):
        if m.role == MessageRole.system:
            continue
        if m.role == MessageRole.user:
            resolved = _resolve_attachment_refs(db, m.content_json)
            history.append({"role": "user", "content": _parts_to_openai_content(resolved)})
        elif m.role == MessageRole.assistant:
            entry: dict[str, Any] = {"role": "assistant"}
            text = ""
            if m.content_json:
                for p in m.content_json:
                    if p.get("type") == "text":
                        text += p.get("text", "")
            entry["content"] = text or None
            if m.tool_calls_json:
                entry["tool_calls"] = [
                    {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name"),
                            "arguments": _stringify_args(tc.get("arguments") or {}),
                        },
                    }
                    for tc in m.tool_calls_json
                ]
            history.append(entry)
        elif m.role == MessageRole.tool:
            entry = {
                "role": "tool",
                "tool_call_id": m.tool_call_id,
                "content": _content_to_text(m.content_json),
            }
            history.append(entry)
    return history


def _stringify_args(args: dict) -> str:
    import json as _json

    return _json.dumps(args, default=str)


def _content_to_text(parts: list[dict]) -> str:
    if isinstance(parts, str):
        return parts
    out = []
    for p in parts or []:
        if p.get("type") == "text":
            out.append(p.get("text", ""))
        else:
            out.append(str(p))
    return "".join(out)


def _tool_schemas_for(
    db: Session, conv_id: str
) -> tuple[list[dict], dict[str, CustomTool], dict[tuple[str, str], tuple[McpServer, McpToolCache]]]:
    """Return OpenAI-format tool schemas, plus lookup tables the runner uses to dispatch."""
    tool_ids = conv_repo.get_tool_ids(db, conv_id)
    mcp_ids = conv_repo.get_mcp_ids(db, conv_id)

    schemas: list[dict] = []
    custom_by_name: dict[str, CustomTool] = {}
    mcp_by_name: dict[tuple[str, str], tuple[McpServer, McpToolCache]] = {}

    for tid in tool_ids:
        t = tool_repo.get_for_user(db, conv_repo.get_for_user(db, "", "").user_id if False else "", tid)  # placeholder
    # ^ we need user_id — pull it from the conversation
    conv = db.get(Conversation, conv_id)
    if conv is None:
        return [], {}, {}

    for tid in tool_ids:
        t = tool_repo.get_for_user(db, conv.user_id, tid)
        if t is None or not t.is_active:
            continue
        schemas.append(
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema_json or {"type": "object"},
            }
        )
        custom_by_name[t.name] = t

    for sid in mcp_ids:
        server = mcp_repo.get_for_user(db, conv.user_id, sid)
        if server is None or not server.is_active:
            continue
        for cached in mcp_repo.list_cached_tools(db, server.id):
            qname = cached.tool_name  # MCP tool name is directly used; prefix collision → last wins
            schemas.append(
                {
                    "name": qname,
                    "description": cached.description or f"MCP tool {qname}",
                    "parameters": cached.args_schema_json or {"type": "object"},
                }
            )
            mcp_by_name[(server.id, qname)] = (server, cached)
    return schemas, custom_by_name, mcp_by_name


async def _run_tool(
    name: str,
    args: dict,
    custom_by_name: dict[str, CustomTool],
    mcp_by_name: dict[tuple[str, str], tuple[McpServer, McpToolCache]],
) -> tuple[bool, str]:
    """Dispatch a tool call. Returns (ok, result-as-text)."""
    if name in custom_by_name:
        res = await execute_tool(custom_by_name[name], args)
        text = _summarise_tool_output(res.result if res.ok else res.error or "tool error")
        return res.ok, text
    for (_sid, tool_name), (server, _) in mcp_by_name.items():
        if tool_name == name:
            client = McpHttpClient(url=server.url, headers=server.headers_encrypted or None)
            try:
                out = await client.call_tool(name, args)
                return True, _summarise_tool_output(out)
            except Exception as exc:  # pragma: no cover
                return False, f"MCP tool error: {exc}"
    return False, f"Unknown tool: {name}"


def _summarise_tool_output(output: Any) -> str:
    import json as _json

    if isinstance(output, str):
        return output[:8192]
    try:
        return _json.dumps(output, default=str)[:8192]
    except Exception:  # pragma: no cover
        return str(output)[:8192]


def _estimate_cost(model: ProviderModel, in_toks: int | None, out_toks: int | None) -> Decimal | None:
    if not in_toks and not out_toks:
        return None
    total = Decimal(0)
    if model.price_input_per_mtok_usd is not None and in_toks:
        total += Decimal(in_toks) * model.price_input_per_mtok_usd / Decimal(1_000_000)
    if model.price_output_per_mtok_usd is not None and out_toks:
        total += Decimal(out_toks) * model.price_output_per_mtok_usd / Decimal(1_000_000)
    return total.quantize(Decimal("0.000001"))


async def run_turn(
    db: Session,
    *,
    conv: Conversation,
    model: ProviderModel,
    user_content: str | list[dict],
    parent_message_id: str | None = None,
    attachment_ids: list[str] | None = None,
) -> AgentTurnResult:
    request_id = new_uuid()

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

    tool_schemas, custom_by_name, mcp_by_name = _tool_schemas_for(db, conv.id)
    provider = get_provider(model)

    turn_input_tokens = 0
    turn_output_tokens = 0
    turn_latency_ms = 0
    tool_messages: list[Message] = []

    parent_for_step: str = user_msg.id

    final_content = ""
    final_finish = "stop"
    final_tool_calls: list[dict] | None = None

    for iteration in range(MAX_TOOL_ITERATIONS):
        history = _build_history(db, conv, model)
        start = time.perf_counter()
        try:
            resp = await provider.chat(
                model,
                messages=history,
                tools=tool_schemas or None,
            )
        except Exception as exc:  # pragma: no cover
            _log.exception("agent.provider.error", error=str(exc))
            assistant = msg_repo.add_assistant_message(
                db,
                conversation_id=conv.id,
                request_id=request_id,
                parent_message_id=parent_for_step,
                content=[{"type": "text", "text": ""}],
                tool_calls=None,
                provider_snapshot=f"{model.provider_type.value}:{model.model_name}",
                input_tokens=None,
                output_tokens=None,
                cost_usd=None,
                latency_ms=int((time.perf_counter() - start) * 1000),
                finish_reason=FinishReason.error,
                error_message=str(exc),
            )
            usage = msg_repo.usage_for_conversation(db, conv.id)
            return AgentTurnResult(
                request_id=request_id,
                user_message=user_msg,
                assistant_message=assistant,
                tool_messages=tool_messages,
                usage=usage,
            )

        turn_latency_ms += int((time.perf_counter() - start) * 1000)
        turn_input_tokens += resp.input_tokens or 0
        turn_output_tokens += resp.output_tokens or 0
        final_content = resp.content
        final_finish = resp.finish_reason
        final_tool_calls = resp.tool_calls or None

        if not resp.tool_calls:
            break

        # Persist assistant tool-call announcement
        assistant_step = msg_repo.add_assistant_message(
            db,
            conversation_id=conv.id,
            request_id=request_id,
            parent_message_id=parent_for_step,
            content=[{"type": "text", "text": resp.content or ""}],
            tool_calls=resp.tool_calls,
            provider_snapshot=resp.provider_snapshot,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=_estimate_cost(model, resp.input_tokens, resp.output_tokens),
            latency_ms=int((time.perf_counter() - start) * 1000),
            finish_reason=FinishReason.tool_calls,
        )
        parent_for_step = assistant_step.id

        for tc in resp.tool_calls:
            ok, text = await _run_tool(
                tc.get("name") or "",
                tc.get("arguments") or {},
                custom_by_name,
                mcp_by_name,
            )
            tm = msg_repo.add_tool_result(
                db,
                conversation_id=conv.id,
                request_id=request_id,
                parent_message_id=parent_for_step,
                tool_call_id=tc.get("id") or new_uuid(),
                tool_name=tc.get("name") or "unknown",
                content=[{"type": "text", "text": text}],
            )
            tool_messages.append(tm)
            parent_for_step = tm.id
            _log.info(
                "agent.tool_call.done",
                tool_name=tc.get("name"),
                ok=ok,
                iteration=iteration,
            )
    else:
        _log.warning("agent.tool_loop.max_iterations", conv_id=conv.id)

    assistant = msg_repo.add_assistant_message(
        db,
        conversation_id=conv.id,
        request_id=request_id,
        parent_message_id=parent_for_step,
        content=[{"type": "text", "text": final_content or ""}],
        tool_calls=final_tool_calls if final_finish == FinishReason.tool_calls.value else None,
        provider_snapshot=f"{model.provider_type.value}:{model.model_name}",
        input_tokens=turn_input_tokens or None,
        output_tokens=turn_output_tokens or None,
        cost_usd=_estimate_cost(model, turn_input_tokens or None, turn_output_tokens or None),
        latency_ms=turn_latency_ms,
        finish_reason=_finish_reason(final_finish),
    )

    conv.active_leaf_message_id = assistant.id
    db.commit()

    usage = msg_repo.usage_for_conversation(db, conv.id)
    return AgentTurnResult(
        request_id=request_id,
        user_message=user_msg,
        assistant_message=assistant,
        tool_messages=tool_messages,
        usage=usage,
    )


def _finish_reason(text: str) -> FinishReason:
    mapping = {
        "stop": FinishReason.stop,
        "length": FinishReason.length,
        "tool_calls": FinishReason.tool_calls,
        "content_filter": FinishReason.content_filter,
    }
    return mapping.get(text, FinishReason.stop)
