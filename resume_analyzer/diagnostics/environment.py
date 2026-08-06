"""Command-line environment doctor."""

from __future__ import annotations

import json

from resume_analyzer import ResumePipeline
from resume_analyzer.web.config import WebSettings

from .health import system_capabilities


def run_diagnostics() -> tuple[dict, bool]:
    settings = WebSettings.from_env()
    settings.prepare_runtime_directories()
    report = system_capabilities(settings, public=False)
    report["pipeline"] = {
        "importable": ResumePipeline is not None,
        "single_canonical_entry": "resume_analyzer.ResumePipeline",
    }
    health = report["health"]
    required_ok = (
        health["status"] == "ok"
        and report["storage"]["temporary_directory_writable"]
        and report["frontend"]["bootstrap_local"]
        and report["pipeline"]["importable"]
    )
    return report, required_ok


def main() -> int:
    try:
        report, required_ok = run_diagnostics()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "broken",
                    "error": f"Configuration error: {type(exc).__name__}",
                },
                indent=2,
            )
        )
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
