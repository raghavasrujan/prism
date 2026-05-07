"""MCP servers CRUD + tool discovery."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models_db.audit import AuditAction
from app.models_db.user import User
from app.repositories import mcp as mcp_repo
from app.schemas.mcp import (
    McpRefreshResponse,
    McpServerCreate,
    McpServerOut,
    McpServerUpdate,
    McpToolCacheOut,
)
from app.security import now_utc
from app.services.audit_service import record
from app.services.mcp_client import McpClientError, discover_tools

_log = get_logger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _to_out(s) -> McpServerOut:
    return McpServerOut(
        id=s.id,
        name=s.name,
        transport=s.transport,
        url=s.url,
        is_active=s.is_active,
        has_headers=s.headers_encrypted is not None,
        last_probed_at=s.last_probed_at,
        last_probe_ok=s.last_probe_ok,
        last_probe_error=s.last_probe_error,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=list[McpServerOut])
def list_mcp(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[McpServerOut]:
    return [_to_out(s) for s in mcp_repo.list_for_user(db, user.id)]


@router.post("", response_model=McpServerOut, status_code=status.HTTP_201_CREATED)
def create_mcp(
    body: McpServerCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpServerOut:
    if mcp_repo.get_by_name(db, user.id, body.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"MCP server named {body.name!r} already exists",
        )
    s = mcp_repo.create(
        db,
        user_id=user.id,
        name=body.name,
        transport=body.transport,
        url=body.url,
        headers=body.headers,
    )
    record(
        db,
        action=AuditAction.mcp_created,
        user_id=user.id,
        resource_type="mcp_server",
        resource_id=s.id,
        details={"name": s.name, "transport": s.transport.value},
    )
    return _to_out(s)


@router.get("/{server_id}", response_model=McpServerOut)
def get_mcp(
    server_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpServerOut:
    s = mcp_repo.get_for_user(db, user.id, server_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_out(s)


@router.patch("/{server_id}", response_model=McpServerOut)
def update_mcp(
    server_id: str,
    body: McpServerUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpServerOut:
    s = mcp_repo.get_for_user(db, user.id, server_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)

    if "name" in data and data["name"] != s.name:
        if mcp_repo.get_by_name(db, user.id, data["name"]) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Another server already uses that name"
            )

    if "headers" in data:
        s.headers_encrypted = data.pop("headers")

    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    record(
        db,
        action=AuditAction.mcp_updated,
        user_id=user.id,
        resource_type="mcp_server",
        resource_id=s.id,
    )
    return _to_out(s)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp(
    server_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    s = mcp_repo.get_for_user(db, user.id, server_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    mcp_repo.soft_delete(db, s)
    record(
        db,
        action=AuditAction.mcp_deleted,
        user_id=user.id,
        resource_type="mcp_server",
        resource_id=s.id,
    )


@router.post("/{server_id}/refresh", response_model=McpRefreshResponse)
def refresh_mcp(
    server_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> McpRefreshResponse:
    s = mcp_repo.get_for_user(db, user.id, server_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    ok = False
    err: str | None = None
    tools_out: list = []
    try:
        raw_tools = asyncio.run(
            discover_tools(url=s.url, headers=s.headers_encrypted or None)
        )
        cached = mcp_repo.replace_tool_cache(db, mcp_server_id=s.id, tools=raw_tools)
        tools_out = [McpToolCacheOut.model_validate(c) for c in cached]
        ok = True
    except McpClientError as exc:
        err = str(exc)
        _log.warning("mcp.refresh.failed", server_id=s.id, error=err)

    s.last_probed_at = now_utc()
    s.last_probe_ok = ok
    s.last_probe_error = None if ok else err
    db.commit()
    return McpRefreshResponse(server_id=s.id, tools=tools_out, ok=ok, error=err)
