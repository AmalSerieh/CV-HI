#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"
. "$PROJECT_ROOT/scripts/load_env.sh"
load_local_environment "$PROJECT_ROOT/.env"
MODEL=${1:-${RESUME_AI_MODEL:-}}
[ -n "$MODEL" ] || { printf '%s\n' 'Pass a model or configure RESUME_AI_MODEL.' >&2; exit 2; }
command -v ollama >/dev/null 2>&1 || { printf '%s\n' 'Ollama is not installed.' >&2; exit 1; }
ollama list >/dev/null
if ! ollama show "$MODEL" >/dev/null 2>&1; then
    printf "Model '%s' may require several GB. Download it? [y/N] " "$MODEL"
    read -r answer
    case "$answer" in y|Y|yes|YES) ;; *) printf '%s\n' 'Cancelled.'; exit 2 ;; esac
    ollama pull "$MODEL"
fi
PYTHON=.venv/bin/python
[ -x "$PYTHON" ] || PYTHON=python
"$PYTHON" scripts/verify_ollama.py
printf 'Validated: RESUME_AI_MODEL=%s\n' "$MODEL"
