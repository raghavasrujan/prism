"""Messages (tree structure via parent_message_id for branching)."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import UUIDString


class MessageRole(str, enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class FinishReason(str, enum.Enum):
    stop = "stop"
    length = "length"
    tool_calls = "tool_calls"
    content_filter = "content_filter"
    error = "error"
    cancelled = "cancelled"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(UUIDString, nullable=False, index=True)
    parent_message_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("messages.id", ondelete="SET NULL")
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, native_enum=False, length=16), nullable=False
    )

    content_json: Mapped[list] = mapped_column(JSON, nullable=False)
    tool_calls_json: Mapped[list | None] = mapped_column(JSON)
    tool_call_id: Mapped[str | None] = mapped_column(String(200))
    tool_name: Mapped[str | None] = mapped_column(String(200))

    provider_snapshot: Mapped[str | None] = mapped_column(String(200))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    finish_reason: Mapped[FinishReason | None] = mapped_column(
        Enum(FinishReason, native_enum=False, length=32)
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
        Index("ix_messages_parent", "parent_message_id"),
        Index("ix_messages_request", "request_id"),
    )
