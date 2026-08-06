"""Cancellable local Ollama provider with prompt-free diagnostics."""

from __future__ import annotations

import http.client
import json
import threading
import time
from collections import Counter
from typing import Any
from urllib.parse import urlsplit

from .base import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderModelNotFound,
    AIProviderTimeout,
    AIProviderUnavailable,
    ProviderResponse,
)

_STATE_LOCK = threading.RLock()
_RUNTIME_STATE: dict[tuple[str, str], dict[str, Any]] = {}
_GENERATION_LOCKS: dict[tuple[str, str], threading.Lock] = {}


def _runtime_key(base_url: str, model: str) -> tuple[str, str]:
    return base_url.rstrip("/"), model


def ollama_runtime_status(base_url: str, model: str | None) -> dict[str, Any]:
    """Return process-local state based only on real generation attempts."""
    if not model:
        return {"state": "cold", "request_count": 0, "operations": {}}
    with _STATE_LOCK:
        value = dict(_RUNTIME_STATE.get(_runtime_key(base_url, model), {}))
    value.setdefault("state", "cold")
    value.setdefault("request_count", 0)
    value.setdefault("operations", {})
    return value


def _update_runtime(base_url: str, model: str, **updates: Any) -> None:
    key = _runtime_key(base_url, model)
    with _STATE_LOCK:
        current = _RUNTIME_STATE.setdefault(
            key,
            {"state": "cold", "request_count": 0, "operations": {}},
        )
        current.update(updates)


def _generation_lock(base_url: str, model: str) -> threading.Lock:
    key = _runtime_key(base_url, model)
    with _STATE_LOCK:
        return _GENERATION_LOCKS.setdefault(key, threading.Lock())


