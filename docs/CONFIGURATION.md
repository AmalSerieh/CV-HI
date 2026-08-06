# Configuration

Copy `.env.example` to `.env` and edit the copy. No setting contains a required secret.
Empty optional values are intentional.

## Web Application

| Variable | Default | Purpose |
|---|---:|---|
| `APP_ENV` | `development` | Environment label used in diagnostics. |
| `APP_HOST` | `127.0.0.1` | Bind address; loopback is the safe default. |
| `APP_PORT` | `8000` | TCP port. |
| `APP_DEBUG` | `false` | FastAPI debug responses; keep false outside controlled development. |
| `APP_RELOAD` | `true` | Source reload for local development. |
| `RESUME_PUBLIC_ABSOLUTE_PATHS` | `false` | Must remain false for the web application. |
| `RESUME_TEMP_DIR` | `runtime/temp` | Private temporary-upload directory. |
| `RESUME_OUTPUT_DIR` | `runtime/outputs` | Temporary result directory. |
| `RESUME_RESULT_TTL_MINUTES` | `60` | In-memory result lifetime. |
| `RESUME_MAX_UPLOAD_MB` | `10` | Per-upload limit. |
| `RESUME_MAX_PAGES` | `20` | Maximum analyzed pages. |
| `RESUME_MAX_EXTRACTED_CHARS` | `200000` | Extracted-text bound. |
| `RESUME_MAX_JOB_DESCRIPTION_CHARS` | `30000` | Job-description bound. |
| `RESUME_MAX_CONCURRENT_ANALYSES` | `1` | Local concurrency bound. |
| `RESUME_MAX_DOCX_UNCOMPRESSED_MB` | `100` | DOCX expanded-size limit. |
| `RESUME_MAX_DOCX_FILES` | `2048` | DOCX archive-entry limit. |

## Analysis Modules

| Variable | Default | Purpose |
|---|---:|---|
| `RESUME_ENABLE_TARGET_ROLE` | `true` | Evidence-based target-role suggestions. |
| `RESUME_ENABLE_RECOMMENDATIONS` | `true` | Recommendations module. |
| `RESUME_ENABLE_ATS` | `true` | ATS compatibility module. |
| `RESUME_ENABLE_JOB_MATCH` | `true` | Job match when a job description is supplied. |
| `RESUME_ENABLE_REWRITES` | `false` | Optional rewrite proposals. |
| `RESUME_ENABLE_OCR` | `true` | OCR attempt when extraction needs it. |
| `RESUME_USE_SPACY` | `false` | Optional local spaCy support. |
| `RESUME_USE_SBERT` | `false` | Optional local sentence-transformer support. |
| `RESUME_ALLOW_MODEL_DOWNLOAD` | `false` | Must be explicitly enabled before model download. |

Rewrite scope and limits are documented directly in `.env.example`. Defaults protect evidence
grounding, input size, output size, and processing time.

## AI

| Variable | Default | Purpose |
|---|---:|---|
| `RESUME_AI_PROVIDER` | `none` | `none`, `ollama`, or explicitly installed `transformers`. |
| `RESUME_AI_MODEL` | empty | Required only when an AI provider is selected. |
| `RESUME_OLLAMA_BASE_URL` | loopback URL | Ollama API location. |
| `RESUME_AI_TIMEOUT_SECONDS` | `60` | Legacy/common timeout fallback. |
| `RESUME_AI_CONNECT_TIMEOUT_SECONDS` | `5` | Connection timeout. |
| `RESUME_AI_RECOMMENDATION_TIMEOUT_SECONDS` | `120` | Recommendation timeout. |
| `RESUME_AI_REWRITE_TIMEOUT_SECONDS` | `90` | Rewrite timeout. |
| `RESUME_AI_MAX_RETRIES` | `1` | Retry count for eligible failures. |
| `RESUME_AI_RETRY_TIMEOUTS` | `false` | Avoids repeating expensive timeouts. |
| `RESUME_AI_TEMPERATURE` | `0` | Deterministic generation preference. |
| `RESUME_AI_SEED` | `42` | Reproducibility hint where supported. |
| `RESUME_OLLAMA_NUM_CTX` | `4096` | Ollama context window request. |
| `RESUME_OLLAMA_KEEP_ALIVE` | `10m` | Ollama model residency request. |

The remaining `RESUME_RECOMMENDATION_*`, `RESUME_REWRITE_*`, and operation-specific token
variables in `.env.example` are bounded tuning controls used by the application. Keep defaults
unless validation supports a change.

## OCR

| Variable | Default | Purpose |
|---|---:|---|
| `TESSERACT_CMD` | empty | Explicit Tesseract executable when not on `PATH`. |
| `TESSERACT_LANGUAGES` | `eng+ara` | Requested OCR languages. |
| `TESSDATA_PREFIX` | empty | Optional custom trained-data directory. |

## Production-Like Local Use

Use:

```dotenv
APP_ENV=production
APP_DEBUG=false
APP_RELOAD=false
```

Keep `APP_HOST=127.0.0.1` unless a reverse proxy, authentication boundary, TLS, access control,
and retention policy have been designed for the deployment.

