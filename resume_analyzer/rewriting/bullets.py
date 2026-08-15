"""Conservative experience-bullet improvement."""

from __future__ import annotations

from resume_analyzer.ai.client import AIClient
from resume_analyzer.ai.providers import AIProviderError, AIProviderTimeout
from resume_analyzer.schemas import ExperienceBulletRewriteResult, PipelineReport, RejectedRewrite

from .contracts import BulletProposal, canonical_changes, evidence_constrained_schema
from .diagnostics import bounded_rejection_message
from .parser import (
    RewriteResponseParseError,
    RewriteResponseParser,
    RewriteResponseTruncatedError,
)
from .prompts import RewritePromptBuilder
from .validator import RewriteValidator


class BulletImprover:
    def __init__(
        self,
        *,
        prompt_builder: RewritePromptBuilder,
        parser: RewriteResponseParser,
        validator: RewriteValidator,
        max_characters: int = 650,
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
        experience_index: int,
        bullet_index: int,
        bullet_kind: str,
        language: str,
        timeout_seconds: float | None = None,
        max_output_tokens: int | None = None,
    ) -> tuple[ExperienceBulletRewriteResult, RejectedRewrite | None]:
        experience = report.entities.experience[experience_index]
        bullets = (
            experience.responsibilities
            if bullet_kind == "responsibility"
            else experience.achievements
        )
        original = bullets[bullet_index]
        evidence_ids = list(experience.evidence_ids)
        if not original.strip():
            return (
                ExperienceBulletRewriteResult(
                    experience_index=experience_index,
                    bullet_index=bullet_index,
                    bullet_kind=bullet_kind,
                    status="unchanged",
                    original=original,
                    improved=None,
                    evidence_ids=evidence_ids,
                    warnings=["Empty bullets are preserved."],
                    requires_review=True,
                ),
                None,
            )
        incomplete_reason = self.validator.incomplete_text_reason(original)
        if incomplete_reason:
            return (
                ExperienceBulletRewriteResult(
                    experience_index=experience_index,
                    bullet_index=bullet_index,
                    bullet_kind=bullet_kind,
                    status="unchanged",
                    original=original,
                    improved=None,
                    evidence_ids=evidence_ids,
                    warnings=[
                        "The source bullet appears incomplete; it was preserved and "
                        f"was not sent to the model ({incomplete_reason})."
                    ],
                    requires_review=True,
                ),
                None,
            )
        try:
            response = client.generate(
                self.prompt_builder.bullet(
                    report,
                    experience_index=experience_index,
                    bullet_index=bullet_index,
                    bullet_kind=bullet_kind,
                    evidence_ids=evidence_ids,
                    language=language,
                ),
                response_schema=evidence_constrained_schema(
                    BulletProposal,
                    evidence_ids,
                ),
                timeout_seconds=timeout_seconds,
                operation="rewrite_bullet",
                max_output_tokens=max_output_tokens,
            )
            proposal = self.parser.parse(
                response.text, BulletProposal, diagnostics=response.diagnostics
            )
        except RewriteResponseTruncatedError as exc:
            return self._rejected(
                experience_index,
                bullet_index,
                bullet_kind,
                original,
                evidence_ids,
                None,
                "MODEL_OUTPUT_TRUNCATED",
                str(exc),
            )
        except RewriteResponseParseError as exc:
            return self._rejected(
                experience_index,
                bullet_index,
                bullet_kind,
                original,
                evidence_ids,
                None,
                "INVALID_MODEL_RESPONSE",
                str(exc),
            )
        except AIProviderTimeout:
            return self._rejected(
                experience_index,
                bullet_index,
                bullet_kind,
                original,
                evidence_ids,
                None,
                "AI_PROVIDER_TIMEOUT",
                "The local model timed out before generating a valid bullet rewrite.",
                status="unavailable",
            )
        except AIProviderError:
            return self._rejected(
                experience_index,
                bullet_index,
                bullet_kind,
                original,
                evidence_ids,
                None,
                "AI_PROVIDER_UNAVAILABLE",
                "The local model was unavailable for the bullet rewrite.",
                status="unavailable",
            )
        except ValueError as exc:
            return self._rejected(
                experience_index,
                bullet_index,
                bullet_kind,
                original,
                evidence_ids,
                None,
                "INVALID_MODEL_RESPONSE",
                str(exc),
            )
        if len(proposal.improved) > self.max_characters:
            return self._rejected(
                experience_index,
                bullet_index,
                bullet_kind,
                original,
                evidence_ids,
                proposal.improved,
                "INVALID_MODEL_RESPONSE",
                f"Bullet exceeds {self.max_characters} characters",
            )
        validation = self.validator.validate_text(
            report,
            expected_original=original,
            response_original=None,
            improved=proposal.improved,
            evidence_ids=proposal.evidence_ids,
            output_language=language,
            allow_evidence_expansion=False,
        )
        if not validation.accepted:
            return self._rejected(
                experience_index,
                bullet_index,
                bullet_kind,
                original,
                evidence_ids,
                proposal.improved,
                validation.code or "UNSUPPORTED_FACTUAL_CLAIM",
                validation.message or "Bullet rewrite was rejected",
            )
        unchanged = self.validator.comparison_key(
            proposal.improved
        ) == self.validator.comparison_key(original)
        return (
            ExperienceBulletRewriteResult(
                experience_index=experience_index,
                bullet_index=bullet_index,
                bullet_kind=bullet_kind,
                status="unchanged" if unchanged else "improved",
                original=original,
                improved=(None if unchanged else proposal.improved),
                evidence_ids=proposal.evidence_ids,
                changes=canonical_changes(proposal.changes),
                warnings=list(validation.warnings),
                requires_review=validation.requires_review,
            ),
            None,
        )

    @staticmethod
    def _rejected(
        experience_index,
        bullet_index,
        bullet_kind,
        original,
        evidence_ids,
        candidate,
        code,
        message,
        *,
        status="rejected",
    ):
        message = bounded_rejection_message(message)
        result = ExperienceBulletRewriteResult(
            experience_index=experience_index,
            bullet_index=bullet_index,
            bullet_kind=bullet_kind,
            status=status,
            original=original,
            improved=None,
            evidence_ids=evidence_ids,
            warnings=[message],
            requires_review=True,
        )
        rejection = RejectedRewrite(
            component="experience_bullet",
            code=code,
            message=message,
            original=original,
            candidate=candidate,
            experience_index=experience_index,
            bullet_index=bullet_index,
        )
        return result, rejection