class OllamaProvider:
    name = "ollama"
    timeout_mode = "transport"

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        temperature: float = 0.0,
        seed: int = 42,
        max_tokens: int = 900,
        max_output_characters: int = 50_000,
        keep_alive: str | int = "5m",
        connect_timeout_seconds: float = 5.0,
        num_ctx: int = 4096,
        cancel_cooldown_seconds: float = 2.0,
    ) -> None:
        if not model.strip():
            raise ValueError("Ollama model must be configured explicitly")
        if not 0 <= temperature <= 2:
            raise ValueError("Ollama temperature must be between 0 and 2")
        if max_tokens <= 0 or max_output_characters <= 0 or num_ctx <= 0:
            raise ValueError("Ollama output and context limits must be positive")
        if connect_timeout_seconds <= 0 or cancel_cooldown_seconds < 0:
            raise ValueError("Ollama connection timeout must be positive and cooldown non-negative")
        parsed = urlsplit(base_url.rstrip("/"))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Ollama base URL must be an absolute HTTP(S) URL")
        if parsed.query or parsed.fragment:
            raise ValueError("Ollama base URL cannot contain a query or fragment")
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens
        self.max_output_characters = max_output_characters
        self.keep_alive = keep_alive
        self.connect_timeout_seconds = connect_timeout_seconds
        self.num_ctx = num_ctx
        self.cancel_cooldown_seconds = cancel_cooldown_seconds
        self._parsed_url = parsed
        self._lock = _generation_lock(self.base_url, self.model)
        self._operation_counts: Counter[str] = Counter()
        self._diagnostics_history: list[dict[str, Any]] = []

    @property
    def request_count(self) -> int:
        return sum(self._operation_counts.values())

    @property
    def operation_counts(self) -> dict[str, int]:
        return dict(self._operation_counts)

    @property
    def diagnostics_history(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._diagnostics_history]

    def warm_up(self, *, timeout_seconds: float) -> ProviderResponse:
        schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "const": "ok"}},
            "required": ["status"],
            "additionalProperties": False,
        }
        _update_runtime(self.base_url, self.model, state="warming")
        try:
            response = self.generate(
                "Return one JSON object whose status is ok.",
                timeout_seconds=timeout_seconds,
                response_schema=schema,
                operation="warmup",
                max_output_tokens=20,
            )
            if json.loads(response.text) != {"status": "ok"}:
                raise AIProviderError(
                    "Ollama warm-up returned an unexpected structured response",
                    details={"provider": self.name, "model": self.model, "operation": "warmup"},
                )
            _update_runtime(self.base_url, self.model, state="ready", last_error=None)
            return response
        except AIProviderError:
            raise
        except (ValueError, json.JSONDecodeError) as exc:
            _update_runtime(self.base_url, self.model, state="unavailable")
            raise AIProviderError("Ollama warm-up response failed validation") from exc

    def generate(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        response_schema: dict[str, Any] | None = None,
        operation: str = "generation",
        max_output_tokens: int | None = None,
    ) -> ProviderResponse:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        token_limit = max_output_tokens or self.max_tokens
        if token_limit <= 0:
            raise ValueError("max_output_tokens must be positive")
        if not operation or len(operation) > 80:
            raise ValueError("operation must be a short non-empty label")

        acquired = self._lock.acquire(timeout=timeout_seconds)
        if not acquired:
            details = self._details(
                operation,
                timeout_seconds,
                timeout_seconds,
                layer="provider_queue",
                reached_ollama=False,
                partial_response_bytes=0,
            )
            raise AIProviderTimeout(
                f"Ollama {operation} timed out waiting for the local generation slot after "
                f"{timeout_seconds:g}s",
                details=details,
            )
        try:
            return self._generate_locked(
                prompt,
                timeout_seconds=timeout_seconds,
                response_schema=response_schema,
                operation=operation,
                token_limit=token_limit,
            )
        finally:
            self._lock.release()

    def _generate_locked(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        response_schema: dict[str, Any] | None,
        operation: str,
        token_limit: int,
    ) -> ProviderResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "format": response_schema or "json",
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_predict": token_limit,
                "num_ctx": self.num_ctx,
            },
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        connection = self._connection()
        response: http.client.HTTPResponse | None = None
        connected = False
        bytes_received = 0
        started = time.monotonic()
        self._operation_counts[operation] += 1
        _update_runtime(
            self.base_url,
            self.model,
            request_count=self.request_count,
            operations=self.operation_counts,
        )
        try:
            connection.connect()
            connected = True
            generation_started = time.monotonic()
            if connection.sock is not None:
                connection.sock.settimeout(timeout_seconds)
            connection.request(
                "POST",
                self._api_path("/api/generate"),
                body=body,
                headers={"Content-Type": "application/json", "Accept": "application/x-ndjson"},
            )
            response = connection.getresponse()
            if response.status >= 400:
                self._raise_http_error(response, operation, timeout_seconds, generation_started)

            chunks: list[str] = []
            final_payload: dict[str, Any] = {}
            transport_limit = max(1_000_000, self.max_output_characters * 12)
            while True:
                elapsed = time.monotonic() - generation_started
                remaining = timeout_seconds - elapsed
                if remaining <= 0:
                    raise TimeoutError("generation wall-clock deadline reached")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                line = response.readline(transport_limit + 1)
                if not line:
                    break
                bytes_received += len(line)
                if bytes_received > transport_limit:
                    raise AIProviderError(
                        "Ollama transport response exceeds the configured limit",
                        details=self._details(
                            operation,
                            timeout_seconds,
                            time.monotonic() - generation_started,
                            layer="http_read",
                            reached_ollama=True,
                            partial_response_bytes=bytes_received,
                        ),
                    )
                item = json.loads(line.decode("utf-8"))
                if not isinstance(item, dict):
                    raise ValueError("stream item is not an object")
                if item.get("error"):
                    raise AIProviderError(
                        f"Ollama generation failed: {str(item['error'])[:300]}",
                        details=self._details(
                            operation,
                            timeout_seconds,
                            time.monotonic() - generation_started,
                            layer="ollama_response",
                            reached_ollama=True,
                            partial_response_bytes=bytes_received,
                        ),
                    )
                chunk = item.get("response", "")
                if not isinstance(chunk, str):
                    raise ValueError("response chunk is not text")
                chunks.append(chunk)
                if sum(len(value) for value in chunks) > self.max_output_characters:
                    raise AIProviderError("Ollama generated response exceeds the configured limit")
                if item.get("done"):
                    final_payload = item
                    break

            text = "".join(chunks)
            if not text.strip():
                raise AIProviderError("Ollama returned no generated response")
            diagnostics = self._success_diagnostics(
                final_payload,
                operation=operation,
                elapsed=time.monotonic() - generation_started,
                partial_response_bytes=bytes_received,
                token_limit=token_limit,
                response_characters=len(text),
            )
            self._diagnostics_history.append(dict(diagnostics))
            _update_runtime(
                self.base_url,
                self.model,
                state="ready",
                last_error=None,
                last_operation=operation,
                last_diagnostics=diagnostics,
            )
            return ProviderResponse(
                text=text,
                provider=self.name,
                model=self.model,
                diagnostics=diagnostics,
            )
        except TimeoutError as exc:
            elapsed = time.monotonic() - started
            layer = "http_read" if connected else "http_connect"
            details = self._details(
                operation,
                timeout_seconds,
                elapsed,
                layer=layer,
                reached_ollama=connected,
                partial_response_bytes=bytes_received,
            )
            self._diagnostics_history.append(dict(details))
            _update_runtime(
                self.base_url,
                self.model,
                state="unavailable",
                last_error="generation_timeout",
                last_operation=operation,
                last_diagnostics=details,
            )
            self._close(response, connection)
            if self.cancel_cooldown_seconds:
                time.sleep(self.cancel_cooldown_seconds)
            raise AIProviderTimeout(
                f"Ollama {operation} timed out at {layer} after {elapsed:.3f}s",
                details=details,
            ) from exc
        except AIProviderError:
            raise
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            elapsed = time.monotonic() - started
            details = self._details(
                operation,
                timeout_seconds,
                elapsed,
                layer="http_connect" if not connected else "http_transport",
                reached_ollama=connected,
                partial_response_bytes=bytes_received,
            )
            self._diagnostics_history.append(dict(details))
            _update_runtime(
                self.base_url,
                self.model,
                state="unavailable",
                last_error="connection_error",
                last_operation=operation,
                last_diagnostics=details,
            )
            raise AIProviderUnavailable(
                f"Ollama is unavailable: {type(exc).__name__}: {str(exc)[:200]}",
                retryable=True,
                details=details,
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise AIProviderError(
                "Ollama returned an invalid transport response",
                details=self._details(
                    operation,
                    timeout_seconds,
                    time.monotonic() - started,
                    layer="http_decode",
                    reached_ollama=connected,
                    partial_response_bytes=bytes_received,
                ),
            ) from exc
        finally:
            self._close(response, connection)

    def _connection(self) -> http.client.HTTPConnection:
        host = self._parsed_url.hostname
        if host is None:
            raise AIProviderConfigurationError("Ollama URL has no host")
        port = self._parsed_url.port or (443 if self._parsed_url.scheme == "https" else 80)
        factory = (
            http.client.HTTPSConnection
            if self._parsed_url.scheme == "https"
            else http.client.HTTPConnection
        )
        return factory(host, port, timeout=self.connect_timeout_seconds)

    def _api_path(self, suffix: str) -> str:
        prefix = self._parsed_url.path.rstrip("/")
        return f"{prefix}{suffix}" or suffix

    def _raise_http_error(
        self,
        response: http.client.HTTPResponse,
        operation: str,
        timeout_seconds: float,
        started: float,
    ) -> None:
        body = response.read(4096)
        message = ""
        try:
            payload = json.loads(body.decode("utf-8"))
            message = str(payload.get("error", "")) if isinstance(payload, dict) else ""
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        details = self._details(
            operation,
            timeout_seconds,
            time.monotonic() - started,
            layer="http_status",
            reached_ollama=True,
            partial_response_bytes=len(body),
        )
        details["http_status"] = response.status
        if response.status == 404 and "model" in message.casefold():
            _update_runtime(
                self.base_url, self.model, state="model_missing", last_error="model_missing"
            )
            raise AIProviderModelNotFound(
                f"Ollama model was not found: {self.model}",
                retryable=False,
                details=details,
            )
        retryable = 500 <= response.status < 600
        raise AIProviderUnavailable(
            f"Ollama returned HTTP {response.status}: {message[:200] or response.reason}",
            retryable=retryable,
            details=details,
        )

    def _details(
        self,
        operation: str,
        timeout_seconds: float,
        elapsed: float,
        *,
        layer: str,
        reached_ollama: bool,
        partial_response_bytes: int,
    ) -> dict[str, Any]:
        state = ollama_runtime_status(self.base_url, self.model).get("state", "cold")
        return {
            "provider": self.name,
            "model": self.model,
            "operation": operation,
            "timeout_layer": layer,
            "configured_timeout_seconds": timeout_seconds,
            "elapsed_seconds": round(elapsed, 3),
            "model_state_before": state,
            "request_reached_ollama": reached_ollama,
            "partial_response_bytes": partial_response_bytes,
        }

    def _success_diagnostics(
        self,
        payload: dict[str, Any],
        *,
        operation: str,
        elapsed: float,
        partial_response_bytes: int,
        token_limit: int,
        response_characters: int,
    ) -> dict[str, Any]:
        keys = (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        )
        result: dict[str, Any] = {key: int(payload.get(key, 0) or 0) for key in keys}
        load_duration = result["load_duration"]
        result.update(
            provider=self.name,
            model=self.model,
            operation=operation,
            elapsed_seconds=round(elapsed, 3),
            partial_response_bytes=partial_response_bytes,
            max_output_tokens=token_limit,
            num_ctx=self.num_ctx,
            done_reason=payload.get("done_reason"),
            done=bool(payload.get("done")),
            response_characters=response_characters,
            model_load_state=("cold" if load_duration >= 2_000_000_000 else "warm"),
        )
        return result

    @staticmethod
    def _close(
        response: http.client.HTTPResponse | None,
        connection: http.client.HTTPConnection,
    ) -> None:
        if response is not None:
            try:
                response.close()
            except OSError:
                pass
        try:
            connection.close()
        except OSError:
            pass
