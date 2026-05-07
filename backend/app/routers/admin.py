"""Admin-only endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models_db.audit import AuditAction
from app.models_db.conversation import Conversation
from app.models_db.message import Message, MessageRole
from app.models_db.user import User, UserRole
from app.repositories import users as user_repo
from app.services.audit_service import record

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    display_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AdminUserPatch(BaseModel):
    is_active: bool | None = None
    role: UserRole | None = None


class AdminUsageRow(BaseModel):
    user_id: str
    email: EmailStr
    provider_snapshot: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    request_count: int


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AdminUserOut]:
    stmt = select(User).order_by(User.created_at.desc())
    return [AdminUserOut.model_validate(u) for u in db.execute(stmt).scalars().all()]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: str,
    body: AdminUserPatch,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminUserOut:
    u = user_repo.get_by_id(db, user_id)
    if u is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(u, k, v)
    db.commit()
    db.refresh(u)
    record(
        db,
        action=AuditAction.admin_user_updated,
        user_id=admin.id,
        resource_type="user",
        resource_id=u.id,
        details=data,
    )
    return AdminUserOut.model_validate(u)


@router.get("/usage", response_model=list[AdminUsageRow])
def admin_usage(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    user_id: str | None = None,
) -> list[AdminUsageRow]:
    conds = [
        Message.role == MessageRole.assistant,
        Message.is_deleted.is_(False),
    ]
    if user_id is not None:
        conds.append(Conversation.user_id == user_id)

    rows = (
        db.query(
            Conversation.user_id,
            User.email,
            Message.provider_snapshot,
            func.coalesce(func.sum(Message.input_tokens), 0),
            func.coalesce(func.sum(Message.output_tokens), 0),
            func.coalesce(func.sum(Message.cost_usd), 0),
            func.count(Message.id),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(User, User.id == Conversation.user_id)
        .filter(and_(*conds))
        .group_by(Conversation.user_id, User.email, Message.provider_snapshot)
        .all()
    )
    return [
        AdminUsageRow(
            user_id=r[0],
            email=r[1],
            provider_snapshot=r[2],
            input_tokens=int(r[3] or 0),
            output_tokens=int(r[4] or 0),
            cost_usd=float(r[5] or 0),
            request_count=int(r[6] or 0),
        )
        for r in rows
    ]
