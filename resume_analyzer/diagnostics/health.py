"""Application health and privacy-safe capability reports."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import Any

from resume_analyzer.schemas import SCHEMA_VERSION

from .models import model_status
from .ocr import tesseract_status

REQUIRED_IMPORTS = (
    "fastapi",
    "uvicorn",
    "jinja2",
    "multipart",
    "pydantic",
    "fitz",
    "pdfplumber",
    "docx",
)


def application_health(settings) -> dict[str, Any]:
    missing = [name for name in REQUIRED_IMPORTS if importlib.util.find_spec(name) is None]
    return {
        "status": "ok" if not missing else "degraded",
        "application": "Resume Intelligence Platform",
        "schema_version": SCHEMA_VERSION,
        "python_supported": (3, 10) <= sys.version_info[:2] < (3, 13),
        "required_dependencies": "available" if not missing else "missing",
        "missing_dependencies": missing,
        "temporary_results": True,
        "result_ttl_minutes": settings.result_ttl_minutes,
    }


def _temporary_writable(directory: Path | None) -> bool:
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix="resume-doctor-", delete=True):
            return True
    except OSError:
        return False


def system_capabilities(settings, *, public: bool = True) -> dict[str, Any]:
    package_dir = Path(__file__).resolve().parents[1]
    bootstrap_dir = package_dir / "web" / "static" / "vendor" / "bootstrap"
    return {
        "health": application_health(settings),
        "runtime": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "environment": settings.app_env,
            "local_bind_default": settings.host in {"127.0.0.1", "localhost", "::1"},
            "source_reload_enabled": settings.reload,
        },
        "storage": {
            "temporary_directory_writable": _temporary_writable(settings.temp_dir),
            "temporary_results": True,
            "absolute_paths_public": False,
        },
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "max_pages": settings.max_pages,
            "max_extracted_chars": settings.max_extracted_chars,
            "max_job_description_chars": settings.max_job_description_chars,
            "max_concurrent_analyses": settings.max_concurrent_analyses,
        },
        "models": model_status(public=public),
        "ocr": tesseract_status(),
        "frontend": {
            "bootstrap_local": (bootstrap_dir / "bootstrap.min.css").is_file()
            and (bootstrap_dir / "bootstrap.bundle.min.js").is_file(),
            "rtl_supported": True,
        },
    }
