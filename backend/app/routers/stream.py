"""Streaming chat + cancel endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models_db.user import User
from app.repositories import conversations as conv_repo
from app.repositories import provider_models as pm_repo
from app.schemas.message import SendMessageRequest
from app.services import cancel_bus
from app.services.agent_stream import stream_turn

router = APIRouter(tags=["messages"])


@router.post("/conversations/{conv_id}/messages/stream")
async def send_message_stream(
    conv_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    model = pm_repo.get_for_user(db, user.id, conv.provider_model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation's model was deleted"
        )

    gen = stream_turn(
        db,
        conv=conv,
        model=model,
        user_content=body.content,
        parent_message_id=body.parent_message_id or conv.active_leaf_message_id,
        attachment_ids=body.attachment_ids,
    )
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            # no-cache: every event must reach the client immediately.
            # no-transform: tell any intermediate proxy (nginx, Cloudflare …)
            #   not to modify or compress this response — compression requires
            #   buffering the full body before sending.
            "cache-control": "no-cache, no-transform",
            "connection": "keep-alive",
            "x-accel-buffering": "no",     # nginx: disable proxy buffering
            "content-encoding": "identity", # no gzip / deflate at this layer
        },
    )


@router.post("/messages/{request_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_message(
    request_id: str,
    user: User = Depends(get_current_user),  # noqa: ARG001 — auth-gate only
) -> None:
    cancel_bus.signal(request_id)
