# File retention scheduled cleanup readonly plan design

## Boundary

The runner is a read-only planning primitive. It is safe to invoke manually or from a future scheduler because it does not mutate system state except for an optional JSON report file.

## Implemented Shape

Module:

- `app/domains/files/scheduled_cleanup.py`

Script:

- `scripts/ops/run_file_retention_cleanup_readonly.py`

The module composes:

- `DocumentFileRetentionPlanner.build_plan()`
- `DocumentFileStorageUsageReporter.build_report()`

It does not call:

- `DocumentFileRetentionPlanner.mark_expired()`
- `FileUploadService.preview_retention_physical_delete()`
- `FileUploadService.execute_retention_physical_delete()`
- storage delete adapters
- job stage dispatchers
- conversion, parsing, translation, or Word rendering services

## Report Contract

Top-level fields:

- `run_id`
- `generated_at`
- `mode=readonly_plan`
- `retention`
- `storage_usage`
- `next_steps`
- `safety`

`retention` includes existing retention plan totals and candidate summaries.

`storage_usage` includes existing storage usage report fields.

`next_steps` should explicitly say:

- review candidates.
- run existing Admin UI/API dry-run before deletion.
- do not treat this runner report as delete authorization.

## CLI Contract

Default behavior:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_file_retention_cleanup_readonly.py
```

Prints JSON to stdout and does not write files.

Optional output:

```bash
/Users/sc/miniconda3/envs/md2word/bin/python scripts/ops/run_file_retention_cleanup_readonly.py --output var/reports/file-retention/latest.json
```

Writes JSON to the requested path. The script must create parent directories but must not delete or overwrite unrelated files except replacing the exact output file.

## Safety

- No metadata mutation.
- No object deletion.
- No broad "delete all".
- No scheduler loop.
- No audit event by default; a later task can add audit recording for run invocations if product requires it.
- Report must not include local absolute paths.
- Candidate summaries intentionally omit `object_key`, `bucket`, and path-like object locators.

## Compatibility

- Works with file/sqlite/mysql metadata backends through existing runtime adapters.
- Full-list scan is acceptable for an operator-invoked readonly runner.
- Can be scheduled by external tooling later without changing semantics.

## Risks

- `build_runtime()` constructs broad services, so the CLI must not create FastAPI app or trigger lifespan replay.
- Metadata-estimated storage usage can differ from actual files.
- A future scheduler must still treat the runner report as advisory only.
