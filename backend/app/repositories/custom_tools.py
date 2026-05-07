"""Custom tools repository."""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models_db.custom_tool import CustomTool, ToolImplType


def list_for_user(db: Session, user_id: str, *, include_deleted: bool = False):
    stmt = select(CustomTool).where(CustomTool.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(CustomTool.is_deleted.is_(False))
    stmt = stmt.order_by(CustomTool.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_for_user(db: Session, user_id: str, tool_id: str) -> CustomTool | None:
    stmt = select(CustomTool).where(
        and_(
            CustomTool.id == tool_id,
            CustomTool.user_id == user_id,
            CustomTool.is_deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_by_name(db: Session, user_id: str, name: str) -> CustomTool | None:
    stmt = select(CustomTool).where(
        and_(
            CustomTool.user_id == user_id,
            CustomTool.name == name,
            CustomTool.is_deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def create_http(db: Session, *, user_id: str, data: dict) -> CustomTool:
    tool = CustomTool(
        user_id=user_id,
        name=data["name"],
        description=data["description"],
        args_schema_json=data["args_schema"],
        impl_type=ToolImplType.http,
        endpoint_url=data["endpoint_url"],
        method=data["method"],
        headers_encrypted=data.get("headers"),
        timeout_ms=data["timeout_ms"],
        is_active=data.get("is_active", True),
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


def create_python(db: Session, *, user_id: str, data: dict) -> CustomTool:
    tool = CustomTool(
        user_id=user_id,
        name=data["name"],
        description=data["description"],
        args_schema_json=data["args_schema"],
        impl_type=ToolImplType.python_inline,
        code_source_encrypted=data["code"],
        runtime=data["runtime"],
        memory_limit_mb=data["memory_limit_mb"],
        cpu_time_limit_s=data["cpu_time_limit_s"],
        network_access=data["network_access"],
        allowed_env_json=data.get("allowed_env"),
        timeout_ms=data["timeout_ms"],
        is_active=data.get("is_active", True),
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


def soft_delete(db: Session, tool: CustomTool) -> None:
    tool.is_deleted = True
    tool.is_active = False
    db.commit()
