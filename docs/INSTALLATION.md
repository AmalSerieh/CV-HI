# Installation

## Supported Python

Use CPython 3.10, 3.11, or 3.12. Python 3.13 and later are outside the declared compatibility
range for this release.

## Automated Setup

Windows PowerShell:

```powershell
.\scripts\setup.ps1
```

Linux/macOS:

```sh
sh scripts/setup.sh
```

Add `-Dev` on PowerShell or `--dev` on POSIX systems to install test and quality tools. Add
`-Nlp` or `--nlp` only for the optional local Transformers integration.

## Manual Setup

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
Copy-Item .env.example .env
python -m pip check
python scripts\doctor.py
```

Linux/macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
cp .env.example .env
python -m pip check
python scripts/doctor.py
```

## Tesseract OCR

Tesseract is an external executable; `pytesseract` alone does not install it.

- Install Tesseract 5 using the supported package or installer for the client operating system.
- Install the `eng` trained data for English OCR.
- Install the `ara` trained data for Arabic OCR.
- Ensure `tesseract` is on `PATH`, or set its executable in `TESSERACT_CMD`.
- Set `TESSDATA_PREFIX` only when language files live outside the installation's normal
  `tessdata` directory.

Common Debian/Ubuntu packages are `tesseract-ocr`, `tesseract-ocr-eng`, and
`tesseract-ocr-ara`. Package names on other systems may differ.

Validate the actual executable and language initialization:

```text
python scripts/doctor.py
```

## Ollama

Ollama is optional and is not bundled.

```text
ollama serve
ollama pull gemma3:4b
```

Then configure `.env`:

```dotenv
RESUME_AI_PROVIDER=ollama
RESUME_AI_MODEL=gemma3:4b
RESUME_OLLAMA_BASE_URL=http://127.0.0.1:11434
```

No GPU is assumed. CPU inference is supported but may be slower. The deterministic application
path remains available without Ollama.

## Verify Installation

```text
python scripts/doctor.py
python -c "from resume_analyzer import ResumePipeline; from resume_analyzer.web.app import app; print('OK')"
```

