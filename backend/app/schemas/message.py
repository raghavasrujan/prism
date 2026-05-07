"""Message schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models_db.message import FinishReason, MessageRole


class TextContentPart(BaseModel):
    type: str = "text"
    text: str


class ImageContentPart(BaseModel):
    type: str = "image_url"
    image_url: dict[str, Any]


ContentPart = TextContentPart | ImageContentPart


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    request_id: str
    parent_message_id: str | None
    role: MessageRole
    content: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None
    tool_name: str | None
    provider_snapshot: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    latency_ms: int | None
    finish_reason: FinishReason | None
    created_at: datetime

    @classmethod
    def from_orm_row(cls, m) -> "MessageOut":
        return cls(
            id=m.id,
            conversation_id=m.conversation_id,
            request_id=m.request_id,
            parent_message_id=m.parent_message_id,
            role=m.role,
            content=m.content_json or [],
            tool_calls=m.tool_calls_json,
            tool_call_id=m.tool_call_id,
            tool_name=m.tool_name,
            provider_snapshot=m.provider_snapshot,
            input_tokens=m.input_tokens,
            output_tokens=m.output_tokens,
            cost_usd=m.cost_usd,
            latency_ms=m.latency_ms,
            finish_reason=m.finish_reason,
            created_at=m.created_at,
        )


class SendMessageRequest(BaseModel):
    content: str | list[dict[str, Any]] = Field(
        ..., description="Either a plain string or an OpenAI-style content-part array"
    )
    attachment_ids: list[str] = Field(default_factory=list)
    parent_message_id: str | None = Field(
        default=None,
        description="Set to fork/branch from a specific message (edit-and-resend)",
    )


class SendMessageResponse(BaseModel):
    conversation_id: str
    request_id: str
    user_message: MessageOut
    assistant_message: MessageOut
    tool_messages: list[MessageOut] = Field(default_factory=list)
    usage: dict[str, Any]
