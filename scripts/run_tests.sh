#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"
[ -x .venv/bin/python ] || {
  printf '%s\n' 'Run scripts/setup.sh --dev first.' >&2
  exit 2
}
PYTHONDONTWRITEBYTECODE=1 exec .venv/bin/python -m pytest -q -p no:cacheprovider

