"""Per-user analytics endpoints — power the frontend analytics page."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models_db.message import Message, MessageRole
from app.models_db.user import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


class UsageSeriesPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date | None = None
    provider_snapshot: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    request_count: int = 0


class UsageResponse(BaseModel):
    series: list[UsageSeriesPoint]
    totals: UsageSeriesPoint


class ModelUsageRow(BaseModel):
    provider_snapshot: str | None
    request_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    avg_latency_ms: float | None


class ModelsUsageResponse(BaseModel):
    rows: list[ModelUsageRow]


def _parse_iso_date(v: str | None) -> datetime | None:
    if v is None:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.get("/usage", response_model=UsageResponse)
def usage(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    group_by: str = Query(default="day", pattern="^(day|model|day,model)$"),
) -> UsageResponse:
    now = datetime.now(tz=timezone.utc)
    start = _parse_iso_date(from_) or (now - timedelta(days=30))
    end = _parse_iso_date(to) or now

    q = (
        db.query(
            func.date(Message.created_at).label("d"),
            Message.provider_snapshot.label("model_snap"),
            func.coalesce(func.sum(Message.input_tokens), 0),
            func.coalesce(func.sum(Message.output_tokens), 0),
            func.coalesce(func.sum(Message.cost_usd), 0),
            func.count(Message.id),
        )
        .join(User, User.id == db.query(Message).subquery().c.conversation_id, isouter=True)
        .filter(False)  # placeholder — replaced below via explicit query
    )
    del q  # We'll do the direct query below for clarity.

    from app.models_db.conversation import Conversation

    base = (
        db.query(
            func.date(Message.created_at).label("d"),
            Message.provider_snapshot.label("model_snap"),
            func.coalesce(func.sum(Message.input_tokens), 0),
            func.coalesce(func.sum(Message.output_tokens), 0),
            func.coalesce(func.sum(Message.cost_usd), 0),
            func.count(Message.id),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            and_(
                Conversation.user_id == user.id,
                Message.role == MessageRole.assistant,
                Message.is_deleted.is_(False),
                Message.created_at >= start,
                Message.created_at < end,
            )
        )
    )

    if group_by == "day":
        rows = base.group_by(func.date(Message.created_at)).order_by(func.date(Message.created_at)).all()
        series = [
            UsageSeriesPoint(
                day=r[0] if isinstance(r[0], date) else _parse_date_str(str(r[0])),
                input_tokens=int(r[2] or 0),
                output_tokens=int(r[3] or 0),
                cost_usd=float(r[4] or 0),
                request_count=int(r[5] or 0),
            )
            for r in rows
        ]
    elif group_by == "model":
        rows = base.group_by(Message.provider_snapshot).all()
        series = [
            UsageSeriesPoint(
                provider_snapshot=r[1],
                input_tokens=int(r[2] or 0),
                output_tokens=int(r[3] or 0),
                cost_usd=float(r[4] or 0),
                request_count=int(r[5] or 0),
            )
            for r in rows
        ]
    else:  # day,model
        rows = base.group_by(func.date(Message.created_at), Message.provider_snapshot).order_by(
            func.date(Message.created_at)
        ).all()
        series = [
            UsageSeriesPoint(
                day=r[0] if isinstance(r[0], date) else _parse_date_str(str(r[0])),
                provider_snapshot=r[1],
                input_tokens=int(r[2] or 0),
                output_tokens=int(r[3] or 0),
                cost_usd=float(r[4] or 0),
                request_count=int(r[5] or 0),
            )
            for r in rows
        ]

    totals = UsageSeriesPoint(
        input_tokens=sum(p.input_tokens for p in series),
        output_tokens=sum(p.output_tokens for p in series),
        cost_usd=sum(p.cost_usd for p in series),
        request_count=sum(p.request_count for p in series),
    )
    return UsageResponse(series=series, totals=totals)


def _parse_date_str(s: str) -> date | None:
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


@router.get("/models", response_model=ModelsUsageResponse)
def usage_by_model(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ModelsUsageResponse:
    from app.models_db.conversation import Conversation

    rows = (
        db.query(
            Message.provider_snapshot,
            func.count(Message.id),
            func.coalesce(func.sum(Message.input_tokens), 0),
            func.coalesce(func.sum(Message.output_tokens), 0),
            func.coalesce(func.sum(Message.cost_usd), 0),
            func.avg(Message.latency_ms),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            and_(
                Conversation.user_id == user.id,
                Message.role == MessageRole.assistant,
                Message.is_deleted.is_(False),
            )
        )
        .group_by(Message.provider_snapshot)
        .all()
    )
    return ModelsUsageResponse(
        rows=[
            ModelUsageRow(
                provider_snapshot=r[0],
                request_count=int(r[1] or 0),
                input_tokens=int(r[2] or 0),
                output_tokens=int(r[3] or 0),
                cost_usd=float(r[4] or 0),
                avg_latency_ms=float(r[5]) if r[5] is not None else None,
            )
            for r in rows
        ]
    )
