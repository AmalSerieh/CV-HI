# User Guide

## Web Workflow

1. Start the application and open the configured local URL.
2. Upload one PDF or DOCX resume.
3. Optionally paste a job description.
4. Select deterministic analysis or a configured local AI option.
5. Submit the analysis and wait for the status page to complete.
6. Review extraction, ATS compatibility, parsing integrity, target-role evidence,
   recommendations, and optional rewrites.
7. Download the canonical JSON report when needed.

Rejected uploads return a safe error when the file type, signature, archive structure, size, page
count, or extracted content violates configured limits.

## Reading Results

- **ATS compatibility** describes document and content compatibility signals; it does not predict
  employment or candidate suitability.
- **Parsing integrity** identifies extraction and structural issues; it does not score the person.
- **Data quality** highlights malformed, duplicated, truncated, or incoherent extracted fields.
- **Target-role evidence** compares supported resume evidence with role definitions; it is not a
  hiring probability.
- **Recommendations** are evidence-grounded improvement suggestions.
- **Rewrites** are proposals and should be reviewed before use. Unsupported AI claims are rejected
  or downgraded.

## CLI Workflow

Analyze a document:

```text
resume-analyzer resume.pdf --pretty
```

Add a job description and save JSON:

```text
resume-analyzer resume.docx --job-description job.txt --output report.json --pretty
```

Installed entry points:

- `resume-analyzer`
- `resume-analyzer-web`
- `resume-analyzer-doctor`

Repository scripts are preferable for local use because they load `.env` consistently.

## Runtime Retention

Web results are temporary and expire according to `RESUME_RESULT_TTL_MINUTES`. The delete action
removes a result immediately. CLI output persists only when an explicit output path is supplied.
Do not place private reports in source-controlled directories.

