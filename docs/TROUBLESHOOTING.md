# Troubleshooting

## Diagnostics First

Run:

```text
python scripts/doctor.py
```

Configuration errors or missing required Python packages return a nonzero status. OCR and local AI
are optional when deterministic extraction is sufficient.

## Ollama Is Unavailable

- Confirm `RESUME_AI_PROVIDER=ollama` only when AI is desired.
- Confirm the service responds at `RESUME_OLLAMA_BASE_URL`.
- Start it with `ollama serve`.
- If AI is not needed, restore `RESUME_AI_PROVIDER=none`.

## Ollama Model Is Missing

Run:

```text
ollama pull gemma3:4b
ollama list
```

Ensure `RESUME_AI_MODEL` exactly matches the installed model name.

## Ollama Times Out

- CPU-only generation can be slow; close competing workloads.
- Keep the verified context and output limits from `.env.example`.
- Confirm the local model is `gemma3:4b`.
- Leave timeout retries disabled unless there is a measured reason to enable them.
- Deterministic fallback remains available when an optional request fails.

## Tesseract Is Missing

Install the external Tesseract executable. Put it on `PATH` or set `TESSERACT_CMD` to its full
executable path, then rerun diagnostics.

## Arabic OCR Is Unavailable

Install the `ara` trained data alongside `eng`. Set `TESSDATA_PREFIX` only for a nonstandard
language-data directory. Diagnostics verify that Tesseract can initialize each language, not only
that a filename exists.

## Port Already in Use

Stop the existing application with `Ctrl+C`, or choose a free `APP_PORT` in `.env`. The launch
command refuses to hide an already-running local server.

## Upload Is Rejected

- Only PDF and DOCX are supported.
- Renaming another file type does not change its signature.
- Check upload size, page count, and DOCX expanded-size limits.
- Confirm the document is not password-protected, truncated, or corrupt.

## Unsupported or Corrupt Document

Open the source file in a trusted PDF or office application and save a clean copy. For an
image-only PDF, install and configure Tesseract. The application reports extraction warnings
without exposing local paths.

## Application Import Fails

Activate the intended virtual environment, reinstall `requirements.txt`, reinstall the project
with `python -m pip install -e . --no-deps`, and run `python -m pip check`.

