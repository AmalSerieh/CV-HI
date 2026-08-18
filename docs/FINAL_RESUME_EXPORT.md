# Final Resume Review and DOCX Export

## Data flow

The canonical `PipelineReport` remains the immutable analysis result. `FinalResumeBuilder` is the
single authority that combines that report with a per-analysis `ResumeReviewState`:

1. valid rewrite proposals begin as `pending`;
2. `pending` and `rejected` resolve to original canonical content;
3. only an explicit `accepted` decision resolves to the validated proposal;
4. fields without supported proposals are copied from the canonical report unchanged;
5. DOCX rendering consumes only the resulting `FinalResume` and never invokes AI.

Review state is held in the thread-safe job store, isolated by analysis UUID, and expires with the
analysis TTL. An expired or unknown analysis returns `404`; an unfinished analysis returns `409`.
Updates are transactional, so an invalid item identifier commits no decisions.

## Template contract

`TemplateRegistry` is the server-side allowlist. Public template metadata exposes only an ID,
display name, description, and preview URL. The DOCX renderer resolves paths from the registry;
client-provided paths are never accepted.

The supplied source files under `Template/` are retained unchanged. Flow-safe runtime copies are
prepared by `scripts/prepare_resume_templates.py` and packaged under
`resume_analyzer/export/templates/`. Each render opens a fresh `DocxTemplate`, builds a normalized
context from `FinalResume`, renders to memory, and validates the resulting OOXML package before it
is returned.

## Add Template 3

1. Add the retained source design and its JPG preview under `Template/`.
2. Extend `scripts/prepare_resume_templates.py` to create a flow-safe docxtpl copy. Use normal Word
   paragraphs, lists, and table rows for repeated content; do not place variable-length sections
   in fixed-size text boxes.
3. Write the prepared DOCX and preview to `resume_analyzer/export/templates/`.
4. Add one `TemplateDefinition` to `DEFAULT_TEMPLATE_REGISTRY` in
   `resume_analyzer/export/template_registry.py`.
5. Add renderer tests for complete, short, long, and multilingual resumes and API tests for the new
   allowlisted ID.
6. Render representative outputs through Word or LibreOffice and inspect every page for clipping,
   overlaps, broken bullets, unintended blank pages, and excessive gaps before release.

No endpoint, modal, or renderer branch should need template-specific path logic beyond the registry
entry and the template's context placeholders.
