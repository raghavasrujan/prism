"""Messages repository."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models_db.message import FinishReason, Message, MessageRole
from app.security import new_uuid


def list_for_conversation(db: Session, conv_id: str, *, include_deleted: bool = False):
    stmt = select(Message).where(Message.conversation_id == conv_id)
    if not include_deleted:
        stmt = stmt.where(Message.is_deleted.is_(False))
    return db.execute(stmt.order_by(Message.created_at.asc())).scalars().all()


def get(db: Session, message_id: str) -> Message | None:
    return db.get(Message, message_id)


def add_user_message(
    db: Session,
    *,
    conversation_id: str,
    request_id: str,
    content: list[dict],
    parent_message_id: str | None = None,
) -> Message:
    msg = Message(
        id=new_uuid(),
        conversation_id=conversation_id,
        request_id=request_id,
        parent_message_id=parent_message_id,
        role=MessageRole.user,
        content_json=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def add_assistant_message(
    db: Session,
    *,
    conversation_id: str,
    request_id: str,
    parent_message_id: str,
    content: list[dict],
    tool_calls: list[dict] | None,
    provider_snapshot: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: Decimal | None,
    latency_ms: int | None,
    finish_reason: FinishReason,
    error_message: str | None = None,
) -> Message:
    msg = Message(
        id=new_uuid(),
        conversation_id=conversation_id,
        request_id=request_id,
        parent_message_id=parent_message_id,
        role=MessageRole.assistant,
        content_json=content,
        tool_calls_json=tool_calls,
        provider_snapshot=provider_snapshot,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
        error_message=error_message,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def add_tool_result(
    db: Session,
    *,
    conversation_id: str,
    request_id: str,
    parent_message_id: str,
    tool_call_id: str,
    tool_name: str,
    content: list[dict],
) -> Message:
    msg = Message(
        id=new_uuid(),
        conversation_id=conversation_id,
        request_id=request_id,
        parent_message_id=parent_message_id,
        role=MessageRole.tool,
        content_json=content,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def usage_for_conversation(db: Session, conv_id: str) -> dict:
    stmt = select(
        func.coalesce(func.sum(Message.input_tokens), 0),
        func.coalesce(func.sum(Message.output_tokens), 0),
        func.coalesce(func.sum(Message.cost_usd), 0),
        func.count(Message.id),
    ).where(
        and_(
            Message.conversation_id == conv_id,
            Message.is_deleted.is_(False),
            Message.role == MessageRole.assistant,
        )
    )
    row = db.execute(stmt).one()
    return {
        "input_tokens": int(row[0] or 0),
        "output_tokens": int(row[1] or 0),
        "cost_usd": float(row[2] or 0),
        "message_count": int(row[3] or 0),
    }


def usage_by_model_for_conversation(db: Session, conv_id: str) -> list[dict]:
    stmt = (
        select(
            Message.provider_snapshot,
            func.coalesce(func.sum(Message.input_tokens), 0),
            func.coalesce(func.sum(Message.output_tokens), 0),
            func.coalesce(func.sum(Message.cost_usd), 0),
            func.count(Message.id),
        )
        .where(
            and_(
                Message.conversation_id == conv_id,
                Message.is_deleted.is_(False),
                Message.role == MessageRole.assistant,
            )
        )
        .group_by(Message.provider_snapshot)
    )
    return [
        {
            "model_snapshot": r[0],
            "provider_model_id": None,
            "input_tokens": int(r[1] or 0),
            "output_tokens": int(r[2] or 0),
            "cost_usd": float(r[3] or 0),
            "message_count": int(r[4] or 0),
        }
        for r in db.execute(stmt).all()
    ]
