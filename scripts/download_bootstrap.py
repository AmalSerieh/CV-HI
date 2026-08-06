"""Download or verify the exact Bootstrap 5 assets used by the offline interface."""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

VERSION = "5.3.3"
ASSETS = {
    "bootstrap.min.css": (
        f"https://cdn.jsdelivr.net/npm/bootstrap@{VERSION}/dist/css/bootstrap.min.css",
        "3c8f27e6009ccfd710a905e6dcf12d0ee3c6f2ac7da05b0572d3e0d12e736fc8",
    ),
    "bootstrap.bundle.min.js": (
        f"https://cdn.jsdelivr.net/npm/bootstrap@{VERSION}/dist/js/bootstrap.bundle.min.js",
        "0833b2e9c3a26c258476c46266e6877fc75218625162e0460be9a3a098a61c6c",
    ),
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    target = (
        Path(__file__).resolve().parents[1]
        / "resume_analyzer"
        / "web"
        / "static"
        / "vendor"
        / "bootstrap"
    )
    target.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in ASSETS.items():
        path = target / name
        if not args.verify_only:
            with urllib.request.urlopen(url, timeout=30) as response:
                path.write_bytes(response.read())
        if not path.is_file() or _digest(path) != expected:
            print(f"Checksum verification failed: {name}")
            return 1
        print(f"Verified Bootstrap {VERSION}: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
