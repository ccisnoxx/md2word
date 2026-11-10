# Directory Structure

The backend is a single FastAPI application rooted at `app/`. There is no `src/` package wrapper.

Evidence:

- `docs/dev/backend-local-setup-and-architecture.md`
- `app/main.py`
- `app/api/v1/router.py`
- `app/core/runtime.py`
- `app/domains/document_jobs/router.py`
- `app/domains/files/service.py`
- `scripts/dev/run_api.py`

## Runtime Composition

`app/main.py` is the composition root. It builds `Settings`, configures logging, builds persistence adapters, wires services, creates `AppRuntime`, registers error handlers, installs middleware, and includes the v1 API router.

Follow this pattern for runtime dependencies:

- Construct shared services and adapters in `build_runtime()`.
- Store shared dependencies on `AppRuntime` in `app/core/runtime.py`.
- Read runtime dependencies in routers through `Depends(get_runtime)` from `app/api/dependencies.py`.
- Avoid constructing repositories, clients, or services directly inside route handlers unless the existing route already owns a narrow local helper.

`create_app()` registers `register_api_error_handlers(app)`, CORS, trace/access logging middleware, 正式 DocumentJob 启动恢复任务, and `api_v1_router`. `app = LazyDefaultApp()` delays reading `.env` and connecting runtime dependencies until the ASGI app is actually called.

## API Layout

`app/api/v1/router.py` owns the `/api/v1` prefix and aggregates business routers from `app/domains/**/router.py`.

截至 2026-11-06（基线 `79f20cef`），[v1 router](../../../app/api/v1/router.py) 已不挂载旧 `/api/v1/jobs` HTTP 入口；公开文档任务入口为 Files + Document Jobs。仍挂载的 MinerU callback router 不表示旧 `/jobs` 入口恢复。

Current pattern:

- API-owned auth/health routers live under `app/api/v1/routers/`.
- Business routers live with their domain, for example `app/domains/document_jobs/router.py`, `app/domains/files/router.py`, `app/domains/saved_views/router.py`, and `app/domains/term_rules/sets_router.py`.
- Router modules convert HTTP inputs to service calls, call FastAPI dependencies, map service results to response schemas, and write audit records for user actions.
- Business request/response schemas usually live in the same domain's `schemas.py`.

When adding a public v1 backend endpoint, add the router in the owning domain and include it from `app/api/v1/router.py`. Do not put new business endpoints under `app/api/v1/routers/` unless they are API shell concerns like current auth/health.

## Domain Layout

Business domains live under `app/domains/<domain>/`. The exact file set varies by domain, but the common local pattern is:

- `models.py` for Pydantic records and state literals.
- `schemas.py` for API request/response models.
- `router.py` or specialized routers such as `sets_router.py`, `review_router.py`, `ops_router.py`.
- `service.py` for application behavior and business validation.
- `repository.py` for `Protocol` ports used by services.
- Focused helpers for workflow, execution, recovery, presenters, validation, or config summaries when a domain has real complexity.

Examples:

- `app/domains/document_jobs/` has `models.py`, `schemas.py`, `router.py`, `service.py`, `repository.py`, `workflow.py`, `execution.py`, `translation_execution.py`（翻译批次执行协作者，由 `execution.py` 持有）, `recovery.py`, and incident routers.
- `app/domains/jobs/` 保留正式 DocumentJob 共用的模型、资源快照、路径、事件端口及 MinerU callback router；旧服务、调度、状态机和未挂载路由已删除。
- `app/domains/files/` splits upload service, retention, quota policy, cleanup, validation, repository, schemas, and router.

当前未建立此约定：not every domain has the same file names or all of `model/schema/router/service/repository`. Match the nearest existing domain with the same kind of behavior instead of forcing a uniform template.

## Core, Services, Conversion, And Workers

`app/core/` owns cross-cutting runtime primitives:

- `config.py` defines `Settings` and path derivation.
- `errors.py` defines `ApiError` and stable API error codes.
- `logging.py` configures runtime logging.
- `runtime.py` stores the process-wide `AppRuntime`.

`app/services/` holds shared services that are not cleanly owned by one business domain, such as auth, health, Document IR conversion, and rendering.

`app/conversion/` 仅保留正式链路使用的共享规则闭包，包括 `docx_rules` 与 `table_html_parser`。B05 第 3、4 步已删除旧转换运行时和 StageWorker；`build_runtime()` 只装配正式 Document Jobs + DocumentIR + Renderer，启动时只运行正式恢复服务。本地调试入口见下文。

`app/workers/` owns worker implementations. Script entrypoints under `scripts/dev/` adapt them for local/PyCharm use:

- `scripts/dev/run_api.py` runs `uvicorn` against `app.main:app`.
- `scripts/dev/run_document_worker.py` is the Document Jobs worker entrypoint.

## Infrastructure And Runtime Data

`app/infrastructure/persistence/` owns metadata adapters:

- `file/`
- `sqlite/`
- `mysql/`
- `factory.py`

`resources/` contains versioned seed/config assets such as templates, template configs, prompts, and term rules. `var/` and `data/` are runtime data directories and are not the versioned source of truth.

`docs/dev/backend-local-setup-and-architecture.md` 说明正式 `document_jobs/`、`document_files/`、callback/batch、共享 `jobs/<id>/resources/`、`tmp/` 和配置目录。旧 stage spool 不再创建或消费。

## Tests And Scripts

Backend tests live under `tests/` as `unittest` test modules. Large contract coverage currently sits in `tests/test_fastapi_jobs_backend.py`, with focused tests such as `tests/test_database_job_repository.py`, `tests/test_backend_logging.py`, `tests/test_openapi_export.py`, and domain-specific tests.

Operational and release scripts live under:

- `scripts/dev/` for local development/debug entrypoints.
- `scripts/ops/` for release, migration/shadow copy, Golden Sample, P1, and P2 checks.

当前未建立此约定：there is no `pyproject.toml`, `pytest.ini`, checked-in lint config, or backend package manager metadata beyond `requirements.txt`.

## Scenario: Local MinerU Debug Uses Formal Renderer Core

### 1. Scope / Trigger

- Trigger: changing local MinerU-to-DOCX scripts, PyCharm run configs, local quality matrix, or component PDF regression runner.
- Purpose: local debugging must reproduce the formal Document Jobs renderer path so layout fixes do not drift between local tools and production conversion.

### 2. Signatures

- CLI: `.venv/bin/python scripts/dev/run_local_mineru_conversion.py <input_path> [--output <docx>] [--template <docx>] [--layout-config <yaml>] [--subscript-config <yaml>] [--translation-mode direct|en2zh|ru2zh|...]`
- JSON/PyCharm: `.venv/bin/python scripts/dev/run_local_mineru_debug_config.py --config scripts/dev/local_mineru_debug_<mode>_config.json`
- Matrix: `.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py --mode <direct|en2zh|ru2zh>`
- Shared local adapter: `scripts.dev.formal_mineru_conversion.run_conversion(...)`

### 3. Contracts

- Local scripts pass MinerU zip/directory inputs to `formal_mineru_conversion`, not to `app.conversion.runtime_runner`.
- The adapter must call `MinerUToDocumentIRService.convert_zip()` and `DocumentIRWordRenderer.render_to_bytes()`.
- Layout fixes belong in `app/services/document_ir/*`, `app/services/renderer/*`, or shared DOCX rules under `app/conversion/docx_rules/*`.
- 旧转换运行时已删除；禁止重新接回旧 `/api/v1/jobs` 或 stage 转换路径。
- Translation modes must not silently fall back to direct. Missing key/response should fail or be reported as blocked after writing any requested local translation request evidence.

### 4. Validation & Error Matrix

- Missing MinerU input -> explicit `FileNotFoundError`.
- Missing explicit template/layout/translation response path -> explicit file-not-found error before rendering.
- Translation mode with neither local response nor available API key -> explicit `OPENAI_API_KEY` provider error or matrix `translation_api_key_missing`.
- Local response item ids do not match formal DocumentIR translation item ids -> explicit provider validation error.

### 5. Good/Base/Bad Cases

- Good: local CLI/config, quality matrix, and component PDF regression all use the shared formal adapter and write DOCX plus DocumentIR/quality evidence.
- Base: a one-off debug script imports `formal_mineru_conversion.run_conversion()` and does no local OOXML/layout post-processing.
- Bad: a script imports `runtime_runner`, applies a DOCX post-processing patch, or treats a legacy local output as proof that formal `document_jobs` output is fixed.

### 6. Tests Required

- `tests.test_conversion_sandbox_dev_tools`: CLI/config call the formal adapter; minimal MinerU package produces an openable DOCX; translation request is written before missing-key failure.
- `tests.test_local_mineru_quality_matrix`: blocked translation entries do not call the adapter and still report `translation_api_key_missing`.
- `tests.test_component_pdf_sample_governance`: committed component sample regression produces an openable DOCX through the formal adapter.
- Renderer behavior changes still require `tests.test_document_ir_mineru_converter_layout` and `tests.test_document_ir_word_renderer_layout`.

### 7. Wrong vs Correct

#### Wrong

```python
from app.conversion import runtime_runner

runtime_runner.run_conversion(...)
```

#### Correct

```python
from scripts.dev import formal_mineru_conversion

formal_mineru_conversion.run_conversion(...)
```
