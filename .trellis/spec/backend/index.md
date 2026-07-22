# Backend Development Guidelines

These guidelines describe the current `md2word` backend as it exists now. They are based on the repository's FastAPI code, backend docs, tests, and release scripts, not on a target architecture.

Primary evidence:

- `README.md`
- `docs/dev/backend-local-setup-and-architecture.md`
- `docs/runbooks/backend.md`
- `docs/dev/runtime-observability-and-health.md`
- `app/main.py`
- `app/core/config.py`
- `app/core/runtime.py`
- `app/api/errors.py`
- `app/infrastructure/persistence/factory.py`
- `tests/test_fastapi_jobs_backend.py`
- `scripts/ops/check_release.py`

## Pre-Development Checklist

Before backend changes:

1. Read [Directory Structure](./directory-structure.md) for ownership boundaries and where files belong.
2. Read [Error Handling](./error-handling.md) for API/service exception behavior.
3. Read [Quality Guidelines](./quality-guidelines.md) for tests and release checks.
4. If the change touches metadata, repositories, stage messages, schema bootstrap, or artifact storage, read [Database Guidelines](./database-guidelines.md).
5. If the change emits logs, affects health/metrics, workers, callbacks, or long-running jobs, read [Logging Guidelines](./logging-guidelines.md).
6. 修改 MinerU 账号与密钥、运行时配置文件或环境变量优先级时，阅读 [Runtime Configuration](./runtime-configuration.md)。
7. 修改 Word 模板样式 schema、版本 API、默认指针、draft 验证权限或多文种字体槽位时，阅读 [Word 模板样式配置合同](./template-layout-configuration.md)。

Also read `.trellis/spec/guides/index.md` and the relevant thinking guide when the change crosses API, service, repository, worker, or runtime boundaries.

## Guidelines Index

| Guide | What It Covers | Status |
|---|---|---|
| [Directory Structure](./directory-structure.md) | FastAPI composition root, domain layout, services, conversion, workers, resources, and tests | Current |
| [Database Guidelines](./database-guidelines.md) | file/sqlite/MySQL metadata backends, schema bootstrap, adapter ports, payload storage, migration state | Current |
| [Error Handling](./error-handling.md) | `ApiError`, unified API error responses, workflow errors, validation, trace IDs, bulk failures | Current |
| [Logging Guidelines](./logging-guidelines.md) | `access` / `business` / `system` loggers, text/JSON format, trace/job context, sensitive data boundaries | Current |
| [Runtime Configuration](./runtime-configuration.md) | MinerU 账号与密钥绑定、环境变量优先级、安全 API、审计和 Worker 即时生效合同 | Current |
| [Word 模板样式配置合同](./template-layout-configuration.md) | Admin schema、版本治理、旧配置兼容和多文种 OOXML 字体槽位 | Current |
| [Quality Guidelines](./quality-guidelines.md) | `unittest` style, targeted checks, release gate, OpenAPI contract checks, local vs online validation | Current |

## Quality Check

Use the smallest check that covers the touched behavior first. Current project-level evidence points to these commands:

```bash
.venv/bin/python -m unittest <specific-test-targets>
.venv/bin/python scripts/ops/check_release.py
```

`README.md` and `docs/runbooks/backend.md` state that local changes should not start frontend, backend, MySQL, Redis/Celery, workers, or Playwright smoke for P0 release evidence. Full API, worker, database, MinerU, and Golden Sample evidence is collected on hostdzire through the online-first workflow.
