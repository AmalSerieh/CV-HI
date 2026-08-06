"""Lazy local-AI provider infrastructure."""

from .client import AIClient
from .provider_factory import build_provider
from .providers import (
    AIProvider,
    AIProviderError,
    AIProviderTimeout,
    AIProviderUnavailable,
    MockProvider,
    OllamaProvider,
    ProviderResponse,
    TransformersProvider,
)

__all__ = [
    "AIClient",
    "AIProvider",
    "AIProviderError",
    "AIProviderTimeout",
    "AIProviderUnavailable",
    "MockProvider",
    "OllamaProvider",
    "ProviderResponse",
    "TransformersProvider",
    "build_provider",
]
