"""Canonical orchestration, validation, and export boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.provider_factory import build_provider
from resume_analyzer.ai.providers import AIProviderError
from resume_analyzer.ats import ATSAnalyzer
from resume_analyzer.contracts import ATSAnalyzerProvider, RecommendationProvider, RewriteProvider
from resume_analyzer.recommendations import RecommendationEngine
from resume_analyzer.recommendations.prompts import PromptBuilder
from resume_analyzer.rewriting import ResumeRewriter
from resume_analyzer.schemas import (
    ATSResult,
    PipelineMessage,
    PipelineReport,
    RewriteResult,
    TargetRoleInfo,
)

from ..config import PipelineConfig
from ..exceptions import ReportExportError
from ..extraction import DocumentExtractionBackend, ExtractionBackend


class ResumePipeline:
    """Run extraction and downstream modules against one canonical report."""

    def __init__(
        self,
        config: PipelineConfig | None = None,
        *,
        extraction_backend: ExtractionBackend | None = None,
        recommendation_engine: RecommendationProvider | None = None,
        ats_analyzer: ATSAnalyzerProvider | None = None,
        resume_rewriter: RewriteProvider | None = None,
    ) -> None:
        self.config = config or PipelineConfig.from_env()
        self.extraction_backend = extraction_backend or DocumentExtractionBackend(self.config)
        provider = None
        client = None
        needs_recommendation_provider = (
            self.config.enable_recommendations and recommendation_engine is None
        )
        needs_rewrite_provider = self.config.enable_rewrites and resume_rewriter is None
        if needs_recommendation_provider or needs_rewrite_provider:
            provider = build_provider(
                self.config.ai_provider,
                model=self.config.ai_model,
                allow_download=self.config.allow_model_download,
                ollama_base_url=self.config.ollama_base_url,
                temperature=self.config.ai_temperature,
                seed=self.config.ai_seed,
                max_tokens=self.config.ai_max_tokens,
                max_output_characters=self.config.max_model_output_characters,
                keep_alive=self.config.ollama_keep_alive,
                connect_timeout_seconds=self.config.ai_connect_timeout_seconds,
                num_ctx=self.config.ollama_num_ctx,
                cancel_cooldown_seconds=self.config.ollama_cancel_cooldown_seconds,
            )
            if provider is not None:
                client = AIClient(
                    provider,
                    timeout_seconds=self.config.ai_timeout_seconds,
                    retries=self.config.ai_retries,
                    retry_timeouts=self.config.ai_retry_timeouts,
                )
        self.ai_provider = provider
        self.ai_client = client
        self._warmup_attempted = False
        if recommendation_engine is None and self.config.enable_recommendations:
            recommendation_engine = RecommendationEngine(
                provider,
                timeout_seconds=self.config.ai_recommendation_timeout_seconds,
                retries=self.config.ai_retries,
                retry_timeouts=self.config.ai_retry_timeouts,
                max_output_tokens=self.config.recommendation_max_output_tokens,
                client=client,
                prompt_builder=PromptBuilder(
                    max_skills=self.config.recommendation_max_skills,
                    max_experience_entries=self.config.recommendation_max_experience_entries,
                    max_bullets_per_experience=(
                        self.config.recommendation_max_bullets_per_experience
                    ),
                    max_projects=self.config.recommendation_max_projects,
                    max_field_characters=self.config.recommendation_max_field_characters,
                    max_total_characters=self.config.recommendation_max_prompt_characters,
                    max_evidence_records=self.config.recommendation_max_evidence_records,
                ),
            )
        self.recommendation_engine = recommendation_engine
        self.ats_analyzer = ats_analyzer or (
            ATSAnalyzer(max_job_description_characters=self.config.max_job_description_characters)
            if self.config.enable_ats
            else None
        )
        if resume_rewriter is None and self.config.enable_rewrites:
            resume_rewriter = ResumeRewriter(
                provider,
                timeout_seconds=self.config.ai_rewrite_timeout_seconds,
                retries=self.config.ai_retries,
                retry_timeouts=self.config.ai_retry_timeouts,
                max_output_tokens=self.config.rewrite_max_output_tokens,
                summary_max_output_tokens=self.config.summary_rewrite_max_output_tokens,
                bullet_max_output_tokens=self.config.bullet_rewrite_max_output_tokens,
                skills_max_output_tokens=self.config.skills_rewrite_max_output_tokens,
                client=client,
                sections=self.config.rewrite_sections,
                output_language=self.config.rewrite_language,
                max_prompt_characters=self.config.rewrite_max_input_characters,
                max_response_characters=self.config.max_model_output_characters,
                max_summary_characters=self.config.max_summary_characters,
                max_bullet_characters=self.config.max_bullet_characters,
                max_bullets=self.config.rewrite_max_bullets,
                absolute_max_bullets=self.config.rewrite_absolute_max_bullets,
                bullet_selection=self.config.rewrite_bullet_selection,
                rewrite_all_bullets=self.config.rewrite_all_bullets,
                skills_ai_max_items=self.config.skills_rewrite_ai_max_items,
            )
        self.resume_rewriter = resume_rewriter

    def analyze(
        self,
        file_path: str,
        *,
        output_path: str | os.PathLike[str] | None = None,
        job_description: str | None = None,
    ) -> dict[str, Any]:
        report = self.extraction_backend.extract(file_path)
        report = self._complete(report, job_description=job_description)
        result = report.to_json_dict()
        if output_path is not None:
            self.export(result, output_path)
        return result

    def analyze_text(
        self,
        text: str,
        *,
        document_name: str = "inline.txt",
        output_path: str | os.PathLike[str] | None = None,
        job_description: str | None = None,
    ) -> dict[str, Any]:
        report = self.extraction_backend.extract_text(text, document_name=document_name)
        report = self._complete(report, job_description=job_description)
        result = report.to_json_dict()
        if output_path is not None:
            self.export(result, output_path)
        return result

    def _complete(
        self, report: PipelineReport, *, job_description: str | None = None
    ) -> PipelineReport:
        current = PipelineReport.model_validate(report)
        current = self._warm_ai(current)
        if self.config.integrate_target_role:
            current = self._attach_target_role(current)
        if self.config.enable_ats and self.ats_analyzer is not None:
            current = self._attach_ats(current, job_description=job_description)
        if self.config.enable_recommendations and self.recommendation_engine is not None:
            current = self._attach_recommendations(current)
        if self.config.enable_rewrites and self.resume_rewriter is not None:
            current = self._attach_rewrites(current)
        return PipelineReport.model_validate(current.to_json_dict())

    def _warm_ai(self, report: PipelineReport) -> PipelineReport:
        if (
            self._warmup_attempted
            or not self.config.ai_warmup
            or self.ai_provider is None
            or not hasattr(self.ai_provider, "warm_up")
        ):
            return report
        self._warmup_attempted = True
        try:
            self.ai_provider.warm_up(
                timeout_seconds=self.config.ai_warmup_timeout_seconds,
            )
            return report
        except (KeyboardInterrupt, SystemExit):
            raise
        except (AIProviderError, ValueError) as exc:
            data = report.to_json_dict()
            data["warnings"].append(
                PipelineMessage(
                    stage="ai_warmup",
                    code="ai_warmup_failed",
                    message=f"{type(exc).__name__}: {exc}",
                    recoverable=True,
                ).model_dump(mode="json")
            )
            return PipelineReport.model_validate(data)

    def _attach_target_role(self, report: PipelineReport) -> PipelineReport:
        data = report.to_json_dict()
        try:
            from resume_analyzer.target_roles import attach_target_role, suggest_target_roles

            suggestion = suggest_target_roles(data)
            merged = attach_target_role(data, suggestion)
            data["target_role"] = TargetRoleInfo.model_validate(merged["target_role"]).model_dump(
                mode="json"
            )
            data["module_status"]["target_role"] = {
                "status": "complete",
                "provider": "deterministic_target_roles",
                "detail": None,
            }
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            data["target_role"] = None
            data["module_status"]["target_role"] = {
                "status": "failed",
                "provider": "deterministic_target_roles",
                "detail": f"{type(exc).__name__}: {exc}",
            }
            data["warnings"].append(
                PipelineMessage(
                    stage="target_role",
                    code="target_role_integration_failed",
                    message=f"{type(exc).__name__}: {exc}",
                    recoverable=True,
                ).model_dump(mode="json")
            )
        return PipelineReport.model_validate(data)

    def _attach_recommendations(self, report: PipelineReport) -> PipelineReport:
        data = report.to_json_dict()
        engine = self.recommendation_engine
        if engine is None:
            return report
        try:
            batch = engine.recommend(report)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            # A custom provider/engine cannot prevent the safe fallback.
            batch = RecommendationEngine().recommend(report)
            batch.warnings.append(f"custom_engine_failed:{type(exc).__name__}:{exc}")

        data["recommendations"] = [item.model_dump(mode="json") for item in batch.recommendations]
        data["module_status"]["recommendations"] = {
            "status": "fallback" if batch.source == "fallback" else "complete",
            "provider": batch.provider,
            "model": batch.model,
            "detail": "; ".join(batch.warnings) or None,
        }
        for warning in batch.warnings:
            public_warning = self._public_recommendation_warning(warning)
            if public_warning is None:
                continue
            code, message = public_warning
            data["warnings"].append(
                PipelineMessage(
                    stage="recommendations",
                    code=code,
                    message=message,
                    recoverable=True,
                ).model_dump(mode="json")
            )
        return PipelineReport.model_validate(data)

    @staticmethod
    def _public_recommendation_warning(warning: str) -> tuple[str, str] | None:
        """Keep projection telemetry internal and expose only actionable failures."""

        normalized = str(warning or "")
        if normalized.startswith("ai_unavailable:AIProviderTimeout:"):
            return (
                "AI_PROVIDER_TIMEOUT",
                (
                    "The local model timed out while generating a recommendation; "
                    "a deterministic evidence-based recommendation was used."
                ),
            )
        if normalized.startswith("custom_engine_failed:"):
            return (
                "RECOMMENDATION_FALLBACK_APPLIED",
                (
                    "The configured recommendation engine was unavailable; "
                    "a deterministic evidence-based recommendation was used."
                ),
            )
        # Bounded-projection notices and rejected model candidates remain in
        # module_status.detail for diagnostics. They are not user problems.
        return None

    def _attach_ats(self, report: PipelineReport, *, job_description: str | None) -> PipelineReport:
        data = report.to_json_dict()
        analyzer = self.ats_analyzer
        if analyzer is None:
            return report
        try:
            result = analyzer.analyze(report, job_description=job_description)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            result = ATSResult(
                status="failed",
                warnings=[f"ATS analysis failed: {type(exc).__name__}: {exc}"],
            )
        data["ats"] = result.model_dump(mode="json")
        data["module_status"]["ats"] = {
            "status": result.status,
            "provider": result.provider,
            "detail": "; ".join(result.warnings) or None,
        }
        for warning in result.warnings:
            data["warnings"].append(
                PipelineMessage(
                    stage="ats",
                    code="ats_warning",
                    message=warning,
                    recoverable=True,
                ).model_dump(mode="json")
            )
        return PipelineReport.model_validate(data)

    def _attach_rewrites(self, report: PipelineReport) -> PipelineReport:
        data = report.to_json_dict()
        rewriter = self.resume_rewriter
        if rewriter is None:
            return report
        try:
            result = rewriter.rewrite(report)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            result = RewriteResult(
                status="failed",
                provider=None,
                warnings=[f"Resume rewriting failed: {type(exc).__name__}: {exc}"],
            )
        data["rewrites"] = result.model_dump(mode="json")
        data["module_status"]["rewrites"] = {
            "status": result.status,
            "provider": result.provider,
            "model": result.model,
            "detail": "; ".join(result.warnings) or None,
        }
        for warning in result.warnings:
            data["warnings"].append(
                PipelineMessage(
                    stage="rewrites",
                    code="rewrite_warning",
                    message=warning,
                    recoverable=True,
                ).model_dump(mode="json")
            )
        return PipelineReport.model_validate(data)

    @staticmethod
    def export(
        report: PipelineReport | dict[str, Any],
        output_path: str | os.PathLike[str],
    ) -> str:
        canonical = (
            report if isinstance(report, PipelineReport) else PipelineReport.model_validate(report)
        )
        data = canonical.to_json_dict()
        path = Path(output_path)
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            serialized = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
            temporary.write_text(serialized, encoding="utf-8")
            os.replace(temporary, path)
        except OSError as exc:
            try:
                if temporary.exists():
                    temporary.unlink()
            except OSError:
                pass
            raise ReportExportError(f"Could not export report to {path}: {exc}") from exc
        return str(path.resolve())
