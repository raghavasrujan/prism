"""MCP server schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models_db.mcp_server import McpTransport


class McpServerBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    transport: McpTransport
    url: str = Field(max_length=1024)

    @field_validator("url")
    @classmethod
    def _url_shape(cls, v: str) -> str:
        HttpUrl(v)
        return v


class McpServerCreate(McpServerBase):
    headers: dict[str, str] | None = None


class McpServerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    transport: McpTransport | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    is_active: bool | None = None


class McpServerOut(McpServerBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    has_headers: bool = False
    last_probed_at: datetime | None = None
    last_probe_ok: bool | None = None
    last_probe_error: str | None = None
    created_at: datetime
    updated_at: datetime


class McpToolCacheOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool_name: str
    description: str | None
    args_schema: dict = Field(validation_alias="args_schema_json")
    fetched_at: datetime


class McpRefreshResponse(BaseModel):
    server_id: str
    tools: list[McpToolCacheOut]
    ok: bool
    error: str | None = None
