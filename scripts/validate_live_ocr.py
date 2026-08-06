"""Run real English, Arabic, mixed, and OCR-bypass extraction smokes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from create_validation_documents import create_documents

from resume_analyzer.config import PipelineConfig
from resume_analyzer.environment import load_env_file
from resume_analyzer.extraction.text_extractor import TextExtractor


def _extract(extractor: TextExtractor, path: Path) -> dict[str, Any]:
    result = extractor.extract(str(path))
    if not result["success"]:
        raise RuntimeError(f"OCR extraction failed for {path.name}: {result['error']}")
    return result


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_env_file(root / ".env")
    config = PipelineConfig.from_env()
    tessdata = os.getenv("TESSDATA_PREFIX")
    if not config.tesseract_cmd or not tessdata:
        raise RuntimeError("Validated Tesseract configuration is missing from .env")

    paths = create_documents(root / "runtime" / "live-validation")
    extractor = TextExtractor(
        enable_ocr=True,
        ocr_language="eng+ara",
        tesseract_cmd=config.tesseract_cmd,
    )
    text_pdf = _extract(extractor, paths["pdf"])
    english = _extract(extractor, paths["english_scan"])
    arabic = _extract(extractor, paths["arabic_scan"])
    mixed = _extract(extractor, paths["mixed_scan"])

    if text_pdf["ocr_used"]:
        raise RuntimeError("Text-based PDF unnecessarily used OCR")
    if not all(item["ocr_used"] and item["engine"] == "ocr" for item in (english, arabic, mixed)):
        raise RuntimeError("One or more scanned PDFs did not use the OCR engine")
    if "PYTHON" not in english["text"].upper():
        raise RuntimeError("English OCR did not recognize the validation keyword")
    if not any(keyword in arabic["text"] for keyword in ("بايثون", "برمجيات", "المهارات")):
        raise RuntimeError("Arabic OCR did not recognize an Arabic validation keyword")
    if "PYTHON" not in mixed["text"].upper() or not any(
        keyword in mixed["text"] for keyword in ("برمجيات", "الويب")
    ):
        raise RuntimeError("Mixed OCR did not preserve both languages")

    print(
        json.dumps(
            {
                "text_pdf": {"engine": text_pdf["engine"], "ocr_used": False},
                "english_scan": {"engine": english["engine"], "arabic_unicode": False},
                "arabic_scan": {"engine": arabic["engine"], "arabic_unicode": True},
                "mixed_scan": {"engine": mixed["engine"], "bilingual": True},
                "languages": "eng+ara",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
