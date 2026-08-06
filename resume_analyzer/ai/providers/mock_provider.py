"""Deterministic provider used by tests and offline development."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from typing import Any

from .base import AIProviderError, ProviderResponse


class MockProvider:
    name = "mock"

    def __init__(
        self,
        responses: (
            str
            | Exception
            | Callable[[str], str | Exception]
            | Iterable[str | Exception | Callable[[str], str | Exception]]
        ),
        *,
        model: str = "mock-v1",
    ) -> None:
        if isinstance(responses, (str, Exception)) or callable(responses):
            values = [responses]
        else:
            values = list(responses)
        if not values:
            raise ValueError("MockProvider requires at least one response")
        self._responses = deque(values)
        self.model = model
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        response_schema: dict[str, Any] | None = None,
        operation: str = "generation",
        max_output_tokens: int | None = None,
    ) -> ProviderResponse:
        call: dict[str, object] = {"prompt": prompt, "timeout_seconds": timeout_seconds}
        if response_schema is not None:
            call["response_schema"] = response_schema
        if operation != "generation":
            call["operation"] = operation
        if max_output_tokens is not None:
            call["max_output_tokens"] = max_output_tokens
        self.calls.append(call)
        value = self._responses[0] if len(self._responses) == 1 else self._responses.popleft()
        if callable(value):
            value = value(prompt)
        if isinstance(value, Exception):
            raise value
        if not isinstance(value, str):
            raise AIProviderError("Mock response must be a string or exception")
        return ProviderResponse(text=value, provider=self.name, model=self.model)
