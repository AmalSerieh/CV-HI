"""Command-line entry point for the one canonical resume pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

# ====== FIX: استيراد ContactExtractor من الموقع الصحيح ======
from resume_analyzer.extraction.contact_extractor import ContactExtractor

# تسجيل ContactExtractor في مجلد extractors المهمل
import resume_analyzer.extractors as extractors
extractors.ContactExtractor = ContactExtractor
# ============================================================

from .config import PipelineConfig
from .pipeline import ResumePipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a PDF or DOCX resume safely.")
    parser.add_argument("resume", help="PDF or DOCX resume path")
    parser.add_argument("--output", help="UTF-8 JSON report path")
    parser.add_argument("--job-description", help="Optional UTF-8 job-description file")
    parser.add_argument("--enable-recommendations", action="store_true", default=None)
    parser.add_argument("--enable-ats", action="store_true", default=None)
    parser.add_argument("--disable-ats", action="store_true")
    parser.add_argument("--enable-rewrites", action="store_true", default=None)
    parser.add_argument("--ai-provider", choices=("none", "ollama", "transformers"))
    parser.add_argument("--ai-model")
    parser.add_argument("--language", choices=("en", "ar", "mixed"))
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print the safe status summary"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        base = PipelineConfig.from_env()
        enable_ats = (
            False
            if args.disable_ats
            else (base.enable_ats if args.enable_ats is None else args.enable_ats)
        )
        config = replace(
            base,
            enable_recommendations=(
                base.enable_recommendations
                if args.enable_recommendations is None
                else args.enable_recommendations
            ),
            enable_ats=enable_ats,
            enable_rewrites=(
                base.enable_rewrites if args.enable_rewrites is None else args.enable_rewrites
            ),
            ai_provider=args.ai_provider or base.ai_provider,
            ai_model=args.ai_model or base.ai_model,
            rewrite_language=args.language or base.rewrite_language,
        )
        job_description = None
        if args.job_description:
            job_path = Path(args.job_description)
            if not job_path.is_file():
                raise ValueError(f"Job-description file does not exist: {job_path.name}")
            job_description = job_path.read_text(encoding="utf-8")
            if len(job_description) > config.max_job_description_characters:
                raise ValueError("Job description exceeds the configured character limit")
        result = ResumePipeline(config=config).analyze(
            args.resume,
            output_path=args.output,
            job_description=job_description,
        )
        summary = {
            "schema_version": result["schema_version"],
            "document": result["document"]["name"],
            "output": str(args.output) if args.output else None,
            "ats_status": result["ats"]["status"],
            "ats_compatibility_score": result["ats"].get("ats_compatibility_score"),
            "job_match_score": result["ats"].get("job_match", {}).get("match_score"),
            "rewrite_status": result["rewrites"]["status"],
            "errors": len(result["errors"]),
        }
        print(
            json.dumps(
                summary,
                ensure_ascii=False,
                allow_nan=False,
                indent=2 if args.pretty else None,
            )
        )
        return 0
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        print(f"resume-analyzer: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())