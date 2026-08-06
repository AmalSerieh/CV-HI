"""Bound diagnostics before storing them in strict public rewrite contracts."""

from __future__ import annotations


def bounded_rejection_message(value: object, maximum: int = 500) -> str:
    """Return a non-empty diagnostic that always fits the schema contract."""

    message = str(value).strip() or "Rewrite proposal was rejected"
    if len(message) <= maximum:
        return message
    return message[: maximum - 3].rstrip() + "..."


__all__ = ["bounded_rejection_message"]
