# File retention scheduled cleanup readonly plan

## Goal

Implement a read-only retention cleanup runner that can be invoked by operators or a future scheduler to generate a cleanup plan without mutating metadata or deleting objects.

## Requirements

- Provide a runner entrypoint for `document_files` retention cleanup planning.
- Runner must build the existing retention dry-run plan and storage usage summary.
- Runner may persist a JSON report under a controlled reports directory when requested.
- Runner must not call `mark-expired`, `delete-preview`, `delete-expired`, storage delete adapters, pdf-mineru parsing, real translation providers, or Word generation.
- Runner output must include generated time, action mode, retention totals, candidate summary, storage usage totals, and next-step guidance.
- Runner output must avoid local absolute paths, secrets, file bytes, prompts, credentials, and raw large payloads.
- This task may add a CLI script and tests; no background scheduler automation is required.

## Non-goals

- No automatic cleanup execution.
- No metadata mutation.
- No physical deletion.
- No S3 deletion.
- No quota enforcement.
- No cron/daemon scheduler.
- No audit export.
- No file search/library.

## Acceptance Criteria

- [x] Task exists.
- [x] `prd.md`, `design.md`, and `implement.md` define the runner boundary.
- [x] `task.py start` is run after user approval.
- [x] Read-only runner domain/service is implemented.
- [x] CLI runner is implemented.
- [x] Tests prove the runner does not mutate metadata, does not delete objects, and writes report only when requested.
- [x] Targeted verification passes.
- [x] `task.py validate` passes.
- [x] `git diff --check` passes.

## Notes

- User explicitly requested direct runner implementation on 2026-06-06.
- "Scheduled cleanup" in this slice means a schedulable read-only planning runner, not automated cleanup execution.
- Observed targeted verification passed on 2026-06-06.
- `task.py validate` and `git diff --check` passed on 2026-06-06.
