"""Minimal, dependency-free loading for the project's private local .env file."""

from __future__ import annotations

import os
from collections import OrderedDict
from pathlib import Path


def read_env_file(path: Path) -> OrderedDict[str, str]:
    values: OrderedDict[str, str] = OrderedDict()
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key.replace("_", "A").isalnum() and not key[0].isdigit():
            values[key] = value.strip().strip('"').strip("'")
    return values


def load_env_file(path: Path, *, override: bool = False) -> int:
    loaded = 0
    for key, value in read_env_file(path).items():
        if override or key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded
