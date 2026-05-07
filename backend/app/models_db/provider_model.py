"""BYOM provider model configuration."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import EncryptedJSON, EncryptedString, UUIDString


class ProviderType(str, enum.Enum):
    openai = "openai"
    openai_compatible = "openai_compatible"
    azure = "azure"
    anthropic = "anthropic"
    gemini = "gemini"
    ollama = "ollama"


class ProviderModel(Base):
    __tablename__ = "provider_models"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType, native_enum=False, length=32), nullable=False
    )
    endpoint_url: Mapped[str | None] = mapped_column(String(1024))
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    api_version: Mapped[str | None] = mapped_column(
        String(40), nullable=True,
        doc="Azure OpenAI api-version query param (e.g. '2025-01-01-preview')",
    )
    api_key_encrypted: Mapped[str | None] = mapped_column(EncryptedString)
    extra_headers_encrypted: Mapped[dict | None] = mapped_column(EncryptedJSON)
    default_system_prompt: Mapped[str | None] = mapped_column(Text)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    context_window_tokens: Mapped[int | None] = mapped_column(Integer)
    price_input_per_mtok_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    price_output_per_mtok_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
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
