"""Strict parsing of the narrowly supported provider response forms."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from resume_analyzer.schemas import RecommendationBatch


class AIResponseParseError(ValueError):
    pass


_FENCE = re.compile(r"\A\s*```(?:json)?\s*\n?(.*?)\n?```\s*\Z", re.IGNORECASE | re.DOTALL)


class ResponseParser:
    @staticmethod
    def response_schema(
        *,
        provider: str,
        model: str | None,
        evidence_ids: list[str],
        focus_evidence_id: str | None = None,
        focus_kind: str | None = None,
        focus_area: str | None = None,
        focus_language: str | None = None,
        focus_severity: str | None = None,
        focus_title: str | None = None,
        focus_problem: str | None = None,
        focus_suggestion: str | None = None,
    ) -> dict:
        """Return an Ollama-compatible, flat schema for grounded recommendations.

        Pydantic's otherwise-correct schema uses ``$defs``/``$ref`` and regex
        constraints. Some local Ollama grammars reject that combination before
        generation begins. Keep the provider grammar deliberately flat, then
        apply the stricter Pydantic contract in :meth:`parse`.
        """
        del provider, model
        evidence_item: dict[str, object] = {"type": "string"}
        if focus_evidence_id:
            evidence_item["const"] = focus_evidence_id
        elif evidence_ids:
            evidence_item["enum"] = evidence_ids
        area_schema: dict[str, object] = {
            "type": "string",
            "enum": [
                "contact",
                "summary",
                "skills",
                "education",
                "experience",
                "projects",
                "languages",
                "certifications",
                "target_role",
                "general",
            ],
        }
        if focus_area:
            area_schema = {"type": "string", "const": focus_area}
        severity_schema: dict[str, object] = {
            "type": "string",
            "enum": ["low", "medium", "high", "critical", "good"],
        }
        if focus_severity:
            severity_schema = {"type": "string", "const": focus_severity}
        conditional_schema: dict[str, object] = {"type": "boolean"}
        if focus_kind in {"present", "missing", "ats_issue", "ats_missing_issue"}:
            conditional_schema["const"] = focus_kind in {"missing", "ats_missing_issue"}
        text_schemas = ResponseParser._safe_text_schemas(
            area=focus_area,
            kind=focus_kind,
            language=focus_language,
            title=focus_title,
            problem=focus_problem,
            suggestion=focus_suggestion,
        )
        return {
            "type": "object",
            "properties": {
                "area": area_schema,
                "severity": severity_schema,
                "title": text_schemas.get(
                    "title", {"type": "string", "minLength": 1, "maxLength": 120}
                ),
                "problem": text_schemas.get(
                    "problem", {"type": "string", "minLength": 1, "maxLength": 300}
                ),
                "suggestion": text_schemas.get(
                    "suggestion", {"type": "string", "minLength": 1, "maxLength": 500}
                ),
                "evidence_ids": {
                    "type": "array",
                    "items": evidence_item,
                    "minItems": 1,
                    "maxItems": 1 if focus_evidence_id else len(evidence_ids) or 1,
                    "uniqueItems": True,
                },
                "conditional": conditional_schema,
            },
            "required": [
                "area",
                "severity",
                "title",
                "problem",
                "suggestion",
                "evidence_ids",
                "conditional",
            ],
            "additionalProperties": False,
        }

    @staticmethod
    def _safe_text_schemas(
        *,
        area: str | None,
        kind: str | None,
        language: str | None,
        title: str | None = None,
        problem: str | None = None,
        suggestion: str | None = None,
    ) -> dict[str, dict[str, object]]:
        if title and problem and suggestion:
            return {
                "title": {"type": "string", "const": title},
                "problem": {"type": "string", "const": problem},
                "suggestion": {"type": "string", "const": suggestion},
            }
        if not area or kind not in {"present", "missing"}:
            return {}
        arabic = language == "ar"
        if arabic:
            label = {
                "contact": "معلومات الاتصال",
                "summary": "الملخص",
                "skills": "قسم المهارات",
                "education": "قسم التعليم",
                "experience": "قسم الخبرة",
                "projects": "قسم المشاريع",
                "languages": "قسم اللغات",
                "certifications": "قسم الشهادات",
                "target_role": "الدور المستهدف",
                "general": "المحتوى المحدد",
            }.get(area, "المحتوى المحدد")
            if kind == "missing":
                values = {
                    "title": f"مراجعة {label} المفقود",
                    "problem": f"{label} المشار إليه غير موجود.",
                    "suggestion": f"أضف معلومات موثقة عن {label} فقط إذا كانت تنطبق على المرشح.",
                }
            else:
                values = {
                    "title": f"تحسين وضوح {label}",
                    "problem": f"يمكن جعل {label} المشار إليه أوضح وأكثر إيجازاً.",
                    "suggestion": (
                        f"حسّن صياغة {label} المشار إليه مع الحفاظ على جميع الحقائق المدعومة."
                    ),
                }
        else:
            label = {
                "contact": "contact information",
                "summary": "summary",
                "skills": "skills section",
                "education": "education section",
                "experience": "experience section",
                "projects": "projects section",
                "languages": "languages section",
                "certifications": "certifications section",
                "target_role": "target role",
                "general": "selected content",
            }.get(area, "selected content")
            if kind == "missing":
                values = {
                    "title": f"Review the missing {label}",
                    "problem": f"The cited {label} is missing.",
                    "suggestion": (
                        f"Add verified {label} information only if it applies to the candidate."
                    ),
                }
            else:
                values = {
                    "title": f"Improve {label} clarity",
                    "problem": f"The cited {label} can be clearer and more concise.",
                    "suggestion": (
                        f"Refine the cited {label} while preserving every supported fact."
                    ),
                }
        return {key: {"type": "string", "const": value} for key, value in values.items()}

    def parse(
        self,
        text: str,
        *,
        provider: str,
        model: str | None,
    ) -> RecommendationBatch:
        if not isinstance(text, str) or not text.strip():
            raise AIResponseParseError("AI response is empty")
        stripped = text.strip()
        fences = stripped.count("```")
        if fences:
            match = _FENCE.fullmatch(stripped)
            if not match or fences != 2:
                raise AIResponseParseError("Only one bare JSON code fence is accepted")
            stripped = match.group(1).strip()

        decoder = json.JSONDecoder()
        try:
            value, end = decoder.raw_decode(stripped)
        except json.JSONDecodeError as exc:
            raise AIResponseParseError(f"Invalid JSON: {exc.msg}") from exc
        if stripped[end:].strip():
            raise AIResponseParseError("Trailing prose or multiple JSON values are not allowed")

        if isinstance(value, list):
            value = {
                "schema_version": "1.0.0",
                "provider": provider,
                "model": model,
                "source": "ai",
                "recommendations": value,
                "warnings": [],
            }
        elif isinstance(value, dict):
            value = dict(value)
            if "recommendations" not in value:
                compact_keys = {
                    "area",
                    "severity",
                    "title",
                    "problem",
                    "suggestion",
                    "evidence_ids",
                    "conditional",
                }
                if set(value) != compact_keys:
                    raise AIResponseParseError(
                        "Compact recommendation object has unexpected or missing keys"
                    )
                value = {
                    "recommendations": [
                        {
                            **value,
                            "id": "rec-primary",
                            "confidence": 0.8,
                            "source": "ai",
                        }
                    ],
                    "warnings": [],
                }
            elif "warnings" not in value:
                raise AIResponseParseError(
                    "Recommendation objects must contain recommendations and warnings"
                )
        else:
            raise AIResponseParseError("The JSON root must be an object or recommendation list")

        if "provider" in value and value.get("provider") != provider:
            raise AIResponseParseError("Provider identity does not match the invoked provider")
        if "source" in value and value.get("source") != "ai":
            raise AIResponseParseError("AI responses must declare source='ai'")
        value.setdefault("schema_version", "1.0.0")
        value.setdefault("provider", provider)
        value.setdefault("model", model)
        value.setdefault("source", "ai")
        try:
            return RecommendationBatch.model_validate(value)
        except ValidationError as exc:
            raise AIResponseParseError(f"Response schema validation failed: {exc}") from exc
