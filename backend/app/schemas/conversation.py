"""Conversation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationBase(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    system_prompt_override: str | None = None


class ConversationCreate(ConversationBase):
    provider_model_id: str
    tool_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    provider_model_id: str | None = None
    system_prompt_override: str | None = None
    tool_ids: list[str] | None = None
    mcp_server_ids: list[str] | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    provider_model_id: str
    system_prompt_override: str | None
    active_leaf_message_id: str | None
    is_shared: bool
    share_slug: str | None
    tool_ids: list[str] = Field(default_factory=list)
    mcp_server_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConversationUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    cost_usd: float
    message_count: int
    by_model: list["ConversationUsageByModel"] = Field(default_factory=list)


class ConversationUsageByModel(BaseModel):
    provider_model_id: str | None
    model_snapshot: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    message_count: int


ConversationUsage.model_rebuild()


class ShareOut(BaseModel):
    slug: str
    url_path: str
