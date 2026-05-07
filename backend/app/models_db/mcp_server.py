"""Remote MCP servers + discovered-tool cache."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import EncryptedJSON, UUIDString


class McpTransport(str, enum.Enum):
    http = "http"
    sse = "sse"


class McpServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    transport: Mapped[McpTransport] = mapped_column(
        Enum(McpTransport, native_enum=False, length=16), nullable=False
    )
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    headers_encrypted: Mapped[dict | None] = mapped_column(EncryptedJSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_probed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_probe_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_probe_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class McpToolCache(Base):
    __tablename__ = "mcp_tool_cache"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    mcp_server_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    args_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_mcp_tool_cache", "mcp_server_id", "tool_name", unique=True),
    )
