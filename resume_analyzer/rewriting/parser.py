"""Strict JSON parser for focused rewrite proposals."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import ValidationError

from resume_analyzer.schemas.pipeline_schema import StrictModel

ProposalT = TypeVar("ProposalT", bound=StrictModel)
_FENCE = re.compile(r"\A\s*```(?:json)?\s*\n?(.*?)\n?```\s*\Z", re.IGNORECASE | re.DOTALL)


class RewriteResponseParseError(ValueError):
    pass


class RewriteResponseTruncatedError(RewriteResponseParseError):
    pass


class RewriteResponseParser:
    def __init__(self, *, max_characters: int = 50_000) -> None:
        self.max_characters = max_characters

    def parse(
        self,
        text: str,
        model: type[ProposalT],
        *,
        diagnostics: dict | None = None,
    ) -> ProposalT:
        if not isinstance(text, str) or not text.strip():
            raise RewriteResponseParseError("Rewrite response is empty")
        if len(text) > self.max_characters:
            raise RewriteResponseParseError("Rewrite response exceeds the configured limit")
        stripped = text.strip()
        fences = stripped.count("```")
        if fences:
            match = _FENCE.fullmatch(stripped)
            if not match or fences != 2:
                raise RewriteResponseParseError("Only one bare JSON code fence is accepted")
            stripped = match.group(1).strip()
        if self._diagnostics_truncated(diagnostics):
            raise RewriteResponseTruncatedError(
                "The local model reached its output limit before completing the response."
            )
        decoder = json.JSONDecoder()
        try:
            value, end = decoder.raw_decode(stripped)
        except json.JSONDecodeError as exc:
            if self._was_truncated(stripped, diagnostics, exc):
                raise RewriteResponseTruncatedError(
                    "The local model reached its output limit before completing the response."
                ) from exc
            raise RewriteResponseParseError(f"Invalid rewrite JSON: {exc.msg}") from exc
        if stripped[end:].strip():
            raise RewriteResponseParseError(
                "Trailing prose or multiple JSON values are not allowed"
            )
        if not isinstance(value, dict):
            raise RewriteResponseParseError("Rewrite JSON root must be an object")
        value = self._adapt_legacy(value, model)
        try:
            return model.model_validate(value)
        except ValidationError as exc:
            raise RewriteResponseParseError(
                f"Rewrite response schema validation failed: {exc}"
            ) from exc

    @staticmethod
    def _was_truncated(
        text: str,
        diagnostics: dict | None,
        error: json.JSONDecodeError,
    ) -> bool:
        info = diagnostics or {}
        if RewriteResponseParser._diagnostics_truncated(info):
            return True
        message = error.msg.casefold()
        if "unterminated string" in message:
            return True
        tail_error = error.pos >= max(0, len(text) - 3)
        incomplete_root = text.startswith(("{", "[")) and not text.endswith(("}", "]"))
        return tail_error and incomplete_root

    @staticmethod
    def _diagnostics_truncated(diagnostics: dict | None) -> bool:
        info = diagnostics or {}
        reason = str(info.get("done_reason") or "").casefold()
        if reason in {"length", "max_tokens", "token_limit"}:
            return True
        if info.get("done") is False:
            return True
        eval_count = info.get("eval_count")
        token_limit = info.get("max_output_tokens")
        if (
            isinstance(eval_count, int)
            and isinstance(token_limit, int)
            and eval_count >= token_limit
        ):
            return True
        return False

    @staticmethod
    def _adapt_legacy(value: dict, model: type[ProposalT]) -> dict:
        """Accept valid older envelopes, then validate the compact canonical contract."""

        name = model.__name__
        if name in {"SummaryProposal", "BulletProposal"}:
            changes = value.get("changes", [])
            value = {
                "improved": value.get("improved"),
                "evidence_ids": value.get("evidence_ids", []),
                "changes": [
                    item.get("description", "") if isinstance(item, dict) else item
                    for item in changes
                ],
            }
        elif name == "SkillsProposal":
            value = {
                "groups": value.get("groups", value.get("improved_groups", [])),
                "removed_duplicates": value.get("removed_duplicates", []),
            }
        return value
