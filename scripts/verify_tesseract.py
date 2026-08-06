"""Verify Tesseract and report installed OCR languages."""

from __future__ import annotations

import json
from pathlib import Path

from resume_analyzer.diagnostics.ocr import tesseract_status
from resume_analyzer.environment import load_env_file


def main() -> int:
    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    report = tesseract_status()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    required = (
        report["installed"]
        and report["english_available"]
        and report["arabic_available"]
        and report["combined_available"]
    )
    return 0 if required else 1


if __name__ == "__main__":
    raise SystemExit(main())
