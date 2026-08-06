# Testing

## Test Suite

Install development dependencies, then run the complete offline suite:

```text
python -m pytest -q -p no:cacheprovider
```

The suite covers the canonical pipeline, extraction, ATS analysis, schemas, security limits, web
behavior, CLI behavior, generalization, adversarial layouts, diagnostics, target roles,
recommendations, rewriting safety, and compatibility imports. AI calls are faked or mocked.

## Quality Checks

```text
python -m ruff check .
python -m black --check .
python -m flake8 .
python -m mypy --no-incremental
python -m compileall -q resume_analyzer ai analyzers ats contracts extractors models1 schemas pipeline.py pipeline2.py
python -m pip check
```

The MyPy command is intentionally scoped to the release-critical typed configuration,
diagnostics, and web-configuration surfaces. It does not imply whole-repository strict typing.

## Synthetic Validation Documents

Create local-only validation inputs:

```text
python scripts/create_validation_documents.py
```

This writes synthetic PDF, DOCX, English scan, Arabic scan, mixed scan, and job-description files
under ignored `runtime/live-validation/`. Generated files are not delivery assets.

## Live Web Workflow

With the web application running on port 8765 and synthetic documents generated:

```text
python scripts/validate_web_workflow.py --base-url http://127.0.0.1:8765
```

Do not use `--live-ai` in routine automated testing. It is an optional local integration smoke
test and requires a configured Ollama service and model.
