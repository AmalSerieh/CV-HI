"""Exercise deterministic and configured local-model modes with synthetic text."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from resume_analyzer import PipelineConfig, ResumePipeline
from resume_analyzer.environment import load_env_file
from resume_analyzer.schemas import PipelineReport

SYNTHETIC_RESUME = """Jordan Example
Software Engineer

Summary
Software engineer building Python and FastAPI services.

Skills
Python, FastAPI, SQL, Docker

Experience
Software Engineer | Example Labs | 2022 - Present
Built FastAPI services and wrote SQL queries.

Education
Bachelor of Computer Science | Example University | 2021
"""

SYNTHETIC_JOB = """Example Labs seeks a software engineer with Python, FastAPI,
SQL, Docker, API testing, and backend service experience."""


def _validate_common(result: dict[str, Any]) -> PipelineReport:
    report = PipelineReport.model_validate(result)
    evidence_ids = {item.id for item in report.evidence}
    for recommendation in report.recommendations:
        if not recommendation.evidence_ids or not set(recommendation.evidence_ids) <= evidence_ids:
            raise RuntimeError("A recommendation referenced missing evidence")
    serialized = json.dumps(result, ensure_ascii=False).casefold()
    if str(Path.cwd().resolve()).casefold() in serialized:
        raise RuntimeError("A public report exposed the repository's absolute path")
    if report.target_role is None:
        raise RuntimeError("Target-role analysis did not complete")
    if (
        report.ats.status not in {"complete", "partial"}
        or report.ats.job_match.status != "complete"
    ):
        raise RuntimeError(
            "ATS or job-description matching did not complete: "
            f"ats={report.ats.status}, job_match={report.ats.job_match.status}"
        )
    return report


def _run(config: PipelineConfig) -> PipelineReport:
    result = ResumePipeline(config=config).analyze_text(
        SYNTHETIC_RESUME,
        document_name="synthetic-live-resume.txt",
        job_description=SYNTHETIC_JOB,
    )
    return _validate_common(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("none", "ollama", "both"),
        default="both",
        help="Validation mode (default: both)",
    )
    args = parser.parse_args()

    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    configured = PipelineConfig.from_env()
    outcomes: dict[str, Any] = {}

    if args.mode in {"none", "both"}:
        started = time.perf_counter()
        offline = _run(
            replace(
                configured,
                ai_provider="none",
                ai_model=None,
                enable_recommendations=True,
                enable_rewrites=True,
                rewrite_sections=("summary",),
            )
        )
        if offline.module_status.recommendations.status != "fallback":
            raise RuntimeError("No-model recommendations did not use deterministic fallback")
        if offline.rewrites.status != "fallback":
            raise RuntimeError("No-model rewriting did not fail safely")
        outcomes["none"] = {
            "duration_seconds": round(time.perf_counter() - started, 3),
            "recommendations": offline.module_status.recommendations.status,
            "ats": offline.ats.status,
            "job_match": offline.ats.job_match.status,
            "rewrites": offline.rewrites.status,
            "evidence_valid": True,
        }

    if args.mode in {"ollama", "both"}:
        if configured.ai_provider.casefold() != "ollama" or not configured.ai_model:
            raise RuntimeError("The validated .env does not select an Ollama model")
        started = time.perf_counter()
        online = _run(
            replace(
                configured,
                enable_recommendations=True,
                enable_rewrites=True,
                rewrite_sections=("summary",),
            )
        )
        if online.module_status.recommendations.status != "complete":
            detail = online.module_status.recommendations.detail or "no detail"
            raise RuntimeError(f"Ollama recommendations fell back: {detail}")
        if online.module_status.recommendations.provider != "ollama":
            raise RuntimeError("Recommendations did not use the configured Ollama provider")
        if online.rewrites.provider != "ollama" or online.rewrites.status not in {
            "complete",
            "partial",
        }:
            raise RuntimeError("Ollama rewriting did not return a validated result")
        if (
            online.rewrites.summary.status == "rejected"
            and online.rewrites.summary.improved != online.rewrites.summary.original
        ):
            raise RuntimeError("A rejected summary rewrite changed canonical content")
        outcomes["ollama"] = {
            "duration_seconds": round(time.perf_counter() - started, 3),
            "model": online.rewrites.model,
            "recommendations": online.module_status.recommendations.status,
            "recommendation_provider": online.module_status.recommendations.provider,
            "ats": online.ats.status,
            "job_match": online.ats.job_match.status,
            "rewrites": online.rewrites.status,
            "summary_rewrite": online.rewrites.summary.status,
            "rewrite_rejection_codes": [item.code for item in online.rewrites.rejected_rewrites],
            "evidence_valid": True,
        }

    print(json.dumps(outcomes, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
