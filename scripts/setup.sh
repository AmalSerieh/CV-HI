#!/usr/bin/env sh
set -eu
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PROJECT_ROOT"
INSTALL_DEV=false
INSTALL_NLP=false
for argument in "$@"; do
  [ "$argument" = "--dev" ] && INSTALL_DEV=true
  [ "$argument" = "--nlp" ] && INSTALL_NLP=true
done
python3 -c 'import sys; assert (3,10) <= sys.version_info[:2] < (3,13), "Python 3.10-3.13 is required"'
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
[ "$INSTALL_DEV" = false ] || .venv/bin/python -m pip install -r requirements-dev.txt
[ "$INSTALL_NLP" = false ] || .venv/bin/python -m pip install -r requirements-nlp.txt
.venv/bin/python -m pip install -e . --no-deps
[ -f .env ] || cp .env.example .env
.venv/bin/python -m pip check
.venv/bin/python -c 'from resume_analyzer import ResumePipeline; from resume_analyzer.web.app import app; print("Import smoke passed")'
printf '%s\n' 'Setup complete.' 'Run: .venv/bin/python scripts/doctor.py' 'Start: ./scripts/run_web.sh'
