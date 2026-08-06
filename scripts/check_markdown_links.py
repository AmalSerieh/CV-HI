"""Validate repository-local links in Markdown documents."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


def local_target(document: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split("#", 1)[0].strip()
    if not target or target.casefold().startswith(EXTERNAL_PREFIXES):
        return None
    return (document.parent / unquote(target)).resolve()


def broken_links(root: Path) -> list[str]:
    broken: list[str] = []
    for document in sorted(root.rglob("*.md")):
        if any(part in {".venv", "runtime"} for part in document.relative_to(root).parts):
            continue
        text = document.read_text(encoding="utf-8")
        for raw_target in LINK.findall(text):
            target = local_target(document, raw_target)
            if target is not None and not target.exists():
                broken.append(f"{document.relative_to(root)} -> {raw_target}")
    return broken


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    broken = broken_links(root)
    if broken:
        print("Broken local Markdown links:", file=sys.stderr)
        for item in broken:
            print(f"- {item}", file=sys.stderr)
        return 1
    count = sum(1 for path in root.rglob("*.md") if ".venv" not in path.relative_to(root).parts)
    print(f"Validated local links in {count} Markdown files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
