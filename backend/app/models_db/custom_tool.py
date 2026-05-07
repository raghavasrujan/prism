"""Custom user tools — HTTP webhook or Python inline (sandboxed)."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import EncryptedJSON, EncryptedString, UUIDString


class ToolImplType(str, enum.Enum):
    http = "http"
    python_inline = "python_inline"


class SandboxRuntime(str, enum.Enum):
    python3_14 = "python3.14"


class CustomTool(Base):
    __tablename__ = "custom_tools"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    args_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    impl_type: Mapped[ToolImplType] = mapped_column(
        Enum(ToolImplType, native_enum=False, length=32),
        default=ToolImplType.http,
        nullable=False,
    )

    # HTTP impl fields
    endpoint_url: Mapped[str | None] = mapped_column(String(1024))
    method: Mapped[str | None] = mapped_column(String(10))
    headers_encrypted: Mapped[dict | None] = mapped_column(EncryptedJSON)

    # Python inline impl fields
    code_source_encrypted: Mapped[str | None] = mapped_column(EncryptedString)
    runtime: Mapped[SandboxRuntime | None] = mapped_column(
        Enum(SandboxRuntime, native_enum=False, length=32)
    )
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256, nullable=False)
    cpu_time_limit_s: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    network_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_env_json: Mapped[dict | None] = mapped_column(JSON)

    # Common
    timeout_ms: Mapped[int] = mapped_column(Integer, default=30000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
