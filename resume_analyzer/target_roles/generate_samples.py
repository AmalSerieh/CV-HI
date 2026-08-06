"""Regenerate deterministic sample outputs from the regression fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from .target_role_suggester import suggest_target_roles

PACKAGE_ROOT = Path(__file__).parent
FIXTURE_ROOT = PACKAGE_ROOT / "tests" / "fixtures"
OUTPUT_ROOT = PACKAGE_ROOT / "sample_outputs"
SAMPLES = {
    "arabic_ai_engineer_result.json": "arabic/ai_engineer.json",
    "english_backend_result.json": "english/backend_engineer.json",
    "mixed_full_stack_result.json": "mixed/full_stack_mixed.json",
    "accounting_result.json": "english/accountant.json",
    "data_analyst_result.json": "english/data_analyst.json",
    "insufficient_data_result.json": "malformed/empty.json",
}


def generate_samples() -> list[Path]:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for output_name, fixture_name in SAMPLES.items():
        fixture = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))
        result = suggest_target_roles(fixture["input"])
        output_path = OUTPUT_ROOT / output_name
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        written.append(output_path)
    return written


def main() -> int:
    for path in generate_samples():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
