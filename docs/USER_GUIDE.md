# User Guide

## Web Workflow

1. Start the application and open the configured local URL.
2. Upload one PDF or DOCX resume.
3. Optionally paste a job description.
4. Select deterministic analysis or a configured local AI option.
5. Submit the analysis and wait for the status page to complete.
6. Review extraction, ATS compatibility, parsing integrity, target-role evidence, and
   recommendations.
7. Open the **Rewrites** tab and inspect each valid AI-assisted or deterministic proposal.
8. Select **Accept** to use a validated proposal or **Reject** to keep the original content.
   Proposals left **Pending** also keep the original content.
9. Select **Review / Export Resume** and confirm the final semantic resume preview.
10. Select **Download Resume**, choose Template 1 or Template 2, and generate the Word file.

Rejected uploads return a safe error when the file type, signature, archive structure, size, page
count, or extracted content violates configured limits.

## Review and Word Export

Review decisions are saved immediately for the current analysis. Reloading the results page keeps
them until the configured analysis TTL expires. Restarting the application may clear this
in-memory state.

- Accepted proposals appear in the Final Resume.
- Rejected and pending proposals resolve to the original extracted content.
- Items without a valid proposal remain unchanged and are not actionable.
- The Final Resume page uses the same reviewed `FinalResume` data as both DOCX templates.
- Template choice controls Word layout only; it does not rerun analysis or AI.

The supplied templates are primarily LTR designs. Arabic Unicode content is preserved, but the
templates are not native RTL redesigns.

## JSON Download

**Download JSON** on the results page downloads the canonical analysis report. It is separate
from the reviewed Final Resume and from the generated Word document.

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
Review decisions share the same temporary lifetime, and generated downloads are not intended as
permanent server storage. Do not place private reports in source-controlled directories.
