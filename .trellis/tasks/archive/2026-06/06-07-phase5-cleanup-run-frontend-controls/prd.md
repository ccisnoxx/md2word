# Phase 5 cleanup run frontend controls

## Goal

Expose the existing manual file-retention cleanup-run backend contract in the Admin File Retention page so operators can run the safe sequence from the UI: exact file IDs -> cleanup preview -> matching preview hash -> reason and confirmation -> execute.

## Requirements

- Add frontend TypeScript contracts for cleanup-run preview and execute responses under the existing files API surface.
- Add frontend API wrappers for:
  - `POST /api/v1/files/retention/cleanup-runs/preview`
  - `POST /api/v1/files/retention/cleanup-runs/execute`
- Add Admin File Retention page controls that:
  - use exact selected retention candidate `file_ids`.
  - require preview before execute.
  - preserve and display the backend `preview_hash`.
  - execute only against the same file ID list as the latest cleanup preview.
  - require a non-empty reason.
  - require the exact backend confirmation phrase.
  - display cleanup-run safety metadata and per-file physical-delete outcomes.
- Keep the legacy selected-file physical-delete controls available.
- Do not change backend cleanup-run behavior, OpenAPI, persistence, audit schema, scheduler, provider calls, S3 deletion, pdf-mineru parsing, translation, or Word generation.

## Acceptance Criteria

- [ ] `FileRetentionPage.vue` has a manual cleanup-run control flow separate from direct physical-delete controls.
- [ ] The cleanup-run preview button is disabled until at least one candidate is selected.
- [ ] The cleanup-run execute button is disabled until a matching cleanup preview exists and at least one preview item is deletable.
- [ ] The execute dialog submits `file_ids`, `max_files`, `preview_hash`, `reason`, and `confirmation`.
- [ ] The page clearly shows scheduler/provider/S3 safety flags from the backend response.
- [ ] `npm --prefix frontend run build`, Trellis validate, and `git diff --check` pass.
- [ ] Browser smoke confirms the route still renders or reaches the expected authenticated boundary.

## Notes

- Backend contract source: archived task `06-07-file-retention-automated-cleanup-execution-contract`.
- This is intentionally not an autonomous cleanup scheduler.
