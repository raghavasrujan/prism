"""Provider factory. Test env may override to inject MockProvider."""

from __future__ import annotations

import os

from app.models_db.provider_model import ProviderModel, ProviderType
from app.services.providers.base import ProviderAdapter


_override: ProviderAdapter | None = None


def override_provider(adapter: ProviderAdapter | None) -> None:
    """Swap in a mock for the whole process. Tests use this."""
    global _override
    _override = adapter


def get_provider(model: ProviderModel) -> ProviderAdapter:
    if _override is not None:
        return _override
    # Force the mock when running under pytest, so nothing ever hits real APIs.
    if os.environ.get("APP_ENV") == "test":
        from app.services.providers.mock import MockProvider

        return MockProvider()
    from app.services.providers.openai_family import OpenAiFamilyProvider

    if model.provider_type in {
        ProviderType.openai,
        ProviderType.openai_compatible,
        ProviderType.azure,
        ProviderType.ollama,
    }:
        return OpenAiFamilyProvider()
    # TODO: Anthropic + Gemini adapters in Phase 3b (planned).
    raise NotImplementedError(f"Provider not yet implemented: {model.provider_type}")
