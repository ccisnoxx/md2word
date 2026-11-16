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

`app/main.py` 是运行时装配入口。`build_runtime()` 读取 `Settings`、配置日志、构建持久化适配器，再依次装配平台服务、文档流水线和术语服务，按初始化模式执行 `run_startup_bootstrap`，装配健康检查并构造 `AppRuntime`。持久化工厂保留在 `app.main` 供定向测试替换。各业务 seed 在服务构造完成后统一执行，服务构造须允许尚未登记 seed。现有顺序依据见 [启动顺序调查](../../tasks/archive/2026-11/11-11-sr-3-composition-root/research/bootstrap-order.md)。

Follow this pattern for runtime dependencies:

- Construct shared services in the owning `app/composition/*.py` assembly function; add new bootstrap side effects only to `run_startup_bootstrap`.
- Store shared dependencies on `AppRuntime` in `app/core/runtime.py`.
- Read runtime dependencies in routers through `Depends(get_runtime)` from `app/api/dependencies.py`.
- Avoid constructing repositories, clients, or services directly inside route handlers unless the existing route already owns a narrow local helper.

`create_app()` registers `register_api_error_handlers(app)`, CORS, trace/access logging middleware (`app/api/middleware.py::install_trace_logging_middleware`), 正式 DocumentJob 启动恢复任务, and `api_v1_router`. `app = LazyDefaultApp()` delays reading `.env` and connecting runtime dependencies until the ASGI app is actually called.

### API 与 Worker 的启动初始化合同

1. **适用范围。** 标准单 API 服务的生产、开发 Compose 和手动运行的 Celery Worker。API 负责共享存储的初始化，Worker 负责恢复与队列消费。
2. **内部入口。** `build_runtime(settings=None, *, bootstrap=True)` 默认执行初始化。Worker 的 `worker_ready`、普通任务、翻译批次调用 `build_runtime(bootstrap=False)`。
3. **装配顺序。** API 依次执行 SQL schema 维护、平台构造时的空库账号导入，以及服务装配后的 Acceptance、Translation Term、Term Rule、Translation Profile 和模板 seed。Worker 装配跳过这些步骤，恢复和任务执行仍可按业务合同写入数据。
4. **健康与失败。** 标准 Compose 使用 `api: {condition: service_healthy}`，API 的 `/api/v1/health/live` 成功表明同步初始化已完成。初始化失败时健康探针失败，Compose 挡住 Worker 启动。已经初始化的库允许单独重启 Worker。
5. **启动场景。** 空库由一次标准 Compose `up` 拉起。手动启动先等 API `/api/v1/health/live` 成功，再启动 Worker。使用 `--no-deps` 的编排自行保证这个顺序。
6. **验证。** 定向检查覆盖 Worker 三个入口的 schema、账号与 seed 跳过行为。隔离 Compose 检查空库一次启动和任务完成、API 初始化失败时 Worker 未执行、保留数据并分别重启后的读回与继续消费。
7. **接线示例。** Worker 接线使用 `build_runtime(bootstrap=False)` 和 `service_healthy`。旧接线中的 `bootstrap_templates=False` 只跳过模板初始化，`service_started` 允许 API 完成初始化前启动 Worker。

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

