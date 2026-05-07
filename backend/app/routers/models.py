"""Provider models CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.logging_config import get_logger
from app.models_db.audit import AuditAction
from app.models_db.user import User
from app.repositories import provider_models as pm_repo
from app.schemas.provider_model import (
    ProviderModelCreate,
    ProviderModelOut,
    ProviderModelUpdate,
)
from app.services.audit_service import record

_log = get_logger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


def _to_out(m) -> ProviderModelOut:
    data = ProviderModelOut.model_validate(m).model_copy(
        update={"has_api_key": m.api_key_encrypted is not None}
    )
    return data


@router.get("", response_model=list[ProviderModelOut])
def list_models(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProviderModelOut]:
    rows = pm_repo.list_for_user(db, user.id)
    return [_to_out(m) for m in rows]


@router.post("", response_model=ProviderModelOut, status_code=status.HTTP_201_CREATED)
def create_model(
    body: ProviderModelCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderModelOut:
    if pm_repo.get_by_name(db, user.id, body.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A model named {body.name!r} already exists",
        )
    m = pm_repo.create(
        db,
        user_id=user.id,
        name=body.name,
        provider_type=body.provider_type,
        endpoint_url=body.endpoint_url,
        model_name=body.model_name,
        api_version=body.api_version,
        api_key=body.api_key,
        extra_headers=body.extra_headers,
        default_system_prompt=body.default_system_prompt,
        supports_vision=body.supports_vision,
        supports_tools=body.supports_tools,
        context_window_tokens=body.context_window_tokens,
        price_input_per_mtok_usd=body.price_input_per_mtok_usd,
        price_output_per_mtok_usd=body.price_output_per_mtok_usd,
    )
    record(
        db,
        action=AuditAction.model_created,
        user_id=user.id,
        resource_type="provider_model",
        resource_id=m.id,
        details={"name": m.name, "provider_type": m.provider_type.value},
    )
    _log.info("model.created", model_id=m.id, provider=m.provider_type.value)
    return _to_out(m)


@router.get("/{model_id}", response_model=ProviderModelOut)
def get_model(
    model_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderModelOut:
    m = pm_repo.get_for_user(db, user.id, model_id)
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_out(m)


@router.patch("/{model_id}", response_model=ProviderModelOut)
def update_model(
    model_id: str,
    body: ProviderModelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderModelOut:
    m = pm_repo.get_for_user(db, user.id, model_id)
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    data = body.model_dump(exclude_unset=True)

    # Rename collision check
    if "name" in data and data["name"] != m.name:
        if pm_repo.get_by_name(db, user.id, data["name"]) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another model already uses that name",
            )

    if "api_key" in data:
        m.api_key_encrypted = data.pop("api_key")
    if "extra_headers" in data:
        m.extra_headers_encrypted = data.pop("extra_headers")

    for k, v in data.items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    record(
        db,
        action=AuditAction.model_updated,
        user_id=user.id,
        resource_type="provider_model",
        resource_id=m.id,
    )
    return _to_out(m)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    m = pm_repo.get_for_user(db, user.id, model_id)
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pm_repo.soft_delete(db, m)
    record(
        db,
        action=AuditAction.model_deleted,
        user_id=user.id,
        resource_type="provider_model",
        resource_id=m.id,
    )
