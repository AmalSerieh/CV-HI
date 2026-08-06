"""FastAPI web interface for the canonical resume pipeline."""

from .app import create_app

__all__ = ["create_app"]
