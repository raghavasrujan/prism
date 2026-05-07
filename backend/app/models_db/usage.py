"""Usage rollup (per user, model, day) — populated by background job."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.security import new_uuid
from app.types_db import UUIDString


class UsageDailySummary(Base):
    __tablename__ = "usage_daily_summary"

    id: Mapped[str] = mapped_column(UUIDString, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        UUIDString, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_model_id: Mapped[str | None] = mapped_column(
        UUIDString, ForeignKey("provider_models.id", ondelete="SET NULL")
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_usage_daily", "user_id", "provider_model_id", "day", unique=True),
        Index("ix_usage_daily_user_day", "user_id", "day"),
    )
