"""Evidence-preserving skills normalization, grouping, and deduplication."""

from __future__ import annotations

from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.providers import AIProviderError, AIProviderTimeout
from resume_analyzer.schemas import (
    PipelineReport,
    RejectedRewrite,
    SkillGroup,
    SkillItem,
    SkillsSectionRewriteResult,
)

from .contracts import SkillsProposal
from .diagnostics import bounded_rejection_message
from .parser import (
    RewriteResponseParseError,
    RewriteResponseParser,
    RewriteResponseTruncatedError,
)
from .prompts import RewritePromptBuilder
from .validator import RewriteValidator


class SkillsSectionImprover:
    _DISPLAY_VALUES = {
        "quickbooks": "QuickBooks",
        "general ledger": "General Ledger",
        "marketing": "Marketing",
        "sales": "Sales",
    }
    _ITEM_GROUPS = {
        "quickbooks": "Accounting Software",
        "caseware": "Accounting Software",
        "taxprep": "Accounting Software",
        "general ledger": "Business / Domain Knowledge",
        "microsoft excel": "Tools",
        "microsoft powerpoint": "Tools",
        "microsoft access": "Tools",
        "apple keynote": "Tools",
        "html": "Frontend",
        "html5": "Frontend",
        "css": "Frontend",
        "css3": "Frontend",
        "javascript": "Frontend",
        "typescript": "Frontend",
        "react": "Frontend",
        "tailwind css": "Frontend",
        "bootstrap": "Frontend",
        "django": "Backend",
        "flask": "Backend",
        "fastapi": "Backend",
        "node.js": "Backend",
        "rest api": "Backend",
        "rest apis": "Backend",
        "graphql": "Backend",
        "clickhouse": "Databases",
        "metabase": "Data / Analytics",
        "dagster": "Data / Analytics",
        "forecasting": "Data / Analytics",
        "data analysis": "Data / Analytics",
        "data visualization": "Data / Analytics",
        "whisper": "AI / ML",
        "ollama": "AI / ML",
        "openrouter": "AI / ML",
        "llm api": "AI / ML",
        "llm apis": "AI / ML",
        "langchain": "AI / ML",
        "timesfm": "AI / ML",
        "ai-powered automation": "AI / ML",
        "rbac": "Methods",
    }
    _CATEGORY_GROUPS = {
        "programming_languages": "Programming Languages",
        "frontend": "Frontend",
        "backend": "Backend",
        "frameworks_libraries": "Frameworks / Libraries",
        "databases": "Databases",
        "cloud_devops": "DevOps / Infrastructure",
        "bi_analytics_tools": "Data / Analytics",
        "data_ai": "AI / ML",
        "tools": "Tools",
        "productivity_tools": "Tools",
        "methods": "Methods",
        "project_management": "Methods",
        "business_domain": "Business / Domain Knowledge",
        "domain": "Business / Domain Knowledge",
        "finance_accounting": "Business / Domain Knowledge",
        "marketing_sales": "Business / Domain Knowledge",
        "hr": "Business / Domain Knowledge",
        "legal": "Business / Domain Knowledge",
        "soft_skills": "Soft Skills",
    }

    def __init__(
        self,
        *,
        prompt_builder: RewritePromptBuilder,
        parser: RewriteResponseParser,
        validator: RewriteValidator,
        max_ai_items: int = 24,
    ) -> None:
        if max_ai_items <= 0:
            raise ValueError("max_ai_items must be positive")
        self.prompt_builder = prompt_builder
        self.parser = parser
        self.validator = validator
        self.max_ai_items = max_ai_items

    def improve(
        self,
        report: PipelineReport,
        client: AIClient,
        *,
        language: str,
        timeout_seconds: float | None = None,
        max_output_tokens: int | None = None,
    ) -> tuple[SkillsSectionRewriteResult, RejectedRewrite | None]:
        original = [item.value for item in report.entities.skills]
        evidence_ids = list(
            dict.fromkeys(
                evidence_id for item in report.entities.skills for evidence_id in item.evidence_ids
            )
        )
        if not original:
            return (
                SkillsSectionRewriteResult(
                    status="unchanged",
                    method="deterministic",
                    original_items=[],
                    evidence_ids=evidence_ids,
                    warnings=["No supported skills are available to reorganize."],
                    requires_review=True,
                ),
                None,
            )
        if len(original) > self.max_ai_items:
            return (
                self._deterministic(
                    report,
                    original,
                    evidence_ids,
                    (
                        f"{len(original)} supported skills exceed the bounded local-model "
                        f"limit of {self.max_ai_items}; deterministic grouping was used."
                    ),
                ),
                None,
            )
        try:
            response = client.generate(
                self.prompt_builder.skills(report, evidence_ids, language),
                response_schema=SkillsProposal.model_json_schema(),
                timeout_seconds=timeout_seconds,
                operation="rewrite_skills",
                max_output_tokens=max_output_tokens,
            )
            proposal = self.parser.parse(
                response.text, SkillsProposal, diagnostics=response.diagnostics
            )
        except RewriteResponseTruncatedError as exc:
            return self._rejected(original, evidence_ids, None, "MODEL_OUTPUT_TRUNCATED", str(exc))
        except RewriteResponseParseError as exc:
            return self._rejected(original, evidence_ids, None, "INVALID_MODEL_RESPONSE", str(exc))
        except AIProviderTimeout:
            message = "The local model timed out while grouping skills."
            return (
                self._deterministic(
                    report,
                    original,
                    evidence_ids,
                    f"{message} Deterministic grouping was used instead.",
                ),
                self._rejection(
                    original,
                    None,
                    "AI_PROVIDER_TIMEOUT",
                    message,
                ),
            )
        except AIProviderError:
            message = "The local model was unavailable while grouping skills."
            return (
                self._deterministic(
                    report,
                    original,
                    evidence_ids,
                    f"{message} Deterministic grouping was used instead.",
                ),
                self._rejection(
                    original,
                    None,
                    "AI_PROVIDER_UNAVAILABLE",
                    message,
                ),
            )
        except ValueError as exc:
            return self._rejected(original, evidence_ids, None, "INVALID_MODEL_RESPONSE", str(exc))

        # A complete, schema-valid grouping may still omit a supported original.
        # Preserve only application-owned originals in a clearly labelled group;
        # invented model items are still rejected by the validator below.
        proposed_keys = {
            self.validator.skill_key(item) for group in proposal.groups for item in group.items
        }
        preserved_items = [
            item for item in original if self.validator.skill_key(item) not in proposed_keys
        ]
        groups_for_validation = list(proposal.groups)
        preservation_warnings: list[str] = []
        if preserved_items:
            groups_for_validation.append(SkillGroup(group="Other Skills", items=preserved_items))
            preservation_warnings.append(
                "The model omitted supported skills; the application preserved "
                "them under Other Skills."
            )
        validation = self.validator.validate_skills(
            report,
            expected_original=original,
            response_original=None,
            improved_groups=groups_for_validation,
            added_items=[],
            evidence_ids=evidence_ids,
            removed_duplicates=proposal.removed_duplicates,
        )
        if not validation.accepted:
            candidate = [item for group in groups_for_validation for item in group.items]
            return self._rejected(
                original,
                evidence_ids,
                candidate,
                validation.code or "UNSUPPORTED_FACTUAL_CLAIM",
                validation.message or "Skills rewrite was rejected",
            )

        seen: set[str] = set()
        groups: list[SkillGroup] = []
        removed = list(proposal.removed_duplicates)
        for group in groups_for_validation:
            items: list[str] = []
            for item in group.items:
                key = self.validator.skill_key(item)
                if key in seen:
                    removed.append(item)
                    continue
                seen.add(key)
                items.append(item)
            if items:
                groups.append(SkillGroup(group=group.group, items=items))
        if not groups:
            return self._rejected(
                original,
                evidence_ids,
                [],
                "INVALID_MODEL_RESPONSE",
                "Skills rewrite removed every supported skill",
            )
        expected_groups = {
            self.validator.skill_key(item.value): self._ITEM_GROUPS[
                item.value.casefold().replace("â€‘", "-").strip()
            ]
            for item in report.entities.skills
            if item.value.casefold().replace("â€‘", "-").strip() in self._ITEM_GROUPS
        }
        taxonomy_mismatches = [
            item
            for group in groups
            for item in group.items
            if (
                self.validator.skill_key(item) in expected_groups
                and group.group != expected_groups[self.validator.skill_key(item)]
            )
        ]
        if taxonomy_mismatches:
            canonical_values = {
                self.validator.skill_key(item): item for group in groups for item in group.items
            }
            deterministic = self._deterministic(
                report,
                original,
                evidence_ids,
                "The model's category labels did not match the validated "
                "application taxonomy; deterministic grouping was used.",
            )
            for group in deterministic.improved_groups:
                group.items = [
                    self._display_value(canonical_values.get(self.validator.skill_key(item), item))
                    for item in group.items
                ]
            deterministic.removed_duplicates = list(
                dict.fromkeys([*deterministic.removed_duplicates, *removed])
            )
            return (
                deterministic,
                None,
            )
        return (
            SkillsSectionRewriteResult(
                status="improved",
                method="ai",
                original_items=original,
                improved_groups=groups,
                added_items=[],
                removed_duplicates=list(dict.fromkeys(removed)),
                evidence_ids=evidence_ids,
                warnings=[*validation.warnings, *preservation_warnings],
                requires_review=validation.requires_review or bool(preservation_warnings),
            ),
            None,
        )

    def _deterministic(
        self,
        report: PipelineReport,
        original: list[str],
        evidence_ids: list[str],
        message: str,
    ) -> SkillsSectionRewriteResult:
        grouped: dict[str, list[str]] = {}
        seen: set[str] = set()
        removed: list[str] = []
        for item in report.entities.skills:
            value = item.value.strip()
            key = self.validator.skill_key(value)
            if key in seen:
                removed.append(value)
                continue
            seen.add(key)
            label = self._expected_group(item)
            grouped.setdefault(label, []).append(self._display_value(value))
        return SkillsSectionRewriteResult(
            status="improved",
            method="deterministic",
            original_items=original,
            improved_groups=[
                SkillGroup(group=label, items=items) for label, items in grouped.items() if items
            ],
            added_items=[],
            removed_duplicates=removed,
            evidence_ids=evidence_ids,
            warnings=[message],
            requires_review=True,
        )

    def _expected_group(self, item: SkillItem) -> str:
        normalized_value = item.value.casefold().replace("‑", "-").strip()
        return self._ITEM_GROUPS.get(
            normalized_value,
            self._CATEGORY_GROUPS.get(item.category or "", "Other Skills"),
        )

    def _display_value(self, value: str) -> str:
        normalized_value = value.casefold().replace("‑", "-").strip()
        return self._DISPLAY_VALUES.get(normalized_value, value)

    @staticmethod
    def _rejection(original, candidate, code, message) -> RejectedRewrite:
        message = bounded_rejection_message(message)
        return RejectedRewrite(
            component="skills_section",
            code=code,
            message=message,
            original=original,
            candidate=candidate,
        )

    @staticmethod
    def _rejected(original, evidence_ids, candidate, code, message, *, status="rejected"):
        message = bounded_rejection_message(message)
        result = SkillsSectionRewriteResult(
            status=status,
            method="ai",
            original_items=original,
            improved_groups=[],
            added_items=[],
            evidence_ids=evidence_ids,
            warnings=[message],
            requires_review=True,
        )
        rejection = RejectedRewrite(
            component="skills_section",
            code=code,
            message=message,
            original=original,
            candidate=candidate,
        )
        return result, rejection
