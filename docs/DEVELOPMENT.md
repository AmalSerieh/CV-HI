# Development

## Environment

Install production and development dependencies:

```text
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
```

The supported Python range is 3.10 through 3.12. Keep production dependencies in
`requirements.txt`, development tools in `requirements-dev.txt`, and optional NLP dependencies in
`requirements-nlp.txt`.

## Canonical Imports

New code should import from `resume_analyzer`. Root-level packages such as `ai`, `ats`, `schemas`,
and `pipeline` are retained compatibility shims and should not gain new business logic.

## Change Discipline

- Preserve schema compatibility unless a deliberate migration is supplied.
- Keep ATS, parsing-integrity, target-role, and candidate-quality concepts separate.
- Keep tests offline and use synthetic identities and fixtures.
- Mock AI providers in automated tests.
- Do not commit `.env`, resumes, runtime output, local models, caches, logs, or absolute paths.
- Add dependencies only when runtime or test code actually requires them.

## Useful Commands

```text
python scripts/doctor.py
python -m pytest -q -p no:cacheprovider
python -m ruff check .
python -m black --check .
python -m flake8 .
python -m mypy --no-incremental
python -m compileall -q resume_analyzer ai analyzers ats contracts extractors models1 schemas pipeline.py pipeline2.py
python -m pip check
```

See [Testing](TESTING.md) for the current MyPy scope.
