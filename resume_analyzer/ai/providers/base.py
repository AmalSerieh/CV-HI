"""Provider protocol and typed failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class AIProviderError(RuntimeError):
    """Base provider failure with bounded, prompt-free diagnostic details."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.details = dict(details or {})


class AIProviderTimeout(AIProviderError):
    pass


class AIProviderUnavailable(AIProviderError):
    pass


class AIProviderModelNotFound(AIProviderUnavailable):
    pass


class AIProviderConfigurationError(AIProviderError):
    pass


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    provider: str
    model: str | None = None
    diagnostics: dict[str, Any] | None = None


@runtime_checkable
class AIProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str | None: ...

    def generate(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        response_schema: dict[str, Any] | None = None,
        operation: str = "generation",
        max_output_tokens: int | None = None,
    ) -> ProviderResponse: ...
