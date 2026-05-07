"""Request-scoped correlation context.

Every log record automatically picks up the values bound here via structlog's
`merge_contextvars` processor. Set once per request in middleware.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
user_email_var: ContextVar[str | None] = ContextVar("user_email", default=None)
conversation_id_var: ContextVar[str | None] = ContextVar("conversation_id", default=None)


def bind(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    user_email: str | None = None,
    conversation_id: str | None = None,
) -> None:
    if request_id is not None:
        request_id_var.set(request_id)
    if user_id is not None:
        user_id_var.set(user_id)
    if user_email is not None:
        user_email_var.set(user_email)
    if conversation_id is not None:
        conversation_id_var.set(conversation_id)


def snapshot() -> dict[str, str | None]:
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "user": user_email_var.get(),
        "conversation_id": conversation_id_var.get(),
    }
