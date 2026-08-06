"""Recommendation orchestration with conservative deterministic fallback."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.providers import AIProvider, AIProviderError
from resume_analyzer.schemas import (
    AIRecommendation,
    PipelineReport,
    RecommendationBatch,
)
from resume_analyzer.schemas.ai_schema import RecommendationArea, RecommendationSeverity

from .parser import AIResponseParseError, ResponseParser
from .prompts import PromptBuilder
from .validator import EvidenceValidator


class RecommendationEngine:
    def __init__(
        self,
        provider: AIProvider | None = None,
        *,
        timeout_seconds: float = 20.0,
        retries: int = 1,
        retry_timeouts: bool = False,
        max_output_tokens: int = 256,
        client: AIClient | None = None,
        prompt_builder: PromptBuilder | None = None,
        parser: ResponseParser | None = None,
        validator: EvidenceValidator | None = None,
    ) -> None:
        if client is not None and provider is not None and client.provider is not provider:
            raise ValueError("Recommendation client and provider must reference the same provider")
        self.provider = provider or (client.provider if client is not None else None)
        self.client = client or (
            AIClient(
                provider,
                timeout_seconds=timeout_seconds,
                retries=retries,
                retry_timeouts=retry_timeouts,
            )
            if provider
            else None
        )
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.parser = parser or ResponseParser()
        self.validator = validator or EvidenceValidator()

    def recommend(self, report: PipelineReport | Mapping[str, Any]) -> RecommendationBatch:
        canonical = (
            report if isinstance(report, PipelineReport) else PipelineReport.model_validate(report)
        )
        try:
            request = self.prompt_builder.build_request(canonical)
        except ValueError as exc:
            return self._fallback(
                canonical,
                f"recommendation_focus_unavailable:{type(exc).__name__}:{exc}",
            )
        if request.focus_evidence_id is None:
            return RecommendationBatch(
                provider="deterministic_rules",
                model=None,
                source="fallback",
                recommendations=[],
                warnings=list(
                    dict.fromkeys(
                        [
                            *request.warnings,
                            "no_grounded_actionable_gap",
                        ]
                    )
                ),
            )
        if self.provider is None or self.client is None:
            return self._fallback(
                canonical,
                *request.warnings,
                "ai_provider_not_configured",
                focus=request,
            )

        try:
            if not request.evidence_ids:
                return self._fallback(
                    canonical,
                    *request.warnings,
                    "ai_request_has_no_relevant_evidence",
                    focus=request,
                )
            response_schema = self.parser.response_schema(
                provider=self.provider.name,
                model=self.provider.model,
                evidence_ids=list(request.evidence_ids),
                focus_evidence_id=request.focus_evidence_id,
                focus_kind=request.focus_kind,
                focus_area=request.focus_area,
                focus_language=request.focus_language,
                focus_severity=request.focus_severity,
                focus_title=request.focus_title,
                focus_problem=request.focus_problem,
                focus_suggestion=request.focus_suggestion,
            )
            response = self.client.generate(
                request.prompt,
                response_schema=response_schema,
                timeout_seconds=self.timeout_seconds,
                operation="recommendation",
                max_output_tokens=self.max_output_tokens,
            )
            parsed = self.parser.parse(
                response.text,
                provider=response.provider,
                model=response.model,
            )
            focus_accepted: list[AIRecommendation] = []
            focus_rejected: list[tuple[str, str]] = []
            for recommendation in parsed.recommendations:
                if self._matches_focus_schema(recommendation, response_schema):
                    focus_accepted.append(recommendation)
                else:
                    focus_rejected.append(
                        (recommendation.id, "deterministic_focus_contract_mismatch")
                    )
            validation = self.validator.validate(focus_accepted, canonical)
        except (AIProviderError, AIResponseParseError, ValueError) as exc:
            return self._fallback(
                canonical,
                *request.warnings,
                f"ai_unavailable:{type(exc).__name__}:{exc}",
                focus=request,
            )

        warnings = list(request.warnings)
        warnings.extend(parsed.warnings)
        warnings.extend(f"rejected:{item_id}:{reason}" for item_id, reason in focus_rejected)
        warnings.extend(f"rejected:{item_id}:{reason}" for item_id, reason in validation.rejected)
        if not validation.accepted:
            return self._fallback(
                canonical,
                *(warnings or ["ai_returned_no_grounded_recommendations"]),
                focus=request,
            )
        hybrid_recommendations = [
            item.model_copy(update={"source": "hybrid"}) for item in validation.accepted
        ]
        return RecommendationBatch(
            provider=response.provider,
            model=response.model,
            source="hybrid",
            recommendations=hybrid_recommendations,
            warnings=warnings,
        )

    @staticmethod
    def _matches_focus_schema(recommendation: AIRecommendation, schema: dict[str, Any]) -> bool:
        properties = schema.get("properties", {})
        values = recommendation.model_dump(mode="json")
        for field in (
            "area",
            "severity",
            "title",
            "problem",
            "suggestion",
            "conditional",
        ):
            expected = properties.get(field, {}).get("const")
            if expected is not None and values.get(field) != expected:
                return False
        evidence_schema = properties.get("evidence_ids", {})
        expected_evidence = evidence_schema.get("items", {}).get("const")
        if expected_evidence is not None and recommendation.evidence_ids != [expected_evidence]:
            return False
        return True

    def _fallback(
        self,
        report: PipelineReport,
        *warnings: str,
        focus=None,
    ) -> RecommendationBatch:
        recommendations: list[AIRecommendation] = []
        evidence_by_path = {item.field_path: item for item in report.evidence}

        if (
            focus is not None
            and focus.focus_origin == "deterministic_ats_issue"
            and focus.focus_evidence_id
            and focus.focus_area
            and focus.focus_severity
            and focus.focus_title
            and focus.focus_problem
            and focus.focus_suggestion
        ):
            slug = hashlib.sha256(
                f"{focus.focus_issue_id}|{focus.focus_evidence_id}".encode()
            ).hexdigest()[:12]
            recommendations.append(
                AIRecommendation(
                    id=f"rec-ats-{slug}",
                    area=focus.focus_area,
                    severity=focus.focus_severity,
                    confidence=0.99,
                    title=focus.focus_title,
                    problem=focus.focus_problem,
                    suggestion=focus.focus_suggestion,
                    evidence_ids=[focus.focus_evidence_id],
                    source="fallback",
                    conditional=focus.focus_kind == "ats_missing_issue",
                )
            )
            return RecommendationBatch(
                provider="deterministic_rules",
                model=None,
                source="fallback",
                recommendations=recommendations,
                warnings=list(dict.fromkeys([*focus.warnings, *warnings])),
            )

        def add(
            area: RecommendationArea,
            severity: RecommendationSeverity,
            title: str,
            problem: str,
            suggestion: str,
            paths: list[str],
            conditional: bool = False,
        ) -> None:
            ids = [evidence_by_path[path].id for path in paths if path in evidence_by_path]
            if not ids:
                return
            slug = hashlib.sha256(f"{area}|{title}".encode()).hexdigest()[:12]
            recommendations.append(
                AIRecommendation(
                    id=f"rec-fallback-{slug}",
                    area=area,
                    severity=severity,
                    confidence=0.98,
                    title=title,
                    problem=problem,
                    suggestion=suggestion,
                    evidence_ids=list(dict.fromkeys(ids)),
                    source="fallback",
                    conditional=conditional,
                )
            )

        missing = set(report.quality.missing_sections)
        if "summary" in missing:
            add(
                "summary",
                "high",
                "Add a professional summary",
                "The summary section is missing.",
                "Add a concise summary using only skills and experience already present in the resume.",
                ["entities.summary"],
                True,
            )
        elif len(report.entities.summary.split()) < 20:
            add(
                "summary",
                "medium",
                "Strengthen the summary",
                "The current summary is very brief.",
                "Expand it with the most relevant existing skills and role evidence; do not add unsupported claims.",
                ["entities.summary"],
            )

        if "skills" in missing:
            add(
                "skills",
                "high",
                "Add a skills section",
                "The skills section is missing.",
                "Add only skills that can be supported by the existing experience, project, or education content.",
                ["entities.skills"],
                True,
            )
        elif len(report.entities.skills) < 5:
            paths = [
                f"entities.skills[{index}].value" for index in range(len(report.entities.skills))
            ]
            add(
                "skills",
                "medium",
                "Review skills coverage",
                "The resume lists only a small set of explicit skills.",
                "Review existing experience and projects for additional demonstrable skills, adding only supported items.",
                paths,
                True,
            )

        if "experience" in missing:
            add(
                "experience",
                "high",
                "Add relevant experience",
                "The experience section is missing.",
                "If applicable, add verified paid, internship, or volunteer experience with accurate dates and responsibilities.",
                ["entities.experience"],
                True,
            )
        else:
            for index, item in enumerate(report.entities.experience):
                if not item.responsibilities and not item.achievements:
                    add(
                        "experience",
                        "medium",
                        "Add evidence-based role bullets",
                        "An experience entry has no responsibility or achievement bullets.",
                        "Add concise bullets describing work actually performed; include metrics only when they can be verified.",
                        [f"entities.experience[{index}]"],
                        True,
                    )
                    break

        contact = report.entities.contact
        for field, label in (
            ("email", "email address"),
            ("phone", "phone number"),
            ("linkedin", "LinkedIn URL"),
        ):
            if not getattr(contact, field):
                add(
                    "contact",
                    "medium" if field != "linkedin" else "low",
                    f"Review missing {label}",
                    f"The {label} is missing.",
                    f"Add a valid {label} only if the candidate wants it included.",
                    [f"entities.contact.{field}"],
                    True,
                )

        if not recommendations:
            paths = [item.field_path for item in report.evidence if item.kind == "present"][:3]
            add(
                "general",
                "good",
                "Keep claims evidence-based",
                "The analyzed sections have no high-priority structural gap.",
                "Keep every resume claim specific, concise, and supported by the existing evidence.",
                paths,
            )

        return RecommendationBatch(
            provider="deterministic_rules",
            model=None,
            source="fallback",
            recommendations=recommendations,
            warnings=list(dict.fromkeys(warnings)),
        )
