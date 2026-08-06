"""Verify and optionally benchmark configured Ollama capabilities with synthetic data."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from validate_live_pipeline import SYNTHETIC_JOB, SYNTHETIC_RESUME

from resume_analyzer import PipelineConfig, ResumePipeline
from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.provider_factory import build_provider
from resume_analyzer.ai.providers import AIProviderError, OllamaProvider
from resume_analyzer.diagnostics.models import model_status, ollama_runtime_status
from resume_analyzer.environment import load_env_file
from resume_analyzer.recommendations import RecommendationEngine
from resume_analyzer.recommendations.prompts import PromptBuilder
from resume_analyzer.rewriting import ResumeRewriter
from resume_analyzer.schemas import PipelineReport


def _seconds(value: int | None) -> float:
    return round(int(value or 0) / 1_000_000_000, 3)


def _timing(response) -> dict[str, Any]:
    diagnostics = dict(response.diagnostics or {})
    return {
        "elapsed_seconds": diagnostics.get("elapsed_seconds"),
        "total_seconds": _seconds(diagnostics.get("total_duration")),
        "load_seconds": _seconds(diagnostics.get("load_duration")),
        "prompt_tokens": diagnostics.get("prompt_eval_count"),
        "prompt_eval_seconds": _seconds(diagnostics.get("prompt_eval_duration")),
        "output_tokens": diagnostics.get("eval_count"),
        "output_eval_seconds": _seconds(diagnostics.get("eval_duration")),
        "done_reason": diagnostics.get("done_reason"),
    }


def _provider(config: PipelineConfig) -> OllamaProvider:
    provider = build_provider(
        "ollama",
        model=config.ai_model,
        ollama_base_url=config.ollama_base_url,
        temperature=config.ai_temperature,
        seed=config.ai_seed,
        max_tokens=config.ai_max_tokens,
        max_output_characters=config.max_model_output_characters,
        keep_alive=config.ollama_keep_alive,
        connect_timeout_seconds=config.ai_connect_timeout_seconds,
        num_ctx=config.ollama_num_ctx,
        cancel_cooldown_seconds=config.ollama_cancel_cooldown_seconds,
    )
    if not isinstance(provider, OllamaProvider):
        raise RuntimeError("Configured provider is not Ollama")
    return provider


def _canonical_fixture(config: PipelineConfig) -> PipelineReport:
    offline = replace(
        config,
        ai_provider="none",
        ai_model=None,
        ai_warmup=False,
        enable_ocr=False,
        enable_recommendations=False,
        enable_rewrites=False,
    )
    return PipelineReport.model_validate(
        ResumePipeline(offline).analyze_text(
            SYNTHETIC_RESUME,
            document_name="synthetic-ollama-diagnostic.txt",
            job_description=SYNTHETIC_JOB,
        )
    )


def _benchmark(config: PipelineConfig, provider: OllamaProvider) -> dict[str, Any]:
    report = _canonical_fixture(config)
    client = AIClient(
        provider,
        timeout_seconds=config.ai_timeout_seconds,
        retries=config.ai_retries,
        retry_timeouts=config.ai_retry_timeouts,
    )
    prompt_builder = PromptBuilder(
        max_skills=config.recommendation_max_skills,
        max_experience_entries=config.recommendation_max_experience_entries,
        max_bullets_per_experience=config.recommendation_max_bullets_per_experience,
        max_projects=config.recommendation_max_projects,
        max_field_characters=config.recommendation_max_field_characters,
        max_total_characters=config.recommendation_max_prompt_characters,
        max_evidence_records=config.recommendation_max_evidence_records,
    )
    request = prompt_builder.build_request(report)
    started = time.perf_counter()
    recommendations = RecommendationEngine(
        provider,
        client=client,
        timeout_seconds=config.ai_recommendation_timeout_seconds,
        retries=config.ai_retries,
        retry_timeouts=config.ai_retry_timeouts,
        max_output_tokens=config.recommendation_max_output_tokens,
        prompt_builder=prompt_builder,
    ).recommend(report)
    recommendation_seconds = time.perf_counter() - started

    started = time.perf_counter()
    rewrites = ResumeRewriter(
        provider,
        client=client,
        timeout_seconds=config.ai_rewrite_timeout_seconds,
        retries=config.ai_retries,
        retry_timeouts=config.ai_retry_timeouts,
        max_output_tokens=config.rewrite_max_output_tokens,
        summary_max_output_tokens=config.summary_rewrite_max_output_tokens,
        bullet_max_output_tokens=config.bullet_rewrite_max_output_tokens,
        skills_max_output_tokens=config.skills_rewrite_max_output_tokens,
        sections=("summary",),
        max_prompt_characters=config.rewrite_max_input_characters,
        max_response_characters=config.max_model_output_characters,
        max_summary_characters=config.max_summary_characters,
        max_bullet_characters=config.max_bullet_characters,
        max_bullets=config.rewrite_max_bullets,
    ).rewrite(report)
    rewrite_seconds = time.perf_counter() - started
    return {
        "recommendation": {
            "duration_seconds": round(recommendation_seconds, 3),
            "status": "complete" if recommendations.source == "ai" else "fallback",
            "provider": recommendations.provider,
            "recommendation_count": len(recommendations.recommendations),
            "warnings": recommendations.warnings,
            "prompt_characters": len(request.prompt),
            "evidence_records": len(request.evidence_ids),
        },
        "rewrite": {
            "duration_seconds": round(rewrite_seconds, 3),
            "status": rewrites.status,
            "provider": rewrites.provider,
            "summary_status": rewrites.summary.status,
            "rejection_codes": [item.code for item in rewrites.rejected_rewrites],
            "warnings": rewrites.warnings,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Also run canonical recommendation and summary-rewrite smoke tests.",
    )
    args = parser.parse_args(argv)
    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    config = PipelineConfig.from_env()
    report = model_status(public=False)
    ollama = report["ollama"]
    output: dict[str, Any] = {
        "configured_provider": config.ai_provider,
        "configured_model": config.ai_model,
        "endpoint": ollama.get("endpoint"),
        "service_reachable": ollama["reachable"],
        "model_available": ollama["configured_model_available"],
        "generation_state": ollama["generation_state"],
        "warmup": {"status": "not_run"},
        "structured_smoke": {"status": "not_run"},
    }
    if config.ai_provider.casefold() != "ollama":
        output["status"] = "not_required"
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    if not ollama["reachable"]:
        output.update(status="unavailable", failure="ollama_service_unavailable")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1
    if not config.ai_model or not ollama["configured_model_available"]:
        output.update(status="model_missing", failure="configured_model_missing")
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1

    provider = _provider(config)
    try:
        warm = provider.warm_up(timeout_seconds=config.ai_warmup_timeout_seconds)
        output["warmup"] = {"status": "ready", **_timing(warm)}
        schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "const": "ok"}},
            "required": ["status"],
            "additionalProperties": False,
        }
        tiny = provider.generate(
            "Return one JSON object whose status is ok.",
            timeout_seconds=config.ai_warmup_timeout_seconds,
            response_schema=schema,
            operation="diagnostic_structured_smoke",
            max_output_tokens=20,
        )
        valid = json.loads(tiny.text) == {"status": "ok"}
        output["structured_smoke"] = {
            "status": "complete" if valid else "schema_rejected",
            **_timing(tiny),
        }
        if args.benchmark:
            output["benchmark"] = _benchmark(config, provider)
    except (AIProviderError, ValueError, json.JSONDecodeError) as exc:
        output.update(
            status="failed",
            failure=type(exc).__name__,
            failure_detail=str(exc)[:500],
            generation_state=ollama_runtime_status(config.ollama_base_url, config.ai_model).get(
                "state"
            ),
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1

    runtime = ollama_runtime_status(config.ollama_base_url, config.ai_model)
    output.update(
        status="ready",
        generation_state=runtime["state"],
        provider_request_count=provider.request_count,
        provider_operations=provider.operation_counts,
        provider_diagnostics=provider.diagnostics_history,
    )
    required_ok = output["structured_smoke"]["status"] == "complete"
    if args.benchmark:
        benchmark = output["benchmark"]
        if config.enable_recommendations:
            required_ok = required_ok and benchmark["recommendation"]["status"] == "complete"
        if config.enable_rewrites:
            required_ok = required_ok and benchmark["rewrite"]["provider"] == "ollama"
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
