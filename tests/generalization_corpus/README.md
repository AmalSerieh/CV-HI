# Generalization corpus

This directory defines the local development, holdout, and randomized resume
evaluation matrix. The cases are synthetic and are generated at test time; parser
code must never select behavior by fixture name, candidate value, or expected
output.

- `development`: focused regressions that describe a known document-understanding
  failure.
- `holdout`: broad invariants only (valid schema, coherent evidence, no false
  phone, no path leakage, and no crashes). Expected entity snapshots are not used
  by parser rules.
- `randomized`: seeded values and layout variations generated during the test run.

The binary PDF/DOCX inputs are created in pytest temporary directories and are
discarded after each run. This keeps the repository small while exercising the
same public file pipeline used in production.
