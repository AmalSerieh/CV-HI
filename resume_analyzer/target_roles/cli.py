"""Command-line entry point for independent offline validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .exceptions import TargetRoleError
from .target_role_suggester import suggest_target_roles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Suggest target roles from Pipeline JSON")
    parser.add_argument("input", type=Path, help="UTF-8 Pipeline JSON file")
    parser.add_argument("--top-k", type=int, default=3, help="maximum total suggested roles")
    parser.add_argument("--minimum-confidence", type=float, default=0.20)
    parser.add_argument("--language", choices=("ar", "en", "mixed", "unknown"))
    parser.add_argument("--pretty", action="store_true", help="indent output JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("the JSON root must be an object")
        result = suggest_target_roles(
            payload,
            top_k=args.top_k,
            minimum_confidence=args.minimum_confidence,
            language=args.language,
        )
    except (OSError, json.JSONDecodeError, TargetRoleError, ValueError) as exc:
        print(f"target-role error: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
