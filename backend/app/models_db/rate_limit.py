"""Sliding-window rate-limit counters (DB-backed v1)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import UUIDString


class RateLimitScope(str, enum.Enum):
    chat_send = "chat_send"
    chat_stream = "chat_stream"
    model_create = "model_create"
    tool_create = "tool_create"
    tool_exec = "tool_exec"
    mcp_create = "mcp_create"
    upload_create = "upload_create"


class RateLimitWindow(Base):
    __tablename__ = "rate_limit_windows"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[RateLimitScope] = mapped_column(
        Enum(RateLimitScope, native_enum=False, length=32), nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        Index(
            "uq_rate_limit_windows",
            "user_id",
            "scope",
            "window_start",
            "window_seconds",
            unique=True,
        ),
    )
