"""Tesseract executable and language diagnostics."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _language_is_usable(executable: str, language: str) -> bool:
    """Ask Tesseract to initialize a language, not merely list its filename."""

    try:
        completed = subprocess.run(
            [str(Path(executable)), "--print-parameters", "-l", language],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def tesseract_status() -> dict[str, Any]:
    configured = os.getenv("TESSERACT_CMD", "").strip()
    tessdata_prefix = os.getenv("TESSDATA_PREFIX", "").strip()
    executable = configured or shutil.which("tesseract")
    if not executable:
        return {
            "installed": False,
            "languages": [],
            "english_available": False,
            "arabic_available": False,
            "combined_available": False,
            "configured_path": bool(configured),
            "tessdata_prefix": tessdata_prefix or None,
            "error": "Tesseract executable was not found.",
        }
    try:
        completed = subprocess.run(
            [str(Path(executable)), "--list-langs"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        languages = [
            line.strip()
            for line in completed.stdout.splitlines()
            if line.strip() and not line.casefold().startswith("list of available")
        ]
        ok = completed.returncode == 0
        required_languages = ("eng", "ara")
        usable_languages = [
            language
            for language in required_languages
            if language in languages and _language_is_usable(executable, language)
        ]
        unusable_languages = [
            language
            for language in required_languages
            if language in languages and language not in usable_languages
        ]
        combined_available = all(
            language in usable_languages for language in required_languages
        ) and _language_is_usable(executable, "+".join(required_languages))
        return {
            "installed": ok,
            "languages": languages,
            "usable_languages": usable_languages,
            "unusable_languages": unusable_languages,
            "english_available": "eng" in usable_languages,
            "arabic_available": "ara" in usable_languages,
            "combined_available": combined_available,
            "configured_path": bool(configured),
            "tessdata_prefix": tessdata_prefix or None,
            "error": None if ok else "Tesseract language discovery failed.",
        }
    except (OSError, subprocess.SubprocessError):
        return {
            "installed": False,
            "languages": [],
            "english_available": False,
            "arabic_available": False,
            "combined_available": False,
            "configured_path": bool(configured),
            "tessdata_prefix": tessdata_prefix or None,
            "error": "Tesseract could not be executed.",
        }
