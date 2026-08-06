"""Create optional providers from explicit configuration."""

from __future__ import annotations

from .providers import AIProvider, OllamaProvider, TransformersProvider


def build_provider(
    name: str,
    *,
    model: str | None,
    allow_download: bool = False,
    ollama_base_url: str = "http://127.0.0.1:11434",
    temperature: float = 0.0,
    seed: int = 42,
    max_tokens: int = 900,
    max_output_characters: int = 50_000,
    keep_alive: str | int = "5m",
    connect_timeout_seconds: float = 5.0,
    num_ctx: int = 4096,
    cancel_cooldown_seconds: float = 2.0,
) -> AIProvider | None:
    normalized = name.strip().casefold()
    if normalized in {"", "none", "disabled", "fallback"}:
        return None
    if normalized == "ollama":
        if not model:
            raise ValueError("ai_model is required for the Ollama provider")
        return OllamaProvider(
            model,
            base_url=ollama_base_url,
            temperature=temperature,
            seed=seed,
            max_tokens=max_tokens,
            max_output_characters=max_output_characters,
            keep_alive=keep_alive,
            connect_timeout_seconds=connect_timeout_seconds,
            num_ctx=num_ctx,
            cancel_cooldown_seconds=cancel_cooldown_seconds,
        )
    if normalized in {"transformers", "huggingface", "hf"}:
        if not model:
            raise ValueError("ai_model is required for the Transformers provider")
        return TransformersProvider(model, allow_download=allow_download)
    if normalized == "mock":
        raise ValueError("MockProvider must be injected directly; it has no production default")
    raise ValueError(f"Unknown AI provider: {name}")
