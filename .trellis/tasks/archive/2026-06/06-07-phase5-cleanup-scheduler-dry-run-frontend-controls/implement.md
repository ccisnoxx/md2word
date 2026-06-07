# Phase 5 cleanup scheduler dry-run frontend controls implementation

## Checklist

1. Planning
   - [x] Fill PRD, design, and implementation plan.
   - [x] Validate task.
   - [x] Start task.

2. Frontend
   - [x] Import scheduler dry-run response type.
   - [x] Add reactive form state, loading state, and result state.
   - [x] Add scheduler dry-run runner method.
   - [x] Add result summary and safety helpers.
   - [x] Add compact UI panel on `FileRetentionPage.vue`.
   - [x] Preserve existing destructive controls unchanged.

3. Verification
   - [x] Run frontend build.
   - [x] Run browser smoke if local frontend can be served.
   - [x] Run Trellis validate.
   - [x] Run `git diff --check`.

## Verification Commands

```bash
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-scheduler-dry-run-frontend-controls
git diff --check
```

## Non-execution Reminder

Do not run pdf-mineru parsing, MinerU recovery query/download, real translation providers, Word generation, real alert delivery, real provider cancellation, cleanup scheduler loops, real S3 deletion, physical cleanup execution, or autonomous destructive cleanup.

## Implementation Summary

- Added a `Scheduler Dry Run` panel to `/system-status/file-retention`.
- The panel calls `filesApi.runRetentionCleanupSchedulerDryRun` with optional `owner_id` and configurable `lock_ttl_seconds`.
- The UI displays run ID, action mode, candidate count, estimated reclaim bytes, cleanup lock evidence, and safety flags.
- Successful dry-run refreshes cleanup run history and opens the newly created history detail.
- Existing physical delete and manual cleanup-run execute controls are unchanged.

## Verification Results

```bash
npm --prefix frontend run build
# PASS; existing Rollup pure-comment and chunk-size warnings remain.

Browser smoke:
# PASS: started Vite on 127.0.0.1:3000 and FastAPI on 127.0.0.1:8000 with temporary file backend/test auth.
# PASS: logged in as local test admin and opened /system-status/file-retention.
# PASS: Scheduler Dry Run panel rendered.
# PASS: clicked "运行 scheduler dry-run"; response rendered run=cleanup_8b2414bf23e9, candidates=0, reclaim=0 B, lock released=true.
# PASS: Cleanup Run History showed dry_run / scheduler_dry_run record.
# PASS: browser console errors: [].

python3 ./.trellis/scripts/task.py validate 06-07-phase5-cleanup-scheduler-dry-run-frontend-controls
# PASS

git diff --check
# PASS
```
