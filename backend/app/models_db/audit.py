"""Audit log."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import UUIDString


class AuditAction(str, enum.Enum):
    auth_login = "auth_login"
    auth_login_failed = "auth_login_failed"
    auth_logout = "auth_logout"
    auth_refresh = "auth_refresh"
    auth_refresh_reuse_detected = "auth_refresh_reuse_detected"
    user_created = "user_created"
    user_updated = "user_updated"
    model_created = "model_created"
    model_updated = "model_updated"
    model_deleted = "model_deleted"
    tool_created = "tool_created"
    tool_updated = "tool_updated"
    tool_deleted = "tool_deleted"
    mcp_created = "mcp_created"
    mcp_updated = "mcp_updated"
    mcp_deleted = "mcp_deleted"
    conversation_created = "conversation_created"
    conversation_updated = "conversation_updated"
    conversation_deleted = "conversation_deleted"
    conversation_shared = "conversation_shared"
    conversation_unshared = "conversation_unshared"
    message_sent = "message_sent"
    message_cancelled = "message_cancelled"
    admin_user_updated = "admin_user_updated"
    rate_limit_hit = "rate_limit_hit"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False, length=64), nullable=False
    )
    resource_type: Mapped[str | None] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(UUIDString)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    details_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_action_created", "action", "created_at"),
    )
