"""Messages: send (non-streaming) + list + branch switching + delete."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.context import bind
from app.db import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models_db.audit import AuditAction
from app.models_db.user import User
from app.repositories import conversations as conv_repo
from app.repositories import messages as msg_repo
from app.repositories import provider_models as pm_repo
from app.schemas.message import MessageOut, SendMessageRequest, SendMessageResponse
from app.services.agent_runner import run_turn
from app.services.audit_service import record

_log = get_logger(__name__)

router = APIRouter(tags=["messages"])


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def list_messages(
    conv_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    bind(conversation_id=conv.id)
    return [MessageOut.from_orm_row(m) for m in msg_repo.list_for_conversation(db, conv.id)]


@router.post(
    "/conversations/{conv_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conv_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SendMessageResponse:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    model = pm_repo.get_for_user(db, user.id, conv.provider_model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation's model was deleted"
        )

    bind(conversation_id=conv.id)

    result = asyncio.run(
        run_turn(
            db,
            conv=conv,
            model=model,
            user_content=body.content,
            parent_message_id=body.parent_message_id or conv.active_leaf_message_id,
            attachment_ids=body.attachment_ids,
        )
    )
    record(
        db,
        action=AuditAction.message_sent,
        user_id=user.id,
        resource_type="conversation",
        resource_id=conv.id,
        details={"request_id": result.request_id},
    )
    return SendMessageResponse(
        conversation_id=conv.id,
        request_id=result.request_id,
        user_message=MessageOut.from_orm_row(result.user_message),
        assistant_message=MessageOut.from_orm_row(result.assistant_message),
        tool_messages=[MessageOut.from_orm_row(m) for m in result.tool_messages],
        usage=result.usage,
    )


@router.post("/conversations/{conv_id}/switch-branch")
def switch_branch(
    conv_id: str,
    leaf_message_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    leaf = msg_repo.get(db, leaf_message_id)
    if leaf is None or leaf.conversation_id != conv.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leaf not in conversation")
    conv.active_leaf_message_id = leaf.id
    db.commit()
    return {"active_leaf_message_id": leaf.id}


@router.delete(
    "/conversations/{conv_id}/messages/{msg_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_message(
    conv_id: str,
    msg_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Soft-delete a single message.

    If the message was the active leaf, the conversation's active leaf is
    stepped back to its parent so the tree remains navigable.
    """
    conv = conv_repo.get_for_user(db, user.id, conv_id)
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    msg = msg_repo.get(db, msg_id)
    if msg is None or msg.conversation_id != conv_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    msg.is_deleted = True
    # Step the active-leaf back so future sends don't branch from a deleted node.
    if conv.active_leaf_message_id == msg_id:
        conv.active_leaf_message_id = msg.parent_message_id
    db.commit()
