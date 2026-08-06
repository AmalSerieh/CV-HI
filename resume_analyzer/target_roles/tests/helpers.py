"""Shared test-only fixture helpers."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def fixture_paths() -> list[Path]:
    return sorted(FIXTURE_ROOT.rglob("*.json"))


def load_fixture(relative: str) -> dict:
    return json.loads((FIXTURE_ROOT / relative).read_text(encoding="utf-8"))


def all_source_strings(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, str):
        output.add(value)
    elif isinstance(value, dict):
        for item in value.values():
            output.update(all_source_strings(item))
    elif isinstance(value, list):
        for item in value:
            output.update(all_source_strings(item))
    return output


def suggested_roles(result: dict) -> list[dict]:
    target = result["target_role"]
    primary = target["primary"]
    return ([] if primary is None else [primary]) + target["alternatives"]


def iter_evidence(result: dict) -> Iterable[dict]:
    for role in suggested_roles(result):
        yield from role["evidence"]
