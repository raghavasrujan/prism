"""Refresh-token repository with rotation family + reuse detection."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.models_db.refresh_token import RefreshToken
from app.security import new_uuid, now_utc, token_hash


def create(
    db: Session,
    *,
    user_id: str,
    raw_token: str,
    expires_at: datetime,
    family_id: str | None = None,
    parent_id: str | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> RefreshToken:
    rt = RefreshToken(
        id=new_uuid(),
        user_id=user_id,
        token_hash=token_hash(raw_token),
        family_id=family_id or new_uuid(),
        parent_id=parent_id,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(rt)
    db.commit()
    db.refresh(rt)
    return rt


def get_by_raw(db: Session, raw_token: str) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw_token))
    return db.execute(stmt).scalar_one_or_none()


def revoke(db: Session, rt: RefreshToken) -> None:
    rt.revoked_at = now_utc()
    db.commit()


def revoke_family(db: Session, family_id: str) -> None:
    stmt = (
        update(RefreshToken)
        .where(and_(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)))
        .values(revoked_at=now_utc())
    )
    db.execute(stmt)
    db.commit()


def is_active(rt: RefreshToken) -> bool:
    if rt.revoked_at is not None:
        return False
    # SQLite gives us naive datetimes on read from DateTime(timezone=True). Handle both.
    now = now_utc()
    exp = rt.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=now.tzinfo)
    return exp > now
