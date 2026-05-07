"""Audit-log writer — thin helper used by every mutating service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.context import request_id_var
from app.models_db.audit import AuditAction, AuditLog


def record(
    db: Session,
    *,
    action: AuditAction,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id_var.get(),
        ip_address=ip_address,
        user_agent=user_agent,
        details_json=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
