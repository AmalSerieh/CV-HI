#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"
. "$PROJECT_ROOT/scripts/load_env.sh"
load_local_environment "$PROJECT_ROOT/.env"
[ -x .venv/bin/python ] || {
  printf '%s\n' 'Run scripts/setup.sh first.' >&2
  exit 2
}
.venv/bin/python scripts/ensure_ollama.py --start
exec .venv/bin/python -m resume_analyzer.cli "$@"

