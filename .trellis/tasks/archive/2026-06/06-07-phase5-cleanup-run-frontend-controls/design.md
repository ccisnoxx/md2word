# Phase 5 cleanup run frontend controls design

## Boundary

This task is frontend-only. It consumes the existing backend cleanup-run contract and does not alter backend execution semantics.

Excluded work:

- scheduler loop or autonomous executor.
- distributed lock or signed cleanup plan.
- real S3 delete.
- provider cancellation.
- alert delivery.
- pdf-mineru parsing, translation providers, or Word generation.

## Existing Contract

Backend endpoints:

```text
POST /api/v1/files/retention/cleanup-runs/preview
POST /api/v1/files/retention/cleanup-runs/execute
```

Preview request:

```json
{
  "file_ids": ["file_a"],
  "max_files": 50
}
```

Execute request:

```json
{
  "file_ids": ["file_a"],
  "max_files": 50,
  "preview_hash": "sha256:...",
  "reason": "operator reason",
  "confirmation": "EXECUTE AUTOMATED RETENTION CLEANUP"
}
```

The backend owns validation for file ID uniqueness, max limits, reason, confirmation, hash mismatch, storage support, audit writing, and physical-delete outcomes.

## UI Flow

Add a cleanup-run section near the existing physical-delete result area on `frontend/src/pages/FileRetentionPage.vue`.

Flow:

1. Operator selects exact retention candidates from the existing table.
2. Operator clicks `预览 cleanup run`.
3. UI stores `cleanupRunReport` and displays:
   - `action_mode`
   - `run_id`
   - `preview_hash`
   - `max_files`
   - safety flags
   - physical-delete totals and item outcomes
4. Execute is available only when:
   - latest report is `cleanup_preview`.
   - selected file IDs exactly match `requested_file_ids`.
   - at least one item outcome is `deletable`.
5. Dialog asks for reason and confirmation phrase, then calls execute with the preview hash.
6. After execute, UI refreshes the retention plan while preserving the execution report.

## Data Contracts

Add TypeScript types to `frontend/src/api/types.ts`:

- `FileRetentionCleanupRunPreviewRequest`
- `FileRetentionCleanupRunExecuteRequest`
- `FileRetentionCleanupRunSafetyResponse`
- `FileRetentionCleanupRunResponse`

Reuse existing `FileRetentionDeleteResponse` for `physical_delete`.

Add wrappers to `frontend/src/api/files.ts`:

- `previewRetentionCleanupRun(payload)`
- `executeRetentionCleanupRun(payload)`

## Safety Design

- Preview does not mutate and does not write audit by backend contract.
- Execute requires the backend generated `preview_hash`.
- UI never invents a confirmation phrase; it shows and submits the phrase returned by preview.
- Selection changes clear stale cleanup previews.
- The section labels the operation as manual cleanup-run execution, not autonomous scheduling.

## Compatibility

- Additive frontend only.
- Existing direct physical-delete controls remain intact.
- No new dependency.
- No route or navigation change.

## Risk

- The word "cleanup run" can be confused with scheduler automation. The UI must show safety metadata and use manual wording.
- Stale preview hash can reject execution if backend state changes; the UI should surface the backend API error and require re-preview.
