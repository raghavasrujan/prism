"""Custom tool schemas — discriminated union on ``impl_type``."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models_db.custom_tool import SandboxRuntime, ToolImplType


class ToolBase(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str = Field(min_length=1)
    args_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "additionalProperties": True},
        description="JSON-Schema for tool arguments",
    )
    timeout_ms: int = Field(default=30000, ge=100, le=600_000)
    is_active: bool = True

    @field_validator("args_schema")
    @classmethod
    def _validate_schema(cls, v: dict) -> dict:
        if v.get("type") != "object":
            raise ValueError("args_schema.type must be 'object'")
        return v


class HttpToolCreate(ToolBase):
    impl_type: Literal[ToolImplType.http] = ToolImplType.http
    endpoint_url: str = Field(max_length=1024)
    method: str = "POST"
    headers: dict[str, str] | None = None

    @field_validator("endpoint_url")
    @classmethod
    def _url(cls, v: str) -> str:
        HttpUrl(v)  # raises if invalid
        return v

    @field_validator("method")
    @classmethod
    def _method(cls, v: str) -> str:
        v = v.upper()
        if v not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("method must be GET/POST/PUT/PATCH/DELETE")
        return v


class PythonToolCreate(ToolBase):
    impl_type: Literal[ToolImplType.python_inline] = ToolImplType.python_inline
    code: str = Field(min_length=1, max_length=200_000)
    runtime: SandboxRuntime = SandboxRuntime.python3_14
    memory_limit_mb: int = Field(default=256, ge=32, le=2048)
    cpu_time_limit_s: int = Field(default=10, ge=1, le=120)
    network_access: bool = False
    allowed_env: dict[str, str] | None = None


ToolCreate = Annotated[
    HttpToolCreate | PythonToolCreate,
    Field(discriminator="impl_type"),
]


class ToolUpdate(BaseModel):
    """Partial update — impl_type is immutable."""

    name: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str | None = None
    args_schema: dict[str, Any] | None = None
    timeout_ms: int | None = Field(default=None, ge=100, le=600_000)
    is_active: bool | None = None
    # HTTP-only
    endpoint_url: str | None = None
    method: str | None = None
    headers: dict[str, str] | None = None
    # Python-only
    code: str | None = None
    memory_limit_mb: int | None = Field(default=None, ge=32, le=2048)
    cpu_time_limit_s: int | None = Field(default=None, ge=1, le=120)
    network_access: bool | None = None
    allowed_env: dict[str, str] | None = None


class ToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    args_schema: dict[str, Any] = Field(validation_alias="args_schema_json")
    impl_type: ToolImplType
    timeout_ms: int
    is_active: bool
    # HTTP fields
    endpoint_url: str | None = None
    method: str | None = None
    has_headers: bool = False
    # Python fields
    has_code: bool = False
    code: str | None = None
    runtime: SandboxRuntime | None = None
    memory_limit_mb: int = 256
    cpu_time_limit_s: int = 10
    network_access: bool = False
    created_at: datetime
    updated_at: datetime


class ToolTestRequest(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)


class ToolTestResponse(BaseModel):
    ok: bool
    result: Any | None = None
    error: str | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int
    status_code: int | None = None
