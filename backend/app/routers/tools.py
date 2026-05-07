"""Custom tools CRUD + test endpoint."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models_db.audit import AuditAction
from app.models_db.custom_tool import ToolImplType
from app.models_db.user import User
from app.repositories import custom_tools as tool_repo
from app.schemas.tool import (
    HttpToolCreate,
    PythonToolCreate,
    ToolCreate,
    ToolOut,
    ToolTestRequest,
    ToolTestResponse,
    ToolUpdate,
)
from app.services.audit_service import record
from app.services.tool_executor import execute_tool

_log = get_logger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


def _to_out(t) -> ToolOut:
    return ToolOut(
        id=t.id,
        name=t.name,
        description=t.description,
        args_schema_json=t.args_schema_json,
        impl_type=t.impl_type,
        timeout_ms=t.timeout_ms,
        is_active=t.is_active,
        endpoint_url=t.endpoint_url,
        method=t.method,
        has_headers=t.headers_encrypted is not None,
        has_code=t.code_source_encrypted is not None,
        code=t.code_source_encrypted,  # EncryptedString auto-decrypts on read
        runtime=t.runtime,
        memory_limit_mb=t.memory_limit_mb,
        cpu_time_limit_s=t.cpu_time_limit_s,
        network_access=t.network_access,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("", response_model=list[ToolOut])
def list_tools(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ToolOut]:
    return [_to_out(t) for t in tool_repo.list_for_user(db, user.id)]


@router.post("", response_model=ToolOut, status_code=status.HTTP_201_CREATED)
def create_tool(
    body: ToolCreate = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ToolOut:
    if tool_repo.get_by_name(db, user.id, body.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tool named {body.name!r} already exists",
        )
    if isinstance(body, HttpToolCreate):
        tool = tool_repo.create_http(
            db,
            user_id=user.id,
            data={
                "name": body.name,
                "description": body.description,
                "args_schema": body.args_schema,
                "endpoint_url": body.endpoint_url,
                "method": body.method,
                "headers": body.headers,
                "timeout_ms": body.timeout_ms,
                "is_active": body.is_active,
            },
        )
    elif isinstance(body, PythonToolCreate):
        tool = tool_repo.create_python(
            db,
            user_id=user.id,
            data={
                "name": body.name,
                "description": body.description,
                "args_schema": body.args_schema,
                "code": body.code,
                "runtime": body.runtime,
                "memory_limit_mb": body.memory_limit_mb,
                "cpu_time_limit_s": body.cpu_time_limit_s,
                "network_access": body.network_access,
                "allowed_env": body.allowed_env,
                "timeout_ms": body.timeout_ms,
                "is_active": body.is_active,
            },
        )
    else:  # pragma: no cover
        raise HTTPException(400, "Unknown tool impl_type")

    record(
        db,
        action=AuditAction.tool_created,
        user_id=user.id,
        resource_type="custom_tool",
        resource_id=tool.id,
        details={"name": tool.name, "impl_type": tool.impl_type.value},
    )
    return _to_out(tool)


@router.get("/{tool_id}", response_model=ToolOut)
def get_tool(
    tool_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ToolOut:
    tool = tool_repo.get_for_user(db, user.id, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_out(tool)


@router.patch("/{tool_id}", response_model=ToolOut)
def update_tool(
    tool_id: str,
    body: ToolUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ToolOut:
    tool = tool_repo.get_for_user(db, user.id, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)

    if "name" in data and data["name"] != tool.name:
        if tool_repo.get_by_name(db, user.id, data["name"]) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another tool already uses that name",
            )

    if "args_schema" in data:
        tool.args_schema_json = data.pop("args_schema")
    if "headers" in data:
        tool.headers_encrypted = data.pop("headers")
    if "code" in data:
        if tool.impl_type != ToolImplType.python_inline:
            raise HTTPException(400, "code is only valid for python_inline tools")
        tool.code_source_encrypted = data.pop("code")
    if "allowed_env" in data:
        tool.allowed_env_json = data.pop("allowed_env")

    for k, v in data.items():
        setattr(tool, k, v)
    db.commit()
    db.refresh(tool)
    record(
        db,
        action=AuditAction.tool_updated,
        user_id=user.id,
        resource_type="custom_tool",
        resource_id=tool.id,
    )
    return _to_out(tool)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tool(
    tool_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    tool = tool_repo.get_for_user(db, user.id, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    tool_repo.soft_delete(db, tool)
    record(
        db,
        action=AuditAction.tool_deleted,
        user_id=user.id,
        resource_type="custom_tool",
        resource_id=tool.id,
    )


@router.post("/{tool_id}/test", response_model=ToolTestResponse)
def test_tool(
    tool_id: str,
    body: ToolTestRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ToolTestResponse:
    tool = tool_repo.get_for_user(db, user.id, tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = asyncio.run(execute_tool(tool, body.args))
    return ToolTestResponse(
        ok=result.ok,
        result=result.result,
        error=result.error,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        status_code=result.status_code,
    )
