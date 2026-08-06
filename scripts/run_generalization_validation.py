"""Run the local live-validation matrix and store a bounded machine-readable summary."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import time
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path
from typing import Any

from resume_analyzer.config import PipelineConfig
from resume_analyzer.pipeline import ResumePipeline


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _working_set_mb() -> float | None:
    if os.name != "nt":
        return None
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    process = kernel.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(
        process,
        ctypes.byref(counters),
        counters.cb,
    ):
        return None
    return round(counters.WorkingSetSize / 1_048_576, 3)


def _active_sections(result: dict[str, Any]) -> list[str]:
    return [key for key, value in result["extraction"]["sections"].items() if value.get("content")]


def _row(path: Path) -> dict[str, Any]:
    config = replace(
        PipelineConfig.from_env(),
        enable_ocr=True,
        ocr_language=os.getenv("GENERALIZATION_OCR_LANGUAGE", "ara+eng"),
        enable_recommendations=False,
        enable_rewrites=False,
        enable_ats=True,
        integrate_target_role=False,
    )
    started = time.perf_counter()
    try:
        result = ResumePipeline(config).analyze(str(path))
        return {
            "file": path.name,
            "file_type": path.suffix.casefold(),
            "result": "passed",
            "engine": result["extraction"]["engine"],
            "ocr_used": result["extraction"]["ocr_used"],
            "ocr_status": result["extraction"]["visual_metadata"].get("contact_ocr_status"),
            "layout": result["document"]["layout"],
            "reading_order": result["extraction"]["reading_order"],
            "sections": _active_sections(result),
            "contact_fields": [
                key
                for key, value in result["entities"]["contact"].items()
                if key != "evidence_ids" and value
            ],
            "experience_count": len(result["entities"]["experience"]),
            "project_count": len(result["entities"]["projects"]),
            "education_count": len(result["entities"]["education"]),
            "skill_count": len(result["entities"]["skills"]),
            "ats_score": result["ats"]["ats_compatibility_score"],
            "ats_label": result["ats"]["score_label"],
            "parsing_integrity": result["data_quality"]["parsing_integrity_score"],
            "parsing_status": result["data_quality"]["status"],
            "warnings": [
                *result["extraction"]["warnings"],
                *(item["code"] for item in result["data_quality"]["issues"]),
            ],
            "error_count": len(result["errors"]),
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "working_set_mb": _working_set_mb(),
            "path_leaked": str(path.resolve()) in json.dumps(result),
        }
    except Exception as exc:
        return {
            "file": path.name,
            "file_type": path.suffix.casefold(),
            "result": "failed",
            "engine": "unknown",
            "ocr_used": False,
            "ocr_status": "failed",
            "layout": "unknown",
            "reading_order": "unknown",
            "sections": [],
            "contact_fields": [],
            "experience_count": 0,
            "project_count": 0,
            "education_count": 0,
            "skill_count": 0,
            "ats_score": None,
            "ats_label": "unavailable",
            "parsing_integrity": None,
            "parsing_status": "poor",
            "warnings": [f"{type(exc).__name__}: {exc}"],
            "error_count": 1,
            "runtime_seconds": round(time.perf_counter() - started, 3),
            "working_set_mb": _working_set_mb(),
            "path_leaked": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("runtime/generalization-validation"),
    )
    parser.add_argument(
        "--private-adversarial",
        type=Path,
        help="Optional private resume included in the same invariant matrix.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runtime/generalization-validation-results.json"),
    )
    parser.add_argument(
        "--include",
        nargs="*",
        help="Optional exact filenames to validate.",
    )
    args = parser.parse_args()
    paths = [
        *([args.private_adversarial] if args.private_adversarial else []),
        *sorted(args.corpus.glob("*.pdf")),
        *sorted(args.corpus.glob("*.docx")),
    ]
    if args.include:
        selected = set(args.include)
        paths = [path for path in paths if path.name in selected]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in paths:
        row = _row(path.resolve())
        rows.append(row)
        args.output.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return 1 if any(row["path_leaked"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
