# File retention management implementation record

本任务已完成 metadata-only file retention 管理切片。实现没有运行
pdf-mineru 解析、翻译或 Word 生成主流程，也没有添加真实文件删除能力。

## Classification

- Type: behavior-changing product feature, metadata-only.
- Public contract change: yes, two Admin-only Files API endpoints and one Admin
  frontend route.
- Storage behavior: metadata status update only; no physical deletion.

## Implementation Summary

1. Backend schemas
   - `app/domains/files/schemas.py` defines
     `FileRetentionCandidateResponse` and `FileRetentionPlanResponse`.

2. Backend routes
   - `app/domains/files/router.py` exposes static retention routes before
     `/{file_id}`:
     - `GET /api/v1/files/retention/plan`
     - `POST /api/v1/files/retention/mark-expired`
   - Both endpoints use Admin-only auth.
   - `mark-expired` writes `file.retention_mark_expired` audit events and only
     updates eligible metadata from `uploaded` to `expired`.

3. Retention planner
   - `app/domains/files/retention.py` reuses
     `DocumentFileRetentionPlanner`.
   - The planner builds candidates from `document_files.expires_at` and never
     deletes local files, object-storage objects, job rows, metadata rows, or
     `object_key`.

4. Frontend API and route
   - `frontend/src/api/types.ts` contains retention response types.
   - `frontend/src/api/files.ts` contains `getRetentionPlan()` and
     `markRetentionExpired()`.
   - `frontend/src/router/index.ts` registers Admin route
     `/system-status/file-retention`.

5. Frontend page
   - `frontend/src/pages/FileRetentionPage.vue` displays totals, retention
     policy days, generated time, candidate rows, expiry time, size, status,
     object key, reason, and job link when `job_id` exists.
   - The page contains refresh and metadata-only mark-expired controls.
   - The page contains no download, physical delete, policy-edit, cleanup
     schedule, or file library controls.

6. Documentation
   - `docs/api/files.md` documents both Admin-only retention endpoints,
     response fields, audit behavior, and non-deletion semantics.

## Verification Run

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_artifact_retention`
  - Result: passed, `Ran 2 tests`.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_plan_is_admin_only_and_reports_dry_run_candidates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_mark_expired_updates_metadata_without_removing_object`
  - Result: passed, `Ran 2 tests`.
- `npm --prefix frontend run build`
  - Result: passed.
  - Notes: Vite reported existing Rollup annotation and chunk-size warnings;
    build completed successfully.
- `python3 ./.trellis/scripts/task.py validate 06-04-file-retention-management`
  - Result: passed.

No verification step ran pdf-mineru parsing, translation, Word generation, or
real file cleanup.

## Residual Non-goals

- No physical file deletion.
- No retention policy CRUD.
- No cleanup schedule or background deletion worker.
- No storage quota enforcement.
- No cross-task file search or full file management library.
- No download controls from the retention page.
- No change to document job creation, retry, cancel, archive, or download
  semantics.

## Rollback Points

- If route ordering conflicts with `/files/{file_id}`, remove the retention
  routes and restore `files` router behavior.
- If metadata marking has unexpected side effects on downloads, keep only the
  GET dry-run endpoint and defer POST.
- If frontend build risk grows, ship backend API plus docs first and leave the
  page behind the planning gate.

## Definition of Done

- [x] Planning artifacts approved.
- [x] Task status moved to `in_progress` before code edits.
- [x] Code implements only this metadata-only retention task.
- [x] Minimal tests/build actually run and results reported.
- [x] No pdf-mineru parsing, translation, Word generation, or physical file
  deletion was executed.
