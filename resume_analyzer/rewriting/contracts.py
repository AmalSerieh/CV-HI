"""Proposal models and canonical rewrite contract re-exports."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import Field

from resume_analyzer.schemas.pipeline_schema import StrictModel
from resume_analyzer.schemas.rewrite_schema import (
    ExperienceBulletRewriteResult,
    RejectedRewrite,
    RewriteChange,
    RewriteResult,
    SkillGroup,
    SkillsSectionRewriteResult,
    SummaryRewriteResult,
)


class SummaryProposal(StrictModel):
    improved: str = Field(min_length=1, max_length=1_200)
    evidence_ids: list[str] = Field(min_length=1)
    changes: list[str] = Field(default_factory=list, max_length=6)


class BulletProposal(StrictModel):
    improved: str = Field(min_length=1, max_length=800)
    evidence_ids: list[str] = Field(min_length=1)
    changes: list[str] = Field(default_factory=list, max_length=6)


class SkillsProposal(StrictModel):
    groups: list[SkillGroup] = Field(min_length=1, max_length=16)
    removed_duplicates: list[str] = Field(default_factory=list)


def evidence_constrained_schema(
    model: type[SummaryProposal] | type[BulletProposal],
    evidence_ids: list[str],
) -> dict[str, Any]:
    """Constrain structured decoding to application-owned evidence identifiers."""

    schema = deepcopy(model.model_json_schema())
    allowed = list(dict.fromkeys(value for value in evidence_ids if value))
    if allowed:
        schema["properties"]["evidence_ids"]["items"] = {
            "type": "string",
            "enum": allowed,
        }
    return schema


def canonical_changes(values: list[str]) -> list[RewriteChange]:
    """Attach the compact model descriptions to the richer public contract."""

    return [RewriteChange(type="clarity", description=value[:300]) for value in values if value]


__all__ = [
    "BulletProposal",
    "canonical_changes",
    "evidence_constrained_schema",
    "ExperienceBulletRewriteResult",
    "RejectedRewrite",
    "RewriteChange",
    "RewriteResult",
    "SkillGroup",
    "SkillsProposal",
    "SkillsSectionRewriteResult",
    "SummaryProposal",
    "SummaryRewriteResult",
]
