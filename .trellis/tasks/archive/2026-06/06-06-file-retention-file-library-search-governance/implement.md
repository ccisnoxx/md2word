# File retention file library search governance implementation

## Checklist

1. Backend search service
   - Add `app/domains/files/library_search.py`.
   - Define query/page dataclasses and safe row projection.
   - Implement exact filters, date filters, free-text search, sorting, and pagination.
   - Status: done.

2. Backend API
   - Add schemas to `app/domains/files/schemas.py`.
   - Add `GET /api/v1/files/library/search` to `app/domains/files/router.py` before `/{file_id}`.
   - Map domain page to API response.
   - Status: done.

3. Frontend
   - Add TypeScript types in `frontend/src/api/types.ts`.
   - Add `filesApi.searchLibrary(...)`.
   - Add read-only "文件库搜索" section to `frontend/src/pages/FileRetentionPage.vue`.
   - Status: done.

4. Tests and docs
   - Add targeted FastAPI tests in `tests/test_fastapi_jobs_backend.py`.
   - Regenerate `docs/api/openapi.json`.
   - Run OpenAPI snapshot tests and frontend build.
   - Status: done.

5. Trellis closeout
   - Update task docs with observed verification.
   - Run `task.py validate`.
   - Run `git diff --check`.
   - Status: done.

## Validation Commands

```bash
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_library_search_is_admin_only_readonly_safe_and_filterable
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py
/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export
npm --prefix frontend run build
python3 ./.trellis/scripts/task.py validate 06-06-file-retention-file-library-search-governance
git diff --check
```

Observed:

- `python3 ./.trellis/scripts/task.py validate 06-06-file-retention-file-library-search-governance` passed before `task.py start`.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_library_search_is_admin_only_readonly_safe_and_filterable` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_library_search_is_admin_only_readonly_safe_and_filterable tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_storage_usage_is_admin_only_readonly_and_reports_reclaim_estimates tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_file_retention_physical_delete_preview_is_admin_only_and_does_not_mutate` passed.
- `/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/export_openapi.py` passed and updated `docs/api/openapi.json` with `path_count=109`, `schema_count=196`.
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export` passed with existing FastAPI status constant deprecation warnings.
- `npm --prefix frontend run build` passed with existing Rollup annotation/chunk warnings.
- `python3 ./.trellis/scripts/task.py validate 06-06-file-retention-file-library-search-governance` passed after implementation.
- `git diff --check` passed.

## Non-Execution Reminder

Do not run pdf-mineru parsing, real translation providers, Word generation, physical deletion, S3 deletion, quota enforcement, or scheduler loops.

## Rollback

- Remove the library search domain module, route, schemas, frontend section, tests, and OpenAPI snapshot changes.
- Existing retention, storage usage, policy, and physical delete endpoints remain unchanged.
