"""Inspect configured local model capabilities without loading or downloading models."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import urllib.error
import urllib.request
from typing import Any

from resume_analyzer.ai.providers.ollama_provider import ollama_runtime_status


def _ollama_tags(base_url: str, timeout: float = 1.0) -> tuple[bool, list[str], str | None]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/tags",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = [
            str(item.get("name") or item.get("model"))
            for item in payload.get("models", [])
            if item.get("name") or item.get("model")
        ]
        return True, models, None
    except (OSError, TimeoutError, urllib.error.URLError):
        return False, [], "Ollama is not reachable at the configured local endpoint."
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return False, [], "Ollama returned an invalid status response."


def model_status(*, public: bool = False) -> dict[str, Any]:
    provider = os.getenv("RESUME_AI_PROVIDER", "none").strip().casefold() or "none"
    configured_model = os.getenv("RESUME_AI_MODEL", "").strip() or None
    base_url = os.getenv("RESUME_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    reachable, ollama_models, ollama_error = _ollama_tags(base_url)
    model_available = bool(
        configured_model
        and any(
            item == configured_model or item.removesuffix(":latest") == configured_model
            for item in ollama_models
        )
    )
    runtime = ollama_runtime_status(base_url, configured_model)
    if shutil.which("ollama") is None:
        generation_state = "unavailable"
    elif not reachable:
        generation_state = "unavailable"
    elif configured_model and not model_available:
        generation_state = "model_missing"
    else:
        generation_state = runtime["state"]
    cache_configured = bool(os.getenv("RESUME_TRANSFORMERS_CACHE_DIR", "").strip())
    result: dict[str, Any] = {
        "configured_provider": provider,
        "configured_model": configured_model,
        "fallback_available": True,
        "ollama": {
            "executable_available": shutil.which("ollama") is not None,
            "reachable": reachable,
            "configured_model_available": model_available,
            "generation_state": generation_state,
            "request_count": runtime["request_count"],
            "operations": runtime["operations"],
            "last_generation": runtime.get("last_diagnostics"),
            "available_models": ollama_models,
            "error": ollama_error,
        },
        "transformers": {
            "installed": importlib.util.find_spec("transformers") is not None,
            "cache_configured": cache_configured,
            "lazy_loading": True,
        },
        "sentence_transformers": {
            "installed": importlib.util.find_spec("sentence_transformers") is not None,
            "required_for_default_pipeline": False,
        },
    }
    if not public:
        result["ollama"]["endpoint"] = base_url
    return result


def main() -> int:
    print(json.dumps(model_status(public=False), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
