"""File/image uploads."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models_db.attachment import Attachment, AttachmentKind
from app.models_db.user import User
from app.security import new_uuid
from app.services.storage_adapter import get_storage

_log = get_logger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: AttachmentKind
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def create_upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadOut:
    settings = get_settings()
    data = await file.read()

    mime = (file.content_type or "application/octet-stream").lower()
    is_image = mime in _IMAGE_MIMES
    max_mb = settings.upload_max_image_mb if is_image else settings.upload_max_file_mb
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds {max_mb}MB limit",
        )

    stored = get_storage().save(user_id=user.id, filename=file.filename or "unnamed", data=data)
    kind = AttachmentKind.image if is_image else AttachmentKind.file

    att = Attachment(
        id=new_uuid(),
        user_id=user.id,
        kind=kind,
        filename=file.filename or "unnamed",
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        storage_path=stored.storage_path,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    _log.info("upload.created", attachment_id=att.id, kind=kind.value, size=stored.size_bytes)
    return UploadOut.model_validate(att)


@router.get("/{attachment_id}")
def get_upload(
    attachment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    att = db.get(Attachment, attachment_id)
    if att is None or att.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    data = get_storage().read(att.storage_path)
    return Response(content=data, media_type=att.mime_type)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_upload(
    attachment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    att = db.get(Attachment, attachment_id)
    if att is None or att.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    get_storage().delete(att.storage_path)
    db.delete(att)
    db.commit()
