"""Provider registry — one adapter interface, five backing implementations."""

from app.services.providers.base import (
    ProviderAdapter,
    ProviderResponse,
    ProviderStreamEvent,
)
from app.services.providers.mock import MockProvider
from app.services.providers.openai_family import OpenAiFamilyProvider
from app.services.providers.registry import get_provider

__all__ = [
    "MockProvider",
    "OpenAiFamilyProvider",
    "ProviderAdapter",
    "ProviderResponse",
    "ProviderStreamEvent",
    "get_provider",
]
