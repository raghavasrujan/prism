"""Conversation repository."""

from __future__ import annotations

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.models_db.conversation import (
    Conversation,
    ConversationMcpServer,
    ConversationTool,
)


def list_for_user(db: Session, user_id: str, *, include_deleted: bool = False):
    stmt = select(Conversation).where(Conversation.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Conversation.is_deleted.is_(False))
    return db.execute(stmt.order_by(Conversation.updated_at.desc())).scalars().all()


def get_for_user(db: Session, user_id: str, conv_id: str) -> Conversation | None:
    stmt = select(Conversation).where(
        and_(
            Conversation.id == conv_id,
            Conversation.user_id == user_id,
            Conversation.is_deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_by_share_slug(db: Session, slug: str) -> Conversation | None:
    stmt = select(Conversation).where(
        and_(Conversation.share_slug == slug, Conversation.is_shared.is_(True))
    )
    return db.execute(stmt).scalar_one_or_none()


def create(
    db: Session,
    *,
    user_id: str,
    provider_model_id: str,
    title: str | None,
    system_prompt_override: str | None,
) -> Conversation:
    conv = Conversation(
        user_id=user_id,
        provider_model_id=provider_model_id,
        title=title,
        system_prompt_override=system_prompt_override,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def replace_tools(db: Session, conv_id: str, tool_ids: list[str]) -> None:
    db.execute(delete(ConversationTool).where(ConversationTool.conversation_id == conv_id))
    for tid in tool_ids:
        db.add(ConversationTool(conversation_id=conv_id, tool_id=tid, enabled=True))
    db.commit()


def replace_mcps(db: Session, conv_id: str, mcp_ids: list[str]) -> None:
    db.execute(
        delete(ConversationMcpServer).where(ConversationMcpServer.conversation_id == conv_id)
    )
    for mid in mcp_ids:
        db.add(ConversationMcpServer(conversation_id=conv_id, mcp_server_id=mid, enabled=True))
    db.commit()


def get_tool_ids(db: Session, conv_id: str) -> list[str]:
    stmt = select(ConversationTool.tool_id).where(
        and_(ConversationTool.conversation_id == conv_id, ConversationTool.enabled.is_(True))
    )
    return [r[0] for r in db.execute(stmt).all()]


def get_mcp_ids(db: Session, conv_id: str) -> list[str]:
    stmt = select(ConversationMcpServer.mcp_server_id).where(
        and_(
            ConversationMcpServer.conversation_id == conv_id,
            ConversationMcpServer.enabled.is_(True),
        )
    )
    return [r[0] for r in db.execute(stmt).all()]


def soft_delete(db: Session, conv: Conversation) -> None:
    conv.is_deleted = True
    db.commit()
