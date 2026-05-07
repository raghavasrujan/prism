"""User repository — thin SQLAlchemy queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_db.user import User, UserRole
from app.security import hash_password


def get_by_id(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower())
    return db.execute(stmt).scalar_one_or_none()


def create(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str | None = None,
    role: UserRole = UserRole.user,
) -> User:
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def count(db: Session) -> int:
    from sqlalchemy import func

    return db.execute(select(func.count(User.id))).scalar_one()
