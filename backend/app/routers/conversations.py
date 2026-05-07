"""Conversations CRUD + share + usage."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models_db.audit import AuditAction
from app.models_db.message import MessageRole
from app.models_db.user import User
from app.repositories import conversations as conv_repo
from app.repositories import messages as msg_repo
from app.repositories import provider_models as pm_repo
from app.schemas.conversation import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    ConversationUsage,
    ConversationUsageByModel,
    ShareOut,
)
from app.services.audit_service import record
from app.services.providers import get_provider

_log = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_out(db, conv) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        provider_model_id=conv.provider_model_id,
        system_prompt_override=conv.system_prompt_override,
        active_leaf_message_id=conv.active_leaf_message_id,
        is_shared=conv.is_shared,
        share_slug=conv.share_slug,
        tool_ids=conv_repo.get_tool_ids(db, conv.id),
        mcp_server_ids=conv_repo.get_mcp_ids(db, conv.id),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    return [_to_out(db, c) for c in conv_repo.list_for_user(db, user.id)]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    model = pm_repo.get_for_user(db, user.id, body.provider_model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    conv = conv_repo.create(
        db,
        user_id=user.id,
        provider_model_id=body.provider_model_id,
        title=body.title,
        system_prompt_override=body.system_prompt_override,
    )
    if body.tool_ids:
        conv_repo.replace_tools(db, conv.id, body.tool_ids)
    if body.mcp_server_ids:
        conv_repo.replace_mcps(db, conv.id, body.mcp_server_ids)
    record(
        db,
        action=AuditAction.conversation_created,
        user_id=user.id,
        resource_type="conversation",
        resource_id=conv.id,
    )
    return _to_out(db, conv)


@router.get("/{conv_id}", response_model=ConversationOut)
def get_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_out(db, conv)


@router.patch("/{conv_id}", response_model=ConversationOut)
def update_conversation(
    conv_id: str,
    body: ConversationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationOut:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "system_prompt_override", "provider_model_id"):
        if field in data:
            setattr(conv, field, data[field])
    if "tool_ids" in data:
        conv_repo.replace_tools(db, conv.id, data["tool_ids"])
    if "mcp_server_ids" in data:
        conv_repo.replace_mcps(db, conv.id, data["mcp_server_ids"])
    db.commit()
    db.refresh(conv)
    record(
        db,
        action=AuditAction.conversation_updated,
        user_id=user.id,
        resource_type="conversation",
        resource_id=conv.id,
    )
    return _to_out(db, conv)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    conv_repo.soft_delete(db, conv)
    record(
        db,
        action=AuditAction.conversation_deleted,
        user_id=user.id,
        resource_type="conversation",
        resource_id=conv.id,
    )


@router.post("/{conv_id}/share", response_model=ShareOut)
def share_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShareOut:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not conv.share_slug:
        conv.share_slug = secrets.token_urlsafe(16)
    conv.is_shared = True
    db.commit()
    record(
        db,
        action=AuditAction.conversation_shared,
        user_id=user.id,
        resource_type="conversation",
        resource_id=conv.id,
    )
    return ShareOut(slug=conv.share_slug, url_path=f"/share/{conv.share_slug}")


@router.delete("/{conv_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def unshare_conversation(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    conv.is_shared = False
    db.commit()
    record(
        db,
        action=AuditAction.conversation_unshared,
        user_id=user.id,
        resource_type="conversation",
        resource_id=conv.id,
    )


@router.get("/{conv_id}/usage", response_model=ConversationUsage)
def conversation_usage(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationUsage:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    totals = msg_repo.usage_for_conversation(db, conv.id)
    by_model = [
        ConversationUsageByModel(**row) for row in msg_repo.usage_by_model_for_conversation(db, conv.id)
    ]
    return ConversationUsage(**totals, by_model=by_model)


@router.post("/{conv_id}/generate-title")
async def generate_title(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Ask the conversation's model to suggest a short title based on the first exchange.

    Silently no-ops if the conversation already has a non-default title, if no
    messages exist yet, or if the provider call fails — the caller should treat
    this as best-effort.
    """
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Don't overwrite a title the user has set manually.
    if conv.title and conv.title not in ("", "Untitled", "New conversation"):
        _log.info("conversation.generate_title.skipped", conv_id=conv_id, reason="already_titled", title=conv.title)
        return {"title": conv.title}

    # Prefer the user's dedicated title-generation model when configured;
    # otherwise fall back to the conversation's own model so the feature
    # keeps working without extra setup.
    model = None
    if user.title_provider_model_id:
        model = pm_repo.get_for_user(db, user.id, user.title_provider_model_id)
    if model is None:
        model = pm_repo.get_for_user(db, user.id, conv.provider_model_id)
    if model is None:
        _log.warning("conversation.generate_title.skipped", conv_id=conv_id, reason="no_model",
                     provider_model_id=conv.provider_model_id)
        return {"title": conv.title or "New conversation"}

    messages_list = msg_repo.list_for_conversation(db, conv.id)
    user_msgs = [m for m in messages_list if m.role == MessageRole.user]
    asst_msgs = [m for m in messages_list if m.role == MessageRole.assistant]

    if not user_msgs:
        _log.warning("conversation.generate_title.skipped", conv_id=conv_id, reason="no_messages")
        return {"title": conv.title or "New conversation"}

    def _extract(msg) -> str:
        parts = msg.content_json or []
        texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return " ".join(texts)[:400]

    user_text = _extract(user_msgs[0])
    asst_text = _extract(asst_msgs[0]) if asst_msgs else ""

    _log.info("conversation.generate_title.start", conv_id=conv_id,
              model=model.model_name, user_text_len=len(user_text))

    provider = get_provider(model)
    try:
        resp = await provider.chat(
            model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Generate a concise 4-6 word title for this conversation. "
                        "Reply with ONLY the title — no quotes, no ending punctuation.\n\n"
                        f"User: {user_text}"
                        + (f"\nAssistant: {asst_text}" if asst_text else "")
                    ),
                }
            ],
            tools=None,
            max_tokens=500,
        )
        raw = resp.content or ""
        title = raw.strip().strip("`\"'").rstrip(".!?").strip()
        _log.info("conversation.generate_title.raw", conv_id=conv_id, raw=raw[:200], title=title)
        if title:
            conv.title = title[:120]
            db.commit()
            _log.info("conversation.title_generated", conv_id=conv_id, title=title)
        else:
            _log.warning("conversation.generate_title.empty", conv_id=conv_id, raw=raw[:200])
    except Exception as exc:
        _log.warning("conversation.generate_title.failed", conv_id=conv_id, error=str(exc))

    return {"title": conv.title or "New conversation"}
