"""Process-local, lazy registry for optional NLP models."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any


class OptionalModelDependencyError(RuntimeError):
    """Raised only when an explicitly requested optional model is unavailable."""


class ModelRegistry:
    _lock = Lock()
    _sbert_models: dict[str, Any] = {}
    _spacy_models: dict[str, Any] = {}

    @classmethod
    def get_sbert(
        cls,
        model_path: str,
        fallback_model_name: str = "all-MiniLM-L6-v2",
        allow_download: bool = False,
    ) -> Any:
        path = Path(model_path).resolve()
        key = str(path).casefold()
        if key in cls._sbert_models:
            return cls._sbert_models[key]
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise OptionalModelDependencyError(
                "sentence-transformers is required only when SBERT is enabled"
            ) from exc
        with cls._lock:
            if key in cls._sbert_models:
                return cls._sbert_models[key]
            if path.exists():
                model = SentenceTransformer(str(path))
            elif allow_download:
                model = SentenceTransformer(fallback_model_name)
                path.mkdir(parents=True, exist_ok=True)
                model.save(str(path))
            else:
                raise FileNotFoundError("The configured SBERT model directory was not found")
            cls._sbert_models[key] = model
            return model

    @classmethod
    def get_spacy(cls, model_name: str = "en_core_web_sm") -> Any:
        if model_name in cls._spacy_models:
            return cls._spacy_models[model_name]
        try:
            import spacy
        except ImportError as exc:
            raise OptionalModelDependencyError(
                "spaCy is required only when spaCy extraction is enabled"
            ) from exc
        with cls._lock:
            if model_name not in cls._spacy_models:
                cls._spacy_models[model_name] = spacy.load(model_name)
            return cls._spacy_models[model_name]

    get_spacy_model = get_spacy

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._sbert_models.clear()
            cls._spacy_models.clear()


__all__ = ["ModelRegistry", "OptionalModelDependencyError"]
