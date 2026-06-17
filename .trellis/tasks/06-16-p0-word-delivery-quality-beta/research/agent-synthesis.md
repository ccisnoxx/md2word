# Agent Synthesis

## Shared Conclusion

The project already has a broad internal portal. The next stage should not add more horizontal workflow or ops features. It should focus on making `direct_pdf_to_word` produce deliverable Word documents for technical datasheet / electronics PDFs.

## Product

- Product positioning: internal high-trust datasheet-to-Word delivery workbench.
- Main gap: generated Word quality, not feature count.
- P0 should focus on direct PDF-to-Word quality and Golden Sample sign-off.
- P1 can introduce `en2zh_pdf_to_word` as beta, but not as a P0 blocker.

## UX

- Main user journey: upload PDF, create job, track status, diagnose, download, optionally admin-delete.
- Task UI should provide a clear next recommended action for failed, running, succeeded, low-quality, and blocked states.
- Dangerous actions should use `Preview -> Reason -> Confirm -> Result`.
- Operator should not see admin-only destructive actions.

## Frontend

- Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router.
- Business state is mostly page-local; auth is in Pinia.
- P0 UI should focus on `/jobs`, `/jobs/new`, and `/jobs/:jobId`.
- Frontend should consume backend `available_actions` and not infer task action availability from status alone.
- Useful P0 components/composables: job filters, action dialogs, quality summary, retryable create flow.

## Backend

- New public workflow is `Files + Document Jobs`; legacy `/api/v1/jobs` is not a supported new integration path.
- Metadata storage supports file/sqlite/mysql; production baseline is now MySQL + Celery + single worker.
- Keep state/action policy centralized and idempotent.
- Avoid adding a parallel task model or broad external-provider features in P0.

## QA / Architecture

- Current 2026-06-03 evidence: 4/4 canonical samples succeeded and DOCX files are openable, but 0/4 met manual P0 quality.
- Main blockers:
  - headings are `Normal`;
  - bullet/list semantics are not Word numbering;
  - double-column and wide-table layout are weak;
  - captions can render below the relevant table;
  - LaTeX residue remains in Word-visible text.
- The original 10-20 sample target is replaced by the current 4-sample canonical suite for this P0.
- Docs must be aligned because older planning docs conflict with current admin-only task delete support.
