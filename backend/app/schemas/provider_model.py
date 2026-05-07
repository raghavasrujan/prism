"""Provider model request / response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.models_db.provider_model import ProviderType


class ProviderModelBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider_type: ProviderType
    endpoint_url: str | None = Field(default=None, max_length=1024)
    model_name: str = Field(min_length=1, max_length=200)
    api_version: str | None = Field(
        default=None,
        max_length=40,
        description="Azure OpenAI api-version (e.g. '2025-01-01-preview'). Required for provider_type=azure.",
    )
    default_system_prompt: str | None = None
    supports_vision: bool = False
    supports_tools: bool = True
    context_window_tokens: int | None = Field(default=None, ge=1)
    price_input_per_mtok_usd: Decimal | None = None
    price_output_per_mtok_usd: Decimal | None = None

    @field_validator("endpoint_url")
    @classmethod
    def _endpoint_url_shape(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        # Basic URL sanity — full validation happens at request time.
        HttpUrl(v)
        return v

    @model_validator(mode="after")
    def _require_endpoint_for_local_providers(self):
        needs_endpoint = {
            ProviderType.openai_compatible,
            ProviderType.ollama,
            ProviderType.azure,
        }
        if self.provider_type in needs_endpoint and not self.endpoint_url:
            raise ValueError(
                f"endpoint_url is required for provider_type={self.provider_type.value}"
            )
        if self.provider_type == ProviderType.azure and not self.api_version:
            raise ValueError("api_version is required for provider_type=azure")
        return self


class ProviderModelCreate(ProviderModelBase):
    api_key: str | None = Field(default=None, description="Provider API key — encrypted at rest")
    extra_headers: dict[str, str] | None = None


class ProviderModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    endpoint_url: str | None = None
    model_name: str | None = None
    api_version: str | None = Field(default=None, max_length=40)
    api_key: str | None = None
    extra_headers: dict[str, str] | None = None
    default_system_prompt: str | None = None
    supports_vision: bool | None = None
    supports_tools: bool | None = None
    context_window_tokens: int | None = None
    price_input_per_mtok_usd: Decimal | None = None
    price_output_per_mtok_usd: Decimal | None = None
    is_active: bool | None = None


class ProviderModelOut(ProviderModelBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    has_api_key: bool = Field(
        default=False,
        description="True if an API key is stored (never returns the key itself)",
    )
    created_at: datetime
    updated_at: datetime
