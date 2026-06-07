# Phase 5 cleanup scheduler dry-run frontend controls design

## Current State

- Backend endpoint and TS API wrapper already exist.
- `FileRetentionPage.vue` currently supports:
  - file library search;
  - storage/quota dry-run;
  - retention plan and mark-expired;
  - selected-file physical delete preview/execute;
  - manual cleanup-run preview/execute;
  - cleanup run durable history.
- Cleanup history can now contain `status=dry_run` and `action_mode=scheduler_dry_run`, but there is no UI control to create that record.

## UI Design

Add a compact panel between cleanup run result and cleanup history:

- Header:
  - title: `Scheduler Dry Run`
  - subtitle: readonly manual runner, no scheduler loop, no delete.
  - tags for current run and generated time when a result exists.
- Form:
  - optional `owner_id` input.
  - `lock_ttl_seconds` numeric input, default 60, min 1, max 900.
  - primary button: `运行 scheduler dry-run`.
- Result cards:
  - run ID / action mode.
  - retention candidates count.
  - estimated reclaim size from readonly report if present.
  - lock owner, fencing token, status, released flag.
- Safety flags:
  - map backend safety entries into `el-tag`.
  - true values are generally success except unsafe side-effect flags, which should be danger if true.

## Data Handling

Use `FileRetentionCleanupSchedulerDryRunResponse`.

Because `readonly_report` is typed as `Record<string, unknown>`, add local helpers:

- `schedulerRetentionTotals()`
- `schedulerStorageReclaim()`
- `schedulerRetentionCandidateCount`
- `schedulerEstimatedReclaimBytes`
- `schedulerDryRunSafetyEntries`

These helpers must validate object shapes before reading dynamic values.

## Safety

- The button calls only the dry-run endpoint.
- No confirmation phrase, no execute action, and no file selection dependency.
- Do not render candidate object locators. Show only aggregate counts and the history detail link.
- Keep existing destructive cleanup controls unchanged.

## Verification

- `npm --prefix frontend run build`.
- Browser smoke for protected `/system-status/file-retention` route when feasible.
- Trellis validate and `git diff --check`.
