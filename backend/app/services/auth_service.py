"""Auth service — orchestrates register / login / refresh / logout."""

from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_config import get_logger
from app.models_db.audit import AuditAction
from app.models_db.user import User
from app.repositories import refresh_tokens as rt_repo
from app.repositories import users as user_repo
from app.security import (
    create_access_token,
    new_opaque_token,
    now_utc,
    verify_password,
)
from app.services.audit_service import record

_log = get_logger(__name__)


class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=status_code, detail=detail)


def _issue_pair(
    db: Session,
    user: User,
    *,
    family_id: str | None = None,
    parent_id: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, str, "datetime"]:  # type: ignore[name-defined]
    from datetime import datetime  # noqa

    settings = get_settings()
    access, access_exp = create_access_token(
        user_id=user.id, email=user.email, role=user.role.value
    )
    raw_refresh = new_opaque_token(48)
    refresh_exp = now_utc() + timedelta(days=settings.jwt_refresh_ttl_days)
    rt_repo.create(
        db,
        user_id=user.id,
        raw_token=raw_refresh,
        expires_at=refresh_exp,
        family_id=family_id,
        parent_id=parent_id,
        user_agent=user_agent,
        ip_address=ip,
    )
    return access, raw_refresh, access_exp


def register(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str | None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[User, str, str, "datetime"]:  # type: ignore[name-defined]
    if user_repo.get_by_email(db, email) is not None:
        raise AuthError("Email already registered", status.HTTP_409_CONFLICT)
    user = user_repo.create(db, email=email, password=password, display_name=display_name)
    record(
        db,
        action=AuditAction.user_created,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email},
    )
    access, refresh, access_exp = _issue_pair(db, user, user_agent=user_agent, ip=ip)
    _log.info("auth.register.ok", user=user.email, user_id=user.id)
    return user, access, refresh, access_exp


def login(
    db: Session,
    *,
    email: str,
    password: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[User, str, str, "datetime"]:  # type: ignore[name-defined]
    user = user_repo.get_by_email(db, email)
    if user is None or not verify_password(user.password_hash, password):
        record(
            db,
            action=AuditAction.auth_login_failed,
            user_id=user.id if user else None,
            details={"email": email},
        )
        _log.warning("auth.login.failed", email=email)
        raise AuthError("Invalid email or password")
    if not user.is_active:
        raise AuthError("Account disabled", status.HTTP_403_FORBIDDEN)

    user.last_login_at = now_utc()
    user.failed_login_count = 0
    db.commit()

    access, refresh, access_exp = _issue_pair(db, user, user_agent=user_agent, ip=ip)
    record(
        db,
        action=AuditAction.auth_login,
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
    )
    _log.info("auth.login.ok", user=user.email, user_id=user.id)
    return user, access, refresh, access_exp


def refresh(
    db: Session,
    *,
    raw_token: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[User, str, str, "datetime"]:  # type: ignore[name-defined]
    rt = rt_repo.get_by_raw(db, raw_token)
    if rt is None:
        _log.warning("auth.refresh.unknown_token")
        raise AuthError("Invalid refresh token")

    if not rt_repo.is_active(rt):
        # Reuse detection: revoked-yet-presented → nuke the family.
        if rt.revoked_at is not None:
            rt_repo.revoke_family(db, rt.family_id)
            record(
                db,
                action=AuditAction.auth_refresh_reuse_detected,
                user_id=rt.user_id,
                resource_type="refresh_family",
                resource_id=rt.family_id,
            )
            _log.warning("auth.refresh.reuse_detected", user_id=rt.user_id, family=rt.family_id)
        raise AuthError("Refresh token expired or revoked")

    user = user_repo.get_by_id(db, rt.user_id)
    if user is None or not user.is_active:
        raise AuthError("Account not available", status.HTTP_403_FORBIDDEN)

    # Rotate: revoke current, issue new in same family
    rt_repo.revoke(db, rt)
    access, refresh_new, access_exp = _issue_pair(
        db, user, family_id=rt.family_id, parent_id=rt.id, user_agent=user_agent, ip=ip
    )
    record(db, action=AuditAction.auth_refresh, user_id=user.id)
    _log.info("auth.refresh.ok", user=user.email, user_id=user.id)
    return user, access, refresh_new, access_exp


def logout(db: Session, *, raw_token: str) -> None:
    rt = rt_repo.get_by_raw(db, raw_token)
    if rt is None:
        return  # idempotent
    if rt.revoked_at is None:
        rt_repo.revoke(db, rt)
    record(db, action=AuditAction.auth_logout, user_id=rt.user_id)
