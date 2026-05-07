"""Conversations + link tables to tools/MCP servers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import UUIDString


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(200))
    provider_model_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("provider_models.id"), nullable=False
    )
    system_prompt_override: Mapped[str | None] = mapped_column(Text)
    active_leaf_message_id: Mapped[str | None] = mapped_column(UUIDString)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    share_slug: Mapped[str | None] = mapped_column(String(64), unique=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_conv_user_updated", "user_id", "is_deleted", "updated_at"),)


class ConversationTool(Base):
    __tablename__ = "conversation_tools"

    conversation_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tool_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("custom_tools.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ConversationMcpServer(Base):
    __tablename__ = "conversation_mcp_servers"

    conversation_id: Mapped[str] = mapped_column(
        UUIDString,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mcp_server_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("mcp_servers.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
