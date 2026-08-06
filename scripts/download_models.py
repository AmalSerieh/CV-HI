"""Explicitly download an optional Hugging Face model into a selected cache."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SUPPORTED_EXAMPLES = {
    "semantic": "sentence-transformers/all-MiniLM-L6-v2",
    "transformers": "Supply the exact causal language model used by your configuration",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List supported optional model modes")
    parser.add_argument("--model", help="Exact Hugging Face model identifier")
    parser.add_argument(
        "--cache-dir", help="Destination cache; defaults to RESUME_TRANSFORMERS_CACHE_DIR"
    )
    parser.add_argument(
        "--yes", action="store_true", help="Confirm that a potentially large download is intended"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list:
        for capability, model in SUPPORTED_EXAMPLES.items():
            print(f"{capability}: {model}")
        return 0
    if not args.model:
        print("--model is required; use --list for supported modes.", file=sys.stderr)
        return 2
    cache_value = args.cache_dir or os.getenv("RESUME_TRANSFORMERS_CACHE_DIR", "")
    if not cache_value:
        print("Set --cache-dir or RESUME_TRANSFORMERS_CACHE_DIR.", file=sys.stderr)
        return 2
    cache = Path(cache_value).expanduser().resolve()
    print(f"Model: {args.model}")
    print("Download size depends on the selected repository and may be several gigabytes.")
    if (
        not args.yes
        and input("Download into the configured external cache? [y/N] ").strip().casefold() != "y"
    ):
        print("Cancelled.")
        return 1
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError:
        print(
            "Install requirements-nlp.txt before downloading Hugging Face models.", file=sys.stderr
        )
        return 2
    try:
        info = HfApi().model_info(args.model, files_metadata=True)
        known_size = sum((sibling.size or 0) for sibling in (info.siblings or []))
        if known_size:
            print(f"Published file size: {known_size / 1_000_000_000:.2f} GB")
        local_path = snapshot_download(repo_id=args.model, cache_dir=cache)
    except Exception as exc:
        print(f"Model download failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not Path(local_path).is_dir() or not any(Path(local_path).iterdir()):
        print("Download did not produce a verifiable model directory.", file=sys.stderr)
        return 1
    print("Model download verified in the configured cache.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
