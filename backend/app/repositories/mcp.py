"""MCP servers repository + tool-cache helpers."""

from __future__ import annotations

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session

from app.models_db.mcp_server import McpServer, McpToolCache, McpTransport


def list_for_user(db: Session, user_id: str, *, include_deleted: bool = False):
    stmt = select(McpServer).where(McpServer.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(McpServer.is_deleted.is_(False))
    return db.execute(stmt.order_by(McpServer.created_at.desc())).scalars().all()


def get_for_user(db: Session, user_id: str, server_id: str) -> McpServer | None:
    stmt = select(McpServer).where(
        and_(
            McpServer.id == server_id,
            McpServer.user_id == user_id,
            McpServer.is_deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_by_name(db: Session, user_id: str, name: str) -> McpServer | None:
    stmt = select(McpServer).where(
        and_(
            McpServer.user_id == user_id,
            McpServer.name == name,
            McpServer.is_deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def create(
    db: Session,
    *,
    user_id: str,
    name: str,
    transport: McpTransport,
    url: str,
    headers: dict | None,
) -> McpServer:
    server = McpServer(
        user_id=user_id,
        name=name,
        transport=transport,
        url=url,
        headers_encrypted=headers,
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


def soft_delete(db: Session, server: McpServer) -> None:
    server.is_deleted = True
    server.is_active = False
    db.commit()


def replace_tool_cache(
    db: Session, *, mcp_server_id: str, tools: list[dict]
) -> list[McpToolCache]:
    """Replace all cached tools for this server."""
    db.execute(delete(McpToolCache).where(McpToolCache.mcp_server_id == mcp_server_id))
    rows = [
        McpToolCache(
            mcp_server_id=mcp_server_id,
            tool_name=t["name"],
            description=t.get("description"),
            args_schema_json=t.get("input_schema") or t.get("args_schema") or {"type": "object"},
        )
        for t in tools
    ]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


def list_cached_tools(db: Session, mcp_server_id: str) -> list[McpToolCache]:
    stmt = select(McpToolCache).where(McpToolCache.mcp_server_id == mcp_server_id)
    return db.execute(stmt).scalars().all()
