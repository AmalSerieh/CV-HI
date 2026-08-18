# Architecture

## System Boundary

Resume Intelligence Platform is a local Python application with one canonical entry point:
`resume_analyzer.ResumePipeline`. The CLI and FastAPI web layer both call that pipeline and
serialize the same schema-versioned report.

## Main Components

1. **Input and extraction** — validates PDF/DOCX files, enforces size and archive limits,
   extracts document text and layout, and invokes OCR when enabled and needed.
2. **Document understanding** — resolves sections and structured contact, education,
   experience, project, skill, language, and certification entities.
3. **Evidence and quality** — links claims to evidence, reconciles cross-field coherence, and
   reports parsing integrity separately from ATS compatibility.
4. **ATS and target role** — produces bounded compatibility findings, optional job-description
   match data, and evidence-based target-role suggestions.
5. **Recommendations and rewrites** — provides deterministic recommendations by default and
   optional validated local-AI output through Ollama or an explicitly configured local
   Transformers model.
6. **Human review** — `ResumeReviewState` records explicit accepted/rejected decisions while
   pending and rejected proposals continue to resolve to canonical original content.
7. **Delivery interfaces** — the CLI exports JSON; FastAPI supplies local pages, asynchronous
   analysis status, result views, JSON downloads, FinalResume preview, and allowlisted DOCX
   templates.

Compatibility packages at the repository root are intentionally retained as thin import shims.
New integrations should use `resume_analyzer` directly.

## Data Flow

```text
PDF/DOCX
  -> signature and limit validation
  -> text/layout extraction (optional OCR)
  -> structured entities and evidence
  -> parsing integrity and data quality
  -> ATS and optional job match
  -> target-role analysis
  -> deterministic or optional local-AI recommendations/rewrites
  -> schema 2.1.0 JSON
  -> explicit human review decisions
  -> semantic FinalResume
  -> allowlisted docxtpl renderer
  -> DOCX download
```

## Runtime Data

Runtime directories are created from configuration when needed. They are not source assets and
are ignored by Git. Web uploads are temporary, result records have a configurable TTL, and the
delete endpoint removes an analysis and its associated temporary data.

## Security Controls

- Localhost binding by default
- Debug mode off by default
- Upload extension, file signature, size, page, and DOCX expansion limits
- Path traversal and unsafe archive-entry protection
- Bounded extraction, prompt, output, and concurrency limits
- Privacy-safe public diagnostics and report paths
- Local Bootstrap assets, restrictive response headers, and no required CDN
