"""Validated web-only configuration with local, privacy-preserving defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _positive(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class WebSettings:
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    reload: bool = False
    public_absolute_paths: bool = False
    temp_dir: Path | None = None
    output_dir: Path = Path("outputs")
    result_ttl_minutes: int = 60
    max_upload_mb: int = 10
    max_pages: int = 20
    max_extracted_chars: int = 200_000
    max_job_description_chars: int = 30_000
    max_concurrent_analyses: int = 2
    max_docx_uncompressed_mb: int = 100
    max_docx_files: int = 2_048

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65_535:
            raise ValueError("APP_PORT must be between 1 and 65535")
        for field_name in (
            "result_ttl_minutes",
            "max_upload_mb",
            "max_pages",
            "max_extracted_chars",
            "max_job_description_chars",
            "max_concurrent_analyses",
            "max_docx_uncompressed_mb",
            "max_docx_files",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.public_absolute_paths:
            raise ValueError("Public absolute paths are not supported by the web application")
        if self.temp_dir is not None and self.temp_dir.exists() and not self.temp_dir.is_dir():
            raise ValueError("RESUME_TEMP_DIR must refer to a directory")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1_000_000

    @property
    def max_docx_uncompressed_bytes(self) -> int:
        return self.max_docx_uncompressed_mb * 1_000_000

    def prepare_runtime_directories(self) -> None:
        """Create configured private runtime directories before accepting uploads."""
        if self.temp_dir is not None:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> WebSettings:
        temp_value = os.getenv("RESUME_TEMP_DIR", "").strip()
        app_env = os.getenv("APP_ENV", "development").strip() or "development"
        return cls(
            app_env=app_env,
            host=os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=_positive("APP_PORT", 8000),
            debug=_flag("APP_DEBUG", False),
            reload=_flag("APP_RELOAD", app_env.casefold() == "development"),
            public_absolute_paths=_flag("RESUME_PUBLIC_ABSOLUTE_PATHS", False),
            temp_dir=Path(temp_value).expanduser() if temp_value else None,
            output_dir=Path(os.getenv("RESUME_OUTPUT_DIR", "outputs")),
            result_ttl_minutes=_positive("RESUME_RESULT_TTL_MINUTES", 60),
            max_upload_mb=_positive("RESUME_MAX_UPLOAD_MB", 10),
            max_pages=_positive("RESUME_MAX_PAGES", 20),
            max_extracted_chars=_positive("RESUME_MAX_EXTRACTED_CHARS", 200_000),
            max_job_description_chars=_positive("RESUME_MAX_JOB_DESCRIPTION_CHARS", 30_000),
            max_concurrent_analyses=_positive("RESUME_MAX_CONCURRENT_ANALYSES", 2),
            max_docx_uncompressed_mb=_positive("RESUME_MAX_DOCX_UNCOMPRESSED_MB", 100),
            max_docx_files=_positive("RESUME_MAX_DOCX_FILES", 2_048),
        )
