"""Retry and timeout policy independent of any specific AI backend."""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

from .providers import AIProvider, AIProviderError, AIProviderTimeout, ProviderResponse


class AIClient:
    def __init__(
        self,
        provider: AIProvider,
        *,
        timeout_seconds: float = 20.0,
        retries: int = 1,
        retry_timeouts: bool = False,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.retry_timeouts = retry_timeouts

    def generate(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
        operation: str = "generation",
        max_output_tokens: int | None = None,
    ) -> ProviderResponse:
        selected_timeout = timeout_seconds or self.timeout_seconds
        if selected_timeout <= 0:
            raise ValueError("timeout_seconds must be positive")
        last_error: AIProviderError | None = None
        allowed_attempts = self.retries + 1
        for attempt in range(allowed_attempts):
            kwargs: dict[str, Any] = {
                "timeout_seconds": selected_timeout,
            }
            if response_schema is not None:
                kwargs["response_schema"] = response_schema
            if operation != "generation":
                kwargs["operation"] = operation
            if max_output_tokens is not None:
                kwargs["max_output_tokens"] = max_output_tokens
            try:
                if getattr(self.provider, "timeout_mode", None) == "transport":
                    return self.provider.generate(prompt, **kwargs)
                return self._bounded_generate(prompt, kwargs, selected_timeout, operation)
            except AIProviderTimeout as exc:
                timeout_attempts = allowed_attempts if self.retry_timeouts else 1
                details = dict(getattr(exc, "details", {}))
                details.update(attempt=attempt + 1, max_attempts=timeout_attempts)
                layer = str(details.get("timeout_layer") or "provider_timeout")
                elapsed = float(details.get("elapsed_seconds") or selected_timeout)
                last_error = AIProviderTimeout(
                    f"{self.provider.name} {operation} timed out at {layer} after "
                    f"{elapsed:.3f}s (configured {selected_timeout:g}s; "
                    f"attempt {attempt + 1}/{timeout_attempts})",
                    details=details,
                )
                if not self.retry_timeouts or attempt + 1 >= allowed_attempts:
                    raise last_error from exc
            except AIProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt + 1 >= allowed_attempts:
                    raise
                time.sleep(min(0.1 * (attempt + 1), 0.5))
            except Exception as exc:
                last_error = AIProviderError(
                    f"{self.provider.name} failed: {type(exc).__name__}: {exc}"
                )
                raise last_error from exc
        raise last_error or AIProviderError("AI provider failed without an error")

    def _bounded_generate(
        self,
        prompt: str,
        kwargs: dict[str, Any],
        timeout_seconds: float,
        operation: str,
    ) -> ProviderResponse:
        outcome: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

        def invoke() -> None:
            try:
                outcome.put((True, self.provider.generate(prompt, **kwargs)))
            except BaseException as exc:  # re-raised on the calling thread
                outcome.put((False, exc))

        worker = threading.Thread(target=invoke, name="resume-ai", daemon=True)
        worker.start()
        worker.join(timeout_seconds)
        if worker.is_alive():
            raise AIProviderTimeout(
                f"{self.provider.name} exceeded the {timeout_seconds:g}s wall-clock bound",
                details={
                    "provider": self.provider.name,
                    "model": self.provider.model,
                    "operation": operation,
                    "timeout_layer": "outer_wall_clock_thread",
                    "configured_timeout_seconds": timeout_seconds,
                    "elapsed_seconds": timeout_seconds,
                    "request_reached_provider": True,
                    "partial_response_bytes": None,
                },
            )
        succeeded, value = outcome.get_nowait()
        if succeeded:
            if not isinstance(value, ProviderResponse):
                raise AIProviderError("AI provider returned an invalid response object")
            return value
        if isinstance(value, BaseException):
            raise value
        raise AIProviderError("AI provider failed without an outcome")
