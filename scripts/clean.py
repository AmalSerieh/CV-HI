"""Safely remove generated project artifacts; source and fixtures are never targets."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

GENERATED_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov"}
GENERATED_FILE_NAMES = {".coverage", "coverage.json", "coverage.xml"}
RUNTIME_GENERATED_DIR_NAMES = {"compile-cache", "live-validation", "logs", "ocr-validation"}


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def targets(root: Path, include_venv: bool) -> list[Path]:
    def outside_environment(path: Path) -> bool:
        return ".venv" not in path.relative_to(root).parts

    found = [
        path
        for path in root.rglob("*")
        if outside_environment(path) and path.is_dir() and path.name in GENERATED_DIR_NAMES
    ]
    found.extend(
        path
        for path in root.rglob("*")
        if outside_environment(path) and path.is_dir() and path.name.endswith(".egg-info")
    )
    found.extend(
        path
        for path in root.rglob("*")
        if outside_environment(path) and path.is_file() and path.name in GENERATED_FILE_NAMES
    )
    found.extend(
        path for path in root.rglob("*.pyc") if outside_environment(path) and path.is_file()
    )
    runtime = root / "runtime"
    found.extend(
        runtime / name for name in RUNTIME_GENERATED_DIR_NAMES if (runtime / name).is_dir()
    )
    if include_venv and (root / ".venv").is_dir():
        found.append(root / ".venv")
    collapsed: list[Path] = []
    for path in sorted(set(found), key=lambda item: (len(item.parts), str(item))):
        if not any(parent == path or parent in path.parents for parent in collapsed):
            collapsed.append(path)
    return sorted(collapsed, key=lambda path: (len(path.parts), str(path)), reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Perform removal; default is a dry run"
    )
    parser.add_argument(
        "--include-venv", action="store_true", help="Also remove the repository .venv"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    selected = targets(root, args.include_venv)
    for path in selected:
        if not _inside(root, path) or path == root:
            raise RuntimeError("Refusing to clean outside the project")
        print(("REMOVE " if args.apply else "WOULD REMOVE ") + str(path.relative_to(root)))
        if args.apply:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
    print(f"{'Removed' if args.apply else 'Found'} {len(selected)} generated paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
