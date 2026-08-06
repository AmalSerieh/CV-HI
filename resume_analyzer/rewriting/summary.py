"""Evidence-grounded professional summary improvement."""

from __future__ import annotations

import re

from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.providers import AIProviderError, AIProviderTimeout
from resume_analyzer.schemas import PipelineReport, RejectedRewrite, SummaryRewriteResult

from .contracts import SummaryProposal, canonical_changes, evidence_constrained_schema
from .diagnostics import bounded_rejection_message
from .parser import (
    RewriteResponseParseError,
    RewriteResponseParser,
    RewriteResponseTruncatedError,
)
from .prompts import RewritePromptBuilder
from .validator import RewriteValidator


class SummaryGenerator:
    def __init__(
        self,
        *,
        prompt_builder: RewritePromptBuilder,
        parser: RewriteResponseParser,
        validator: RewriteValidator,
        max_characters: int = 800,
    ) -> None:
        self.prompt_builder = prompt_builder
        self.parser = parser
        self.validator = validator
        self.max_characters = max_characters

    def improve(
        self,
        report: PipelineReport,
        client: AIClient,
        *,
        language: str,
        timeout_seconds: float | None = None,
        max_output_tokens: int | None = None,
    ) -> tuple[SummaryRewriteResult, RejectedRewrite | None]:
        original = report.entities.summary
        evidence_ids = self._evidence_ids(report)
        present_support = [
            item
            for item in report.evidence
            if item.id in evidence_ids and item.kind == "present" and item.value
        ]
        if not original and len(present_support) < 2:
            return (
                SummaryRewriteResult(
                    status="unchanged",
                    original="",
                    improved=None,
                    evidence_ids=evidence_ids,
                    warnings=["Insufficient evidence to generate a professional summary."],
                    requires_review=True,
                    generated_from_evidence=False,
                ),
                None,
            )

        try:
            response = client.generate(
                self.prompt_builder.summary(report, evidence_ids, language),
                response_schema=evidence_constrained_schema(
                    SummaryProposal,
                    evidence_ids,
                ),
                timeout_seconds=timeout_seconds,
                operation="rewrite_summary",
                max_output_tokens=max_output_tokens,
            )
            proposal = self.parser.parse(
                response.text, SummaryProposal, diagnostics=response.diagnostics
            )
        except RewriteResponseTruncatedError as exc:
            return self._rejected(original, evidence_ids, None, "MODEL_OUTPUT_TRUNCATED", str(exc))
        except RewriteResponseParseError as exc:
            return self._rejected(original, evidence_ids, None, "INVALID_MODEL_RESPONSE", str(exc))
        except AIProviderTimeout:
            return self._rejected(
                original,
                evidence_ids,
                None,
                "AI_PROVIDER_TIMEOUT",
                "The local model timed out before generating a valid summary rewrite.",
                status="unavailable",
            )
        except AIProviderError:
            return self._rejected(
                original,
                evidence_ids,
                None,
                "AI_PROVIDER_UNAVAILABLE",
                "The local model was unavailable for the summary rewrite.",
                status="unavailable",
            )
        except ValueError as exc:
            return self._rejected(original, evidence_ids, None, "INVALID_MODEL_RESPONSE", str(exc))

        if len(proposal.improved) > self.max_characters:
            return self._rejected(
                original,
                evidence_ids,
                proposal.improved,
                "INVALID_MODEL_RESPONSE",
                f"Summary exceeds {self.max_characters} characters",
            )
        validation = self.validator.validate_text(
            report,
            expected_original=original,
            response_original=None,
            improved=proposal.improved,
            evidence_ids=proposal.evidence_ids,
            output_language=language,
            preserve_summary_coverage=True,
        )

        def restore_supported_coverage(current: SummaryProposal):
            restored_text = self.validator.restore_omitted_summary_claims(
                report,
                original,
                current.improved,
            )
            if not restored_text or len(restored_text) > self.max_characters:
                return None
            restored_proposal = current.model_copy(update={"improved": restored_text})
            restored_validation = self.validator.validate_text(
                report,
                expected_original=original,
                response_original=None,
                improved=restored_text,
                evidence_ids=restored_proposal.evidence_ids,
                output_language=language,
                preserve_summary_coverage=True,
            )
            if not restored_validation.accepted:
                return None
            return restored_proposal, restored_validation

        coverage_restored = False
        if (
            not validation.accepted
            and validation.code == "UNSUPPORTED_FACTUAL_CLAIM"
            and (validation.message or "").startswith("Summary rewrite omitted supported content")
        ):
            restored = restore_supported_coverage(proposal)
            if restored is not None:
                proposal, validation = restored
                coverage_restored = True
        if not validation.accepted and validation.code == "UNSUPPORTED_FACTUAL_CLAIM":
            try:
                repaired_response = client.generate(
                    self.prompt_builder.summary(
                        report,
                        evidence_ids,
                        language,
                        previous_candidate=proposal.improved,
                        validation_feedback=(
                            validation.message or "The previous rewrite omitted supported content."
                        ),
                    ),
                    response_schema=evidence_constrained_schema(
                        SummaryProposal,
                        evidence_ids,
                    ),
                    timeout_seconds=timeout_seconds,
                    operation="rewrite_summary_repair",
                    max_output_tokens=max_output_tokens,
                )
                repaired = self.parser.parse(
                    repaired_response.text,
                    SummaryProposal,
                    diagnostics=repaired_response.diagnostics,
                )
                if len(repaired.improved) <= self.max_characters:
                    repaired_validation = self.validator.validate_text(
                        report,
                        expected_original=original,
                        response_original=None,
                        improved=repaired.improved,
                        evidence_ids=repaired.evidence_ids,
                        output_language=language,
                        preserve_summary_coverage=True,
                    )
                    proposal = repaired
                    validation = repaired_validation
                    restored = restore_supported_coverage(proposal)
                    if restored is not None:
                        proposal, validation = restored
                        coverage_restored = True
            except (AIProviderError, RewriteResponseParseError, ValueError):
                # Preserve the first grounded rejection if the one bounded
                # repair attempt cannot itself be parsed or validated.
                pass
        if not validation.accepted:
            return self._rejected(
                original,
                evidence_ids,
                proposal.improved,
                validation.code or "UNSUPPORTED_FACTUAL_CLAIM",
                validation.message or "Summary rewrite was rejected",
            )
        quality_message = self._quality_gate(original, proposal.improved)
        if quality_message:
            return self._rejected(
                original,
                evidence_ids,
                proposal.improved,
                "NO_MATERIAL_CHANGE",
                quality_message,
                status="unchanged",
            )
        if self.validator.comparison_key(proposal.improved) == self.validator.comparison_key(
            original
        ):
            return self._rejected(
                original,
                evidence_ids,
                None,
                "NO_MATERIAL_CHANGE",
                "No material improvement was produced.",
                status="unchanged",
            )
        generated = not bool(original)
        changes = list(proposal.changes)
        warnings = list(validation.warnings)
        if coverage_restored:
            changes.append("Restored omitted supported source content after validation.")
            warnings.append(
                "Supported source content omitted by the model was restored "
                "deterministically; review the flow."
            )
        return (
            SummaryRewriteResult(
                status="generated" if generated else "improved",
                original=original,
                improved=proposal.improved,
                evidence_ids=proposal.evidence_ids,
                changes=canonical_changes(changes),
                warnings=warnings,
                requires_review=(validation.requires_review or generated or coverage_restored),
                generated_from_evidence=generated,
            ),
            None,
        )

    @staticmethod
    def _quality_gate(original: str, candidate: str) -> str | None:
        """Reject stylistically weaker or merely inflated resume-summary prose."""

        original = " ".join(str(original or "").split())
        candidate = " ".join(str(candidate or "").split())
        if not original or not candidate:
            return None
        third_person = re.compile(
            r"(?i)^(?:(?:an?|the)\s+.{0,80}\b(?:possesses|has)\b|"
            r"the candidate\b|this professional\b)"
        )
        if third_person.search(candidate) and not third_person.search(original):
            return "The rewrite weakens concise resume style without adding material value."

        filler = {
            "a",
            "an",
            "the",
            "and",
            "with",
            "who",
            "that",
            "possesses",
            "has",
            "having",
            "professional",
            "candidate",
        }

        def content_tokens(value: str) -> set[str]:
            return {
                token
                for token in re.findall(r"[\w+#.-]+", value.casefold())
                if len(token) > 1 and token not in filler
            }

        original_tokens = content_tokens(original)
        candidate_tokens = content_tokens(candidate)
        added = candidate_tokens - original_tokens
        if len(candidate) > len(original) * 1.12 and not added:
            return "The rewrite is longer but adds no supported material information."
        if (
            original_tokens
            and candidate_tokens
            and len(added) == 0
            and len(original_tokens - candidate_tokens) <= 1
        ):
            return "No material improvement was produced."
        return None

    @staticmethod
    def _evidence_ids(report: PipelineReport) -> list[str]:
        """Select compact, entity-linked evidence in a stable priority order."""

        selected: list[str] = []
        selected.extend(
            item.id for item in report.evidence if item.field_path == "entities.summary"
        )
        for experience in report.entities.experience[:3]:
            selected.extend(experience.evidence_ids)
        for project in report.entities.projects[:2]:
            selected.extend(project.evidence_ids)
        for skill in report.entities.skills[:8]:
            selected.extend(skill.evidence_ids)
        return list(dict.fromkeys(value for value in selected if value))[:8]

    @staticmethod
    def _rejected(original, evidence_ids, candidate, code, message, *, status="rejected"):
        message = bounded_rejection_message(message)
        result = SummaryRewriteResult(
            status=status,
            original=original,
            improved=None,
            evidence_ids=evidence_ids,
            warnings=[message],
            requires_review=True,
        )
        rejection = RejectedRewrite(
            component="summary",
            code=code,
            message=message,
            original=original,
            candidate=candidate,
        )
        return result, rejection
