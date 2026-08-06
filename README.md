# Resume Intelligence Platform

## Overview

Resume Intelligence Platform is a local-first Python application for analyzing PDF and DOCX
resumes through a web interface or command line. It extracts structured resume content and
produces:

- contact, education, experience, project, skill, language, and certification data;
- ATS compatibility findings and a bounded ATS compatibility score;
- parsing-integrity and data-quality findings;
- target-role evidence matching;
- evidence-grounded recommendations;
- optional local-AI resume rewrites;
- OCR-assisted extraction for image-based documents;
- traceable evidence and machine-readable JSON reports.

These measures have deliberately narrow meanings:

- **ATS compatibility is not a hiring probability.**
- **Target-role evidence match is not a hiring probability.**
- **Parsing integrity is not a measure of candidate quality.**

The canonical report schema remains version `2.1.0`.

## Features

- Local web workflow with upload, progress, result, and JSON-download endpoints
- CLI analysis for PDF and DOCX files
- Deterministic offline analysis with optional local Ollama enhancements
- Optional English and Arabic OCR through Tesseract
- Safe upload limits, DOCX archive checks, file-signature validation, and temporary cleanup
- English, Arabic, and mixed-language resume support
- Synthetic regression and adversarial test coverage
- Environment diagnostics for Python, packages, storage, OCR, Ollama, and frontend assets

## Requirements

- CPython `3.10`, `3.11`, or `3.12`
- `pip` and Python virtual-environment support
- Tesseract 5 with `eng` and/or `ara` language data only when OCR is needed
- Ollama only when local-AI recommendations or rewrites are enabled

No GPU is required. The default configuration uses deterministic analysis, sets
`RESUME_AI_PROVIDER=none`, and does not download models.

## Quick Start

### Windows PowerShell

```powershell
Set-Location ProjectResume-Delivery
.\scripts\setup.ps1
.\.venv\Scripts\python.exe scripts\doctor.py
.\scripts\run_web.ps1
```

Open <http://127.0.0.1:8000>.

To include test tools during setup:

```powershell
.\scripts\setup.ps1 -Dev
```

### Linux or macOS

```sh
cd ProjectResume-Delivery
sh scripts/setup.sh
.venv/bin/python scripts/doctor.py
sh scripts/run_web.sh
```

Open <http://127.0.0.1:8000>.

To include test tools during setup:

```sh
sh scripts/setup.sh --dev
```

The setup scripts create `.venv`, install declared dependencies, install the local project,
copy `.env.example` to `.env` if needed, run `pip check`, and verify imports. Review `.env`
before exposing the application beyond its default loopback address.

Manual installation commands are documented in
[Installation](docs/INSTALLATION.md).

## Configuration

The safe template is `.env.example`. The real `.env` is intentionally excluded from delivery
archives and source control.

Default behavior:

- binds to `127.0.0.1:8000`;
- keeps debug mode off;
- stores temporary state under ignored `runtime/`;
- rejects public absolute paths;
- enables ATS, parsing, recommendations, target-role analysis, and OCR attempts;
- uses deterministic recommendations and no AI provider;
- permits 10 MB uploads and at most 20 document pages.

See [Configuration](docs/CONFIGURATION.md) for every supported setting.

## Ollama Setup

Ollama is optional. Deterministic analysis and fallback recommendations work without it.

1. Install Ollama for your operating system.
2. Start its local service.
3. Pull the verified recommended model:

   ```text
   ollama pull gemma3:4b
   ```

4. In `.env`, set:

   ```dotenv
   RESUME_AI_PROVIDER=ollama
   RESUME_AI_MODEL=gemma3:4b
   RESUME_OLLAMA_BASE_URL=http://127.0.0.1:11434
   RESUME_ENABLE_REWRITES=true
   ```

5. Run diagnostics again.

The application uses bounded timeouts and validated deterministic fallbacks when optional AI is
unavailable. See [Configuration](docs/CONFIGURATION.md) and
[Troubleshooting](docs/TROUBLESHOOTING.md).

## OCR Setup

OCR is optional for text-based PDF and DOCX files. For scanned documents, install Tesseract and
the language data required by your resumes:

- `eng` for English;
- `ara` for Arabic;
- both for `TESSERACT_LANGUAGES=eng+ara`.

If Tesseract is not on `PATH`, set `TESSERACT_CMD` in `.env`. If its language data is in a custom
location, set `TESSDATA_PREFIX`. Confirm usable languages with:

```text
python scripts/doctor.py
```

Missing OCR support is reported as optional when ordinary text extraction remains available.
Detailed setup is in [Installation](docs/INSTALLATION.md).

## Running the Web App

Windows:

```powershell
.\scripts\run_web.ps1
```

Linux/macOS:

```sh
sh scripts/run_web.sh
```

The scripts load `.env`, verify required diagnostics, check optional Ollama only when selected,
and start the FastAPI application at the configured local URL.

Important endpoints:

- `/` — upload interface
- `/api/health` — health status
- `/api/system` — privacy-safe system capabilities
- `/api/models` — privacy-safe model status
- `/docs` — FastAPI API documentation

## CLI

Windows:

```powershell
.\scripts\run_cli.ps1 .\path\to\resume.pdf --pretty
.\scripts\run_cli.ps1 .\path\to\resume.docx `
  --job-description .\path\to\job-description.txt `
  --output .\runtime\outputs\report.json --pretty
```

Linux/macOS:

```sh
sh scripts/run_cli.sh ./path/to/resume.pdf --pretty
sh scripts/run_cli.sh ./path/to/resume.docx \
  --job-description ./path/to/job-description.txt \
  --output ./runtime/outputs/report.json --pretty
```

Use `--enable-rewrites --ai-provider ollama --ai-model gemma3:4b` only after configuring
Ollama. Run `python -m resume_analyzer.cli --help` for all flags.

## Diagnostics

Run one command before first use:

```text
python scripts/doctor.py
```

Use the virtual-environment Python in actual commands:

- Windows: `.\.venv\Scripts\python.exe scripts\doctor.py`
- Linux/macOS: `.venv/bin/python scripts/doctor.py`

Required failures produce a nonzero exit code. Optional Ollama and OCR capabilities are reported
without blocking deterministic operation.

## Testing

Install development dependencies and run:

```text
python -m pytest -q -p no:cacheprovider
```

Convenience commands:

- Windows: `.\scripts\run_tests.ps1`
- Linux/macOS: `sh scripts/run_tests.sh`

Quality commands and the project MyPy scope are documented in [Testing](docs/TESTING.md).

## Troubleshooting

See [Troubleshooting](docs/TROUBLESHOOTING.md) for:

- Ollama unavailable, timed out, or missing a model;
- Tesseract missing or Arabic language data unavailable;
- a port already in use;
- rejected uploads;
- corrupt or unsupported documents.

## Privacy and Security

- The default web address is loopback-only.
- Resume analysis and configured Ollama/Tesseract processing occur locally.
- The application does not require internet access for the default pipeline.
- Optional model downloads happen only through explicit setup commands.
- Uploaded temporary files and generated reports are runtime data and are not intended for source
  control.
- Public API payloads suppress local absolute paths.
- This delivery contains synthetic fixtures only and no private candidate data.

Deployment operators remain responsible for host access controls, filesystem permissions,
retention policy, and any configuration that exposes the service beyond localhost.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [User Guide](docs/USER_GUIDE.md)
- [Development](docs/DEVELOPMENT.md)
- [Testing](docs/TESTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

