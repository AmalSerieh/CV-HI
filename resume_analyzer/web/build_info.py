"""Small source fingerprint used to detect a stale development server."""

from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


def source_fingerprint(project_root: Path | None = None) -> str:
    root = project_root or Path(__file__).resolve().parents[2]
    package = root / "resume_analyzer"
    source_suffixes = {".py", ".html", ".js", ".css"}
    files = sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and path.suffix.casefold() in source_suffixes
    )
    files.extend(path for path in (root / ".env", root / "pyproject.toml") if path.is_file())
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError:
            # An editor may briefly replace a file between rglob and read.
            # Hash an explicit marker so the running build is treated as stale
            # instead of turning an ordinary request into a 500 response.
            digest.update(b"<source-unavailable>")
        digest.update(b"\0")
    return digest.hexdigest()


class SourceFingerprintMonitor:
    def __init__(
        self,
        *,
        initial: str | None = None,
        minimum_interval_seconds: float = 1.0,
    ) -> None:
        if minimum_interval_seconds <= 0:
            raise ValueError("minimum_interval_seconds must be positive")
        self.minimum_interval_seconds = minimum_interval_seconds
        self._value = initial
        self._checked_at = time.monotonic() if initial else 0.0
        self._lock = threading.Lock()

    def __call__(self) -> str:
        now = time.monotonic()
        if self._value is not None and now - self._checked_at < self.minimum_interval_seconds:
            return self._value
        with self._lock:
            now = time.monotonic()
            if self._value is not None and now - self._checked_at < self.minimum_interval_seconds:
                return self._value
            self._value = source_fingerprint()
            self._checked_at = now
            return self._value


def build_state(
    startup_fingerprint: str,
    fingerprint_provider: Callable[[], str] = source_fingerprint,
) -> dict[str, Any]:
    current = fingerprint_provider()
    restart_required = current != startup_fingerprint
    return {
        "build_id": startup_fingerprint[:12],
        "current_source_id": current[:12],
        "restart_required": restart_required,
        "status": "stale" if restart_required else "current",
    }
