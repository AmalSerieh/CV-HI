"""Lazy local Hugging Face Transformers provider."""

from __future__ import annotations

from typing import Any

from .base import AIProviderError, AIProviderUnavailable, ProviderResponse


class TransformersProvider:
    name = "transformers"

    def __init__(
        self,
        model: str,
        *,
        allow_download: bool = False,
        max_new_tokens: int = 900,
    ) -> None:
        if not model.strip():
            raise ValueError("Transformers model/path must be configured explicitly")
        self.model = model.strip()
        self.allow_download = allow_download
        self.max_new_tokens = max_new_tokens
        self._generator: Any = None

    def _load(self) -> Any:
        if self._generator is not None:
            return self._generator
        try:
            from transformers import (  # type: ignore[import-not-found]
                AutoModelForCausalLM,
                AutoTokenizer,
                pipeline,
            )
        except ImportError as exc:
            raise AIProviderUnavailable(
                "Transformers provider requires the optional 'transformers' dependency"
            ) from exc
        kwargs = {"local_files_only": not self.allow_download}
        try:
            tokenizer = AutoTokenizer.from_pretrained(self.model, **kwargs)
            model = AutoModelForCausalLM.from_pretrained(self.model, **kwargs)
            self._generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
        except Exception as exc:
            raise AIProviderUnavailable(
                f"Transformers model could not be loaded locally: {type(exc).__name__}: {exc}"
            ) from exc
        return self._generator

    def generate(
        self,
        prompt: str,
        *,
        timeout_seconds: float,
        response_schema: dict[str, Any] | None = None,
        operation: str = "generation",
        max_output_tokens: int | None = None,
    ) -> ProviderResponse:
        # AIClient enforces the wall-clock timeout around this synchronous call.
        del timeout_seconds, response_schema, operation
        generator = self._load()
        try:
            output = generator(
                prompt,
                max_new_tokens=max_output_tokens or self.max_new_tokens,
                do_sample=False,
                return_full_text=False,
            )
            text = output[0]["generated_text"]
        except Exception as exc:
            raise AIProviderError(f"Transformers generation failed: {exc}") from exc
        if not isinstance(text, str) or not text.strip():
            raise AIProviderError("Transformers returned no generated response")
        return ProviderResponse(text=text, provider=self.name, model=self.model)
