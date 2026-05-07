"""Provider models repository."""

from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models_db.provider_model import ProviderModel, ProviderType


def list_for_user(db: Session, user_id: str, *, include_deleted: bool = False):
    stmt = select(ProviderModel).where(ProviderModel.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(ProviderModel.is_deleted.is_(False))
    stmt = stmt.order_by(ProviderModel.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_for_user(db: Session, user_id: str, model_id: str) -> ProviderModel | None:
    stmt = select(ProviderModel).where(
        and_(
            ProviderModel.id == model_id,
            ProviderModel.user_id == user_id,
            ProviderModel.is_deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def get_by_name(db: Session, user_id: str, name: str) -> ProviderModel | None:
    stmt = select(ProviderModel).where(
        and_(
            ProviderModel.user_id == user_id,
            ProviderModel.name == name,
            ProviderModel.is_deleted.is_(False),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def create(
    db: Session,
    *,
    user_id: str,
    name: str,
    provider_type: ProviderType,
    endpoint_url: str | None,
    model_name: str,
    api_version: str | None,
    api_key: str | None,
    extra_headers: dict | None,
    default_system_prompt: str | None,
    supports_vision: bool,
    supports_tools: bool,
    context_window_tokens: int | None,
    price_input_per_mtok_usd,
    price_output_per_mtok_usd,
) -> ProviderModel:
    m = ProviderModel(
        user_id=user_id,
        name=name,
        provider_type=provider_type,
        endpoint_url=endpoint_url,
        model_name=model_name,
        api_version=api_version,
        api_key_encrypted=api_key,
        extra_headers_encrypted=extra_headers,
        default_system_prompt=default_system_prompt,
        supports_vision=supports_vision,
        supports_tools=supports_tools,
        context_window_tokens=context_window_tokens,
        price_input_per_mtok_usd=price_input_per_mtok_usd,
        price_output_per_mtok_usd=price_output_per_mtok_usd,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def soft_delete(db: Session, m: ProviderModel) -> None:
    m.is_deleted = True
    m.is_active = False
    db.commit()