- `app/domains/document_jobs/` has `models.py`, `schemas/`（HTTP 请求模型与仅由路由组装的响应包装，按 `jobs`、`translation`、`incidents`、`quality_review`、`publication` 分子模块）, `views/`（应用层读模型：用例的输出契约，按 `jobs`、`translation`、`config`、`incidents`、`quality_review` 分子模块，HTTP 层直接复用为 `response_model`；依赖方向固定为 `schemas → views`，应用层模块（use_cases、review_content、incidents、config_summary、quality_review_projection 等）不得导入 `schemas`，用例也不得拼接 HTTP 路由地址）, `router.py`（主路由，按拆分前顺序挂载 `downloads_router.py`、`quality_review_router.py`（含新代请求）、`publication_router.py`；`http_responses.py` 负责响应映射与 `actor_from_user`、`externalize_url` 等 HTTP 辅助）, `use_cases/`（应用层用例包，见下）, `repository.py`, `workflow.py`, `execution.py`, `execution_support.py`（执行期状态推进与事件记录的唯一 owner `DocumentJobLifecycle`，以及 `require_uploaded_file`、`document_ir_layout_metadata`；宿主与三个协作者共用）, `translation_execution/`（翻译批次执行协作者包，门面 `TranslationBatchExecution` 由 `execution.py` 持有，内部组件见 [翻译批次生命周期](translation-batch-lifecycle.md)）, `render_execution.py`（Word 渲染执行协作者，由 `execution.py` 持有；只负责渲染编排与页面降级，内部组件 `render_placeholders.py::RenderPlaceholderSource`（表格占位图来源/依赖核验与占位感知 image loader）与 `render_result.py::WordResultFinalizer`（结果身份认证与 receipt 后上传收尾）经 `rendering.placeholders` / `rendering.results` 访问）, `mineru_execution.py`（MinerU 解析与回调执行协作者，由 `execution.py` 持有；宿主调用 `run_parse`、`process_replayable_callback_messages`，默认客户端工厂为 `build_mineru_client`）, `preview.py`（预览执行编排 `DocumentJobPreviewService`）, `preview_evidence.py`（当前预览证据的严格读取唯一 owner：存储异常归一化、Artifact 认证、页级质量/映射解析、`verified_current_preview_files`、`preview_download_ttl`）, `recovery.py`, and incident routers. 三个执行协作者不持有宿主引用：共用依赖（`settings`、`job_repository`、`file_repository`、`file_service` 等）在构造时显式注入，与宿主引用同一对象；构造后替换宿主属性不会传到协作者，测试需要替换时须同时替换实际消费方的属性。翻译协作者的依赖统一由 `translation_batches.deps` 持有，替换时改该对象。宿主只经协作者公开方法调用，不访问其下划线成员。
- `app/domains/document_jobs/use_cases/` 取代原 `service.py`（`DocumentJobService` 已删除）。用例模块 `submission`、`lifecycle_commands`、`publication`、`quality_review`、`table_references`、`translation_qa`、`downloads`、`queries` 各为一个类，构造时只注入自己用到的依赖；它们只依赖共享组件 `events`（事件写入）、`access`（读取授权、有效投影、任务文件归属）、`read_model`（读视图与可用动作/禁用原因的唯一 owner）、`review_writer`（评审提交）、`dispatcher`（Worker 投递与投递失败收口）、`request_snapshot`（请求/资源快照与模式、模板、术语版本解析），用例之间互不依赖（唯一例外：`quality_review` 注入 `queries` 与 `table_references`，供复核内容 reader `review_content.py` 复用翻译批次快照与已认证 IR 的表格参考投影；reader 只经这些对象的公开方法读取）。`build_document_job_use_cases(...)` 按依赖方向装配并返回不可变的 `DocumentJobUseCases`，挂在 `AppRuntime.document_job_use_cases`；router 与 `DocumentJobIncidentService` 直接调用具体组件。router 只依赖 `runtime.document_job_use_cases`、审计与健康检查，不直接访问执行服务、文件服务或存储：翻译批次视图经 `queries.get_translation_batch_view`（执行门面以 `TranslationGenerationSummarizer` 窄协议注入）；任务文件与发布最终件的令牌签发/校验、预签名与预览 TTL 由 `downloads.authorize_download / resolve_token_download` 与 `publication.authorize_publication_download / resolve_publication_download` 完成，令牌编解码在 `use_cases/download_tokens.py`。路由只负责 `url_for` + URL 外部化、用户动作审计与响应映射。模块级共享常量、结果数据类与 `NewGenerationRequestUnavailable` 在 `use_cases/common.py`。测试替换构造后依赖用 `tests/document_job_use_case_support.py::replace_dependency`，冻结用例层时钟用 `patch_use_case_clock`。
- `app/domains/jobs/` 保留正式 DocumentJob 共用的模型、资源快照、路径、事件端口及 MinerU callback router；旧服务、调度、状态机和未挂载路由已删除。
- `app/domains/files/` splits upload service, retention, quota policy, cleanup, validation, repository, schemas, and router.

当前未建立此约定：not every domain has the same file names or all of `model/schema/router/service/repository`. Match the nearest existing domain with the same kind of behavior instead of forcing a uniform template.

## Core, Services, Conversion, And Workers

`app/core/` owns cross-cutting runtime primitives:

- `config.py` defines `Settings` and path derivation.
- `errors.py` defines `ApplicationError` (semantic business errors without HTTP status), `ApiError` (explicit-status subclass reserved for the HTTP layer), stable error codes, and `http_status_for` — the single code→HTTP-status mapping.
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
