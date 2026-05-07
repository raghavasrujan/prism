"""Per-user rate limiting service — sliding window counters in the DB.

Swap-point for Redis in Phase 6+: only the ``check_and_increment`` function
needs to change.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models_db.rate_limit import RateLimitScope, RateLimitWindow
from app.security import new_uuid

_log = get_logger(__name__)


def _window_start(scope_seconds: int, now: datetime) -> datetime:
    epoch = int(now.timestamp())
    aligned = epoch - (epoch % scope_seconds)
    return datetime.fromtimestamp(aligned, tz=timezone.utc)


def check_and_increment(
    db: Session,
    *,
    user_id: str,
    scope: RateLimitScope,
    window_seconds: int,
    limit: int,
) -> tuple[bool, int, int]:
    """Returns ``(allowed, current_count, seconds_until_reset)``."""
    now = datetime.now(tz=timezone.utc)
    ws = _window_start(window_seconds, now)
    stmt = select(RateLimitWindow).where(
        and_(
            RateLimitWindow.user_id == user_id,
            RateLimitWindow.scope == scope,
            RateLimitWindow.window_start == ws,
            RateLimitWindow.window_seconds == window_seconds,
        )
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        row = RateLimitWindow(
            id=new_uuid(),
            user_id=user_id,
            scope=scope,
            window_start=ws,
            window_seconds=window_seconds,
            count=0,
        )
        db.add(row)
        db.flush()

    if row.count >= limit:
        reset_in = int((ws + timedelta(seconds=window_seconds) - now).total_seconds())
        return False, row.count, max(reset_in, 1)

    row.count += 1
    db.commit()
    return True, row.count, window_seconds


def enforce(
    db: Session,
    *,
    user_id: str,
    scope: RateLimitScope,
    per_minute: int | None = None,
    per_hour: int | None = None,
) -> None:
    """Raises HTTP 429 if either bucket is exceeded."""
    from fastapi import HTTPException, status

    if per_minute is not None:
        ok, count, reset = check_and_increment(
            db, user_id=user_id, scope=scope, window_seconds=60, limit=per_minute
        )
        if not ok:
            _log.warning("rate_limit.hit", scope=scope.value, window="1m", count=count)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {per_minute}/minute",
                headers={"Retry-After": str(reset), "X-RateLimit-Remaining": "0"},
            )
    if per_hour is not None:
        ok, count, reset = check_and_increment(
            db, user_id=user_id, scope=scope, window_seconds=3600, limit=per_hour
        )
        if not ok:
            _log.warning("rate_limit.hit", scope=scope.value, window="1h", count=count)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {per_hour}/hour",
                headers={"Retry-After": str(reset), "X-RateLimit-Remaining": "0"},
            )
