# P0 Word Delivery Quality Beta

## Goal

Turn the current internal PDF-to-Word workflow into a P0 beta for technical datasheet / electronics documents. The target outcome is not generic PDF conversion. The target is editable Word output that is close to the source layout while following maintainable Word document structure.

## Current Facts

- The public P0 workflow is `Files + Document Jobs`: upload PDF, create `document_job`, run MinerU/DocumentIR/renderer, then download DOCX.
- Legacy `/api/v1/jobs` is not a supported new integration surface.
- Current runnable Golden Sample PDFs are:
  - `gs-003 / OPA228_P1.pdf`
  - `gs-004 / OPA228_P2.pdf`
  - `gs-006 / OPA228_P6.pdf`
  - `gs-008 / OPA228_P7.pdf`
- These 4 PDFs are the P0 canonical suite. The manifest's pending samples remain backlog and do not block this P0.
- The 2026-06-03 real regression showed 4/4 succeeded and 4/4 DOCX openable, but 0/4 met P0 manual quality.
- Production baseline is MySQL + Celery + single worker for internal company use.
- Full-stack validation runs on hostdzire. The local machine is not the P0 service validation target because MySQL, Redis/Celery, API/Worker, and frontend smoke dependencies are not available there.
- `en2zh_pdf_to_word` is P1 beta work. P0 quality work focuses on `direct_pdf_to_word`.
- Task-level delete remains supported for admin only. Operator UI should hide it, and the backend must keep enforcing permission.
- Golden Sample source ownership, reviewer assignment, and final sign-off are admin responsibilities.
- The manual quality line is not pixel-perfect PDF cloning. It prioritizes Word document formatting standards and maintainable structure while staying close enough to the source datasheet layout.

## Requirements

- Focus product scope on technical datasheet / electronics PDFs, especially the current OPA228 samples.
- Improve Word delivery quality for the canonical suite:
  - Preserve headings as maintainable Word heading structure or an equivalent style contract.
  - Preserve list semantics as Word bullets/numbering where practical, not only plain bullet characters.
  - Preserve caption/table and caption/figure ordering.
  - Keep tables editable and readable.
  - Handle wide tables with a readable Word layout, such as landscape/page-fit/reasonable pagination.
  - Remove raw LaTeX-style residue from final Word-visible text for common datasheet symbols, units, Greek letters, subscripts, superscripts, and square-root expressions.
  - Preserve double-column reading order for the canonical double-column samples.
- Add or expose structured quality evidence so job detail and regression reports can show quality flags and manual quality status.
- Keep `/api/v1/files` + `/api/v1/document-jobs` as the only new P0 integration path.
- Align task actions with backend `available_actions`; frontend must not infer destructive action availability from status alone.
- Make task-level delete admin-only in UX and API behavior.
- Update product/testing/runbook docs so the P0 gate is the canonical 4-sample suite, not a 10-20 sample count.
- Update docs that still present legacy `/api/v1/jobs` as a new workflow path.
- Keep real S3 delete, real provider cancellation, external customer portal, multi-tenant self-service, billing, and online Word editing out of this P0.

## Acceptance Criteria

- Golden Sample canonical suite:
  - [ ] `gs-003`, `gs-004`, `gs-006`, and `gs-008` all complete successfully through `direct_pdf_to_word`.
  - [ ] All 4 generated DOCX files are openable.
  - [ ] All 4 generated DOCX files are editable Word documents, not full-page screenshots.
  - [ ] Admin reviewer records a passing manual quality verdict for all 4 samples.
- Manual quality criteria:
  - [ ] Heading/list/table/caption/symbol/wide-table/double-column issues listed in the 2026-06-03 manual record are resolved or explicitly accepted by admin as non-blocking.
  - [ ] Final DOCX is close to source layout while following Word document formatting standards; where the two conflict, admin evaluates Word-standard structure as the higher priority.
- Frontend / API:
  - [ ] Operator cannot see task delete UI and cannot execute task delete API.
  - [ ] Admin can use guarded task delete with preview, reason, confirmation, result, and audit behavior.
  - [ ] Job detail exposes useful quality/diagnostic information for failed or low-quality output.
- Production readiness:
  - [ ] MySQL + Celery + single-worker deployment path is documented as the production baseline.
  - [ ] `/health/ready` reports no unexplained blocker and `p0_document_jobs_ready=true` before release.
- Documentation:
  - [ ] README, internal portal runbook, Golden Sample reports, and P0 integration docs describe the 4-sample canonical P0 gate.
  - [ ] New integration docs do not direct users to legacy `/api/v1/jobs`.

## Out of Scope

- Generic PDF conversion quality across arbitrary PDF categories.
- Expanding the P0 gate to 10-20 samples.
- Making `en2zh_pdf_to_word` a P0 release blocker.
- Multi-worker production semantics.
- Real S3 deletion, real provider cancellation, automatic cleanup scheduler execution, and real external notification delivery.
- External customer portal, SSO, billing, and multi-tenant self-service.
- Online DOCX editing or heavy PDF/DOCX side-by-side viewer.

## Technical Approach

- Start with current quality evidence in `docs/testing/pdf-to-word-golden-sample-manual-quality-records-20260603.md`.
- Work from the current `document_jobs -> DocumentIR -> app/services/renderer` path, not the removed legacy API path.
- Reuse existing runtime/legacy conversion strategies where they already solve heading, list, formula/symbol, caption, table, or layout behavior.
- Prefer structured tests and quality flags over screenshot-only checks.
- Treat admin manual review as the final product quality sign-off for the canonical suite.

## Implementation Plan

1. Documentation and contract alignment:
   - Update Golden Sample docs and runbooks to define the canonical 4-sample P0 gate.
   - Update task delete documentation to admin-only guarded delete.
   - Remove or demote legacy `/api/v1/jobs` from new workflow docs.
2. Permission and UI alignment:
   - Verify backend admin-only delete enforcement.
   - Ensure frontend hides delete for operator and shows it only when backend `available_actions.delete.enabled` allows it.
3. Quality evidence surface:
   - Add or normalize quality flags for renderer/layout/symbol issues.
   - Surface quality evidence in job detail and Golden Sample reports.
4. Renderer quality pass:
   - Fix headings/lists.
   - Fix symbols and LaTeX residue.
   - Fix caption ordering.
   - Fix double-column reading order where feasible for OPA228 P1/P2.
   - Fix wide table readability/pagination for OPA228 P6/P7.
5. Verification:
   - Run only no-service local checks that are relevant to the change.
   - Upload the local change set to hostdzire and restart Docker Compose when runtime code changes.
   - Run hostdzire runtime release checks, Golden Sample preflight, and Golden Sample regression for the canonical suite.
   - Produce updated manual quality records.

## Decisions

- P0 product category: technical datasheet / electronics documents.
- P0 sample gate: current 4 OPA228 PDFs only.
- P0 quality line: close to original layout, but prioritizing Word document formatting standards and maintainability.
- P1 beta: `en2zh_pdf_to_word` basic framework and future optimization.
- Delete policy: admin-only task delete; operator hidden and denied.
- Production baseline: MySQL + Celery + single worker.
- Golden Sample source owner/reviewer/final sign-off: admin.
