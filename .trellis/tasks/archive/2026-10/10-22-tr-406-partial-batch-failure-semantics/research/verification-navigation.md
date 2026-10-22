# Research: TR-406 验证入口导航

- Query: 把 `implement.md` 第 5 节的历史基线、CON-102 兼容测试、FastAPI 定向选择器、前端 mock smoke、component regression 和 direct phase2-core matrix 具体化为当前 checkout 可执行的命令，并核对环境前提、已有测试与必须新增的测试。
- Scope: mixed（当前源码/测试/归档证据/本地工具版本）
- Date: 2026-10-22

## Findings

### 1. 任务计划与当前状态

- `.trellis/tasks/10-22-tr-406-partial-batch-failure-semantics/implement.md:88-107` 给出的第 5 节是实施阶段计划，不是已经通过的门禁；它要求先固定历史基线，再验证 CON-102 stage/receipt、FastAPI 失败矩阵、前端 unit/build/smoke 和样本 runner。
- `.trellis/tasks/10-22-tr-406-partial-batch-failure-semantics/implementation-authorization.md:1-14` 已记录用户接受 revision 2 并授权先整合 CON-102，再实施和验证；禁止提交、push、生产/VPS、真实 Provider 和线上连接。本调查遵循只读边界。
- 当前 `task.json` 已为 `in_progress` 且 `implementation_authorized=true`，但本文件只提供导航，不改变业务或任务文件。

### 2. 37 项历史基线：选择器已存在，可直接复用

历史 37 项选择器的原始命令和结果保存在 `.trellis/tasks/10-22-tr-406-partial-batch-failure-semantics/research/current-state.md:43-57`；历史结果为 37 tests、1.412s、OK，属于既有证据，不是本轮新结果。精确重跑命令如下：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_translation_integrity_execution \
  tests.test_document_ir_translation \
  tests.test_generated_artifact_identity \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files
```

当前源码计数可静态核对为：`test_translation_integrity_execution.py` 10 个、`test_document_ir_translation.py` 17 个、`test_generated_artifact_identity.py` 7 个，再加上述 FastAPI 3 个，总计 37 个。相关代码模式包括：完整性 Worker/fan-in、代次/attempt 迟到写和实际 artifact 字节由 `tests/test_translation_integrity_execution.py:97-389` 覆盖；正式 OPA228 fixture/fake Provider 由 `tests/test_document_ir_translation.py` 的 `test_opa228_public_fixture_uses_formal_converter_fake_provider_and_validator` 覆盖；file/local-object/fake-S3 生成件物理身份由 `tests/test_generated_artifact_identity.py` 覆盖。

### 3. CON-102 阶段、原子 retry、receipt：归档证据有选择器，当前 checkout 缺模块

- 当前工作区没有 `tests/test_document_job_execution_stages.py`，也没有 `tests/test_translation_batch_failure_semantics.py`；因此 `implement.md:60` 与 `implement.md:93` 中对这两个模块的命令在整合 CON-102 前会触发 unittest loader `ModuleNotFoundError`，不能把它们标为当前已有测试。
- CON-102 归档的 `.trellis/tasks/archive/2026-10/10-15-con-102-document-job-stages/backend-validation.md:1-37` 记录了阶段测试原应存在且有 16 个聚焦用例；其精确历史定向入口包括：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_document_job_execution_stages \
  tests.test_document_job_modes.DocumentJobModesTests.test_direct_without_translation_configuration_executes_one_docx_without_translation_calls \
  tests.test_database_job_repository.PersistenceAdapterTests.test_document_jobs_api_pdf_callback_flow_uses_database_repository \
  tests.test_database_job_repository.PersistenceAdapterTests.test_document_jobs_api_pdf_callback_flow_uses_mysql_repository \
  tests.test_database_job_repository.PersistenceAdapterTests.test_document_jobs_api_retry_flow_uses_database_repository \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_execution_skeleton_is_idempotent_for_duplicate_delivery \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_classifies_timeout_mineru_render_and_oss_failures \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_integrity_gates_fail_before_ir_or_word_publication \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_queue_filters_priority_and_diagnostics \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_worker_saves_mineru_raw_ir_and_image_assets
```

- 归档的同一文件 `backend-validation.md:30-32` 给出了两个最小 stage 交错 selector：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_document_job_execution_stages.DocumentJobExecutionStageTests.test_final_provider_failure_keeps_batch_duration_and_translating_failure_stage \
  tests.test_document_job_execution_stages.DocumentJobExecutionStageTests.test_provider_return_after_cancel_or_generation_change_cannot_finalize \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in
```

- CON-102 receipt/first-valid-result 的归档实现和验证位于 `.trellis/tasks/archive/2026-10/10-15-con-102-document-job-stages/receipt-backend-validation.md:1-110`。其当前可重用的 selector 名称（必须在依赖代码整合后确认方法仍存在）是 `test_completed_batches_resume_from_new_and_legacy_inflight_stages`、`test_quality_replay_and_upload_without_result_rerender_and_recheck`、`test_explicit_result_reuses_old_generation_but_checks_file_identity`、`test_automatic_word_discovery_requires_current_generation_and_final_ir`；归档记录还覆盖 receipt 后取消/超时、双恢复者、file/SQLite 争抢和 pending/物化边界，但没有当前 checkout 的模块文件可直接执行。
- 因此 CON-102 准入顺序应为：先整合真实实现和 `tests/test_document_job_execution_stages.py`/receipt 相关测试，再用上面的归档 selector 做 loader 验证；若整合后的类名或方法名变化，应以实际模块 AST/`unittest` loader 输出更新命令，不要凭归档路径宣称通过。`tests/test_database_job_repository.py` 当前已有 adapter 级 selector（如 `test_document_jobs_api_retry_flow_uses_database_repository`，约 1956 行）但其现有内容不等于 CON-102 receipt 完整覆盖。

### 4. FastAPI 最小失败/split/retry/权限/下载选择器

当前 `tests/test_fastapi_jobs_backend.py` 的 `FastAPIJobsBackendTests` 已有以下可执行选择器：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_translation_failure_records_ai_call_log_without_full_text \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_truncated_batch_is_split_and_fanned_in \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_translation_failure_resumes_after_mineru_and_filters_old_files \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_en2zh_debug_full_text_is_admin_only \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_download_url_returns_temporary_generated_word_link \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_download_url_rejects_unfinished_job \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_files_endpoint_lists_artifacts_and_authorizes_source_download \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_file_download_rejects_mismatched_and_expired_files \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_integrity_gates_fail_before_ir_or_word_publication \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_requeues_failed_job_and_writes_audit \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_retry_rejects_retry_count_limit \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_operator_scope_and_admin_visibility
```

代码锚点：失败断言在 `tests/test_fastapi_jobs_backend.py:10281-10335`（两次 Provider 调用、`translation_failed`、无 debug archive、batch failed/attempt=2）；截断 split/fan-in 在 `:10337-10400`（split 父项、两个 succeeded 子项、3 次调用、`translation_batch_split` 事件）；跨代用户 retry 在 `:10402` 起；debug 全文权限在 `:10130-10160`；下载/文件 allowlist 和过期/错文件分别在 `:10502-10718`；完整性门禁在约 `:10914`；retry 资源/次数在 `:10983-11066`；租户/角色可见性在 `:11119` 起。

TR-406 新增的“终态叶子 + active sibling 立即主任务失败、重复消息零 Provider、AC12 双初始化/部分安装、AC13 terminal CAS 窗口重放”当前没有现存 FastAPI selector；这些应写入计划新增的 `tests/test_translation_batch_failure_semantics.py`，并在此模块被实现后单独执行：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests.test_translation_batch_failure_semantics
```

不要用现有 failure/split 测试冒充 AC1/AC12/AC13：它们证明旧行为的失败记录、截断拆分和 source/old-file 过滤，尚未证明新停止闸门、完整根计划安装或 terminal-window replay。

### 5. blocked / unreviewed / published 边界

- 现有翻译 QA 状态类型只有 `unreviewed | approved | needs_fix | blocked`，见 `app/domains/document_jobs/models.py:41-48` 与 `schemas.py:93-104`；`published` 不是 DocumentJob/translation-QA 状态。
- `test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state`（`tests/test_fastapi_jobs_backend.py:10162`）先断言现有译文为 `unreviewed`，再 PATCH 为 `needs_fix`，验证 QA artifact 读取和脱敏事件。
- `test_document_job_list_supports_workbench_filters_without_running_worker`（`:7683`）构造 `approved`、`needs_fix`、`blocked` 三个 QA 状态，并验证 `approved`、`all`、`unreviewed` 筛选及汇总；它是当前最小 blocked/unreviewed 过滤入口，但没有 published。
- `test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review`（`:10249`）验证 direct 任务 QA 不可用且 PATCH 409；`test_document_job_incident_queue_filters_priority_and_diagnostics`（`:7982`）覆盖 `blocked` 的 artifact_missing incident。
- 当前 `_download_disabled_reason` 只按 deleted/status/result_file_id 决定下载，见 `app/domains/document_jobs/service.py:1920-1927`；没有发布动作/发布状态。若 TR-406 要求“完整 blocked/unreviewed 草稿内部可下载但批准/发布拒绝”，必须在已接受 CON-103/104 的真实 owner/测试整合后新增或复用专门 selector，不能把现有 QA `blocked` 过滤测试说成发布权限证据。
- 当前后端可直接执行的相关命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_reads_existing_artifacts_and_updates_review_state \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_list_supports_workbench_filters_without_running_worker \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_translation_qa_marks_direct_jobs_unavailable_and_rejects_review \
  tests.test_fastapi_jobs_backend.FastAPIJobsBackendTests.test_document_job_incident_queue_filters_priority_and_diagnostics
```

### 6. Frontend unit、mock smoke、本地配置和浏览器

现有前端单测文件均存在：`frontend/src/utils/translationBatches.test.ts`（6 个 `it`，状态/截断/汇总展示）和 `frontend/src/api/documentJobs.test.ts`（1 个 `it`，translation-batches 请求 URL）。精确最小命令：

```bash
npm --prefix frontend run test:unit -- src/utils/translationBatches.test.ts src/api/documentJobs.test.ts
npm --prefix frontend run build
```

`frontend/package.json` 中 `test:unit` 实际是 `vitest run --dir src`，`build` 实际先执行 `vue-tsc --noEmit` 再执行 `vite build`；因此 build 已包含前端类型检查，没有单独的 frontend `lint` 脚本。TR-406 新增 DTO/页面行为后，应在两个现有 unit 文件中增量补断言，而不是以现有 7 个测试覆盖新增终态 UI。

现有 `frontend/tests/smoke/core-flow.spec.ts` 已有 mock API helper 和可复用的 QA 状态 fixture：`translationQaJob.translation_qa_status="unreviewed"`（约 97-110 行）、`translationQaBlockedJob.translation_qa_status="blocked"`（约 112-124 行），blocked response 在约 221-247 行。当前可用的相关 smoke selector：

```bash
npm --prefix frontend run test:smoke -- tests/smoke/core-flow.spec.ts \
  --grep 'translation QA|翻译 QA' --workers=1
```

精确现有测试标题为 `operator can inspect the translation QA queue with backend all-status summary`（`:2486`）、`operator can use the translation QA drawer review flow`（`:2503`）、`operator can use the shared translation QA panel on the detail page`（`:2549`）、`operator sees unavailable translation QA in the queue drawer as readonly`（`:2569`）、`operator sees unavailable translation QA as readonly and cannot submit review`（`:2587`）。当前没有带“翻译批次”字样的 smoke 测试标题，因此计划命令 `--grep '翻译批次'` 在新增测试前会匹配 0 项；实现后应新增带“翻译批次”的明确标题，覆盖自动 retry、终败、split 成功、旧 generation response、operator/admin、viewport 和键盘。

`frontend/playwright.config.ts:1-31` 的本地 smoke 配置是：baseURL `http://127.0.0.1:3010`，`webServer.command="npm run dev:smoke"`，自动启动 Vite 3010，`reuseExistingServer=false`，只用 `chrome` project。当前环境只读探测结果：`frontend/node_modules` 存在，Playwright `1.54.2` 可执行，Node `v24.16.0`、npm `11.13.0`，Chrome `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` 和 Edge 均存在。为避免 Playwright channel 查找差异，实施时可显式使用：

```bash
PW_CHROME_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  npm --prefix frontend run test:smoke -- tests/smoke/core-flow.spec.ts \
  --grep '翻译批次' --workers=1
```

该命令会启动本地 Vite smoke server；本轮调查未启动服务器、未运行 smoke，也未声称浏览器行为已通过。Playwright/Chrome “可用”只表示本地依赖和可执行文件存在。

### 7. component regression 与 direct phase2-core matrix

电子元器件 runner 的实际参数由 `scripts/dev/run_component_pdf_regression.py:39-59,215-235` 定义：`--manifest`、`--output-dir`、可重复 `--sample-id`、`--no-timestamp`、`--json`。当前 manifest `tests/fixtures/component_pdf_samples/manifest.yaml` 只有一个 enabled 且 runnable 的公开最小样本 `ti-opamp-opa228-p1-smoke`，其 `component_content_list_v2.json` 存在。实施时可运行：

```bash
.venv/bin/python scripts/dev/manage_component_pdf_samples.py validate
.venv/bin/python scripts/dev/run_component_pdf_regression.py \
  --sample-id ti-opamp-opa228-p1-smoke --json
```

runner 会走 `scripts.dev.formal_mineru_conversion.run_conversion`，结果写到默认 `tests/tmp/component_pdf_regression/<UTC run id>/`；它属于真实本地 converter/renderer 回归，不调用 Provider。它只覆盖最小 OPA228 page-1，不等价于四页 phase2-core。

phase2 matrix 的 `scripts/dev/run_local_mineru_quality_matrix.py:39-62,198-238` 的 `SAMPLE_SETS` 实际只有 `phase2-core` 和 `ru2zh-acceptance`；`phase2-core` 样本为 `OPA228_P1/P2/P6/P7`（P0）和 `RS2G04`（P1），`ru2zh-acceptance` 为 `RU_DIODE_ANODE_TOP`。`--help` 实测列出 mode `direct|en2zh|ru2zh`、重复 `--sample-id`、`--translation-response-dir`、`--dry-run`、`--allow-blockers` 等参数。当前 `mineru_result/` 下四个 OPA228 package、RS2G04 package、俄文 diode package 都存在；模板、layout YAML、subscript YAML 也存在。因此 direct phase2-core 的精确入口为：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --sample-set phase2-core --mode direct
```

可先以单个 P0 样本缩小范围：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --sample-set phase2-core --sample-id OPA228_P1 --mode direct
```

`--mode en2zh/ru2zh` 没有本地 response 文件且没有 `OPENAI_API_KEY` 时会把条目标为 `blocked/translation_api_key_missing`（源码 `:321-336`），不会静默回退 direct；按本任务边界不提供 key、不调用真实 Provider。离线翻译入口需要预先准备 `<sample_id>.translation-response.json`（也接受 `<sample_id>.response.json` 或 `<sample_id>.json`），例如：

```bash
.venv/bin/python scripts/dev/run_local_mineru_quality_matrix.py \
  --sample-set phase2-core --sample-id OPA228_P1 --mode en2zh \
  --translation-response-dir tests/tmp/local_mineru_debug/en2zh_responses
```

实际输入匹配规则是 `ROOT.glob(sample.input_glob)`，并按 mtime/name 倒序取最新目录，见 `scripts/dev/run_local_mineru_quality_matrix.py:717-719`；因此运行前应检查 `report.json` 的 `input_path/input_matches`，避免同 glob 多目录时误选。runner 自己不执行 LibreOffice，报告中的 `render_command` 由 `:538-560` 生成，人工视觉证据仍是后续门禁。

### 8. backend release、OpenAPI、lint/type-check 与线上门

- 后端没有独立 lint/type-check 配置或命令：`.trellis/spec/backend/directory-structure.md:102` 明确没有 `pyproject.toml`、`pytest.ini`、`setup.cfg`、flake8/ruff/mypy/pyright 等 checked-in 配置；根目录文件探测也只找到 `frontend/tsconfig.json`。不要自行新增或猜测 `ruff`/`mypy`/`pytest` 命令。
- 当前项目正式后端质量入口是 `unittest` 与 release check，见 `.trellis/spec/backend/index.md:58-62` 和 `quality-guidelines.md:46-54`。API/OpenAPI 变更后可执行：

```bash
.venv/bin/python scripts/ops/export_openapi.py
.venv/bin/python scripts/ops/export_openapi.py --check
.venv/bin/python scripts/ops/check_release.py
```

第一条会写 `docs/api/openapi.json`，属于实施变更步骤；`--check` 是只读校验。`check_release.py` 没有运行时 URL 时会执行内置 `DEFAULT_UNITTEST_TARGETS`（源码 `scripts/ops/check_release.py:24-61`）、OpenAPI/frontend contract/mock contract；不要把它与“只跑 TR-406 选择器”混淆。它由 `_build_unittest_environment()` 隔离测试环境，源码 `:555-569` 会清除生产配置影响。
- `check_release.py --runtime-url <url>` 与 `--golden-sample-preflight` 会访问运行中的 API/部署门禁；本任务明确禁止线上/外部连接，实施阶段没有单独授权时必须记录 pending。`README.md:42-45`、`docs/deploy/online-first-validation-workflow.md:293-355` 规定线上 readiness、MySQL、Celery、Golden 证据另走线上优先流程。
- 前端没有单独 lint script；`npm --prefix frontend run build` 中的 `vue-tsc --noEmit` 是现有类型检查入口，`npm run test:unit` 是 Vitest，Playwright smoke 是独立浏览器门禁。

## Related specs

- `.trellis/spec/backend/index.md`：后端测试/发布门禁总入口。
- `.trellis/spec/backend/quality-guidelines.md`：DOCX 结构证据不能只以“文件可打开”代替，缺真客户端/在线门禁要报告替代检查和剩余风险。
- `.trellis/spec/backend/database-guidelines.md`：file/sqlite/MySQL 三 adapter、translation batch CAS 和 artifact 物理身份合同；TR-406 的 AC4/AC11/AC12 需在对应 adapter 测试中落证。
- `.trellis/spec/backend/translation-integrity-validator.md`：Worker/fan-in、evidence、generation/attempt 和失败零 apply 合同；与 37 项历史完整性基线直接相关。
- `.trellis/spec/backend/document-job-mode-contract.md`：direct 零翻译调用、retry/clone、OpenAPI 和 mock UI 合同。
- `.trellis/spec/frontend/index.md` 与 `ui-quality-guidelines.md`：前端 unit/build/smoke、375/768/1024/1440 viewport、键盘可达性。
- `.trellis/tasks/archive/2026-10/10-15-con-102-document-job-stages/backend-validation.md`、`receipt-backend-validation.md`：CON-102 阶段/receipt 的历史选择器和边界，仅作兼容基线证据。

## External references (docs, versions)

- Python runtime used by the project’s `.venv`: FastAPI `0.136.3`（requirements.txt 约束 `>=0.136,<0.137`）、Starlette `1.3.1`、httpx `0.28.1`、Pydantic `2.13.4`、PyMySQL `1.2.0`、PyYAML `6.0.3`。这些版本通过只读 package metadata 探测，未访问外部服务。
- `frontend/package.json` / lockfile：Vue `^3.5.13`、Vite `^6.0.7`、Vitest `^3.2.4`、vue-tsc `^2.2.0`、`@playwright/test ^1.54.2`；实际 installed Playwright 为 `1.54.2`。
- `frontend/playwright.config.ts` 是 smoke 的本地配置真源；`scripts/dev/run_local_mineru_quality_matrix.py` 与 `scripts/dev/run_component_pdf_regression.py` 是样本门禁的 CLI 真源。

## Caveats / Not Found

- 没有运行本调查所列耗时 unittest、component/matrix、frontend unit/build/smoke、OpenAPI export/check 或 release check；没有 Provider、MySQL、S3、VPS、线上 API、LibreOffice/Word 证据。命令和环境前提来自源码、`--help` 和归档记录，不是本轮通过结果。
- `tests/test_document_job_execution_stages.py`、`tests/test_translation_batch_failure_semantics.py` 当前不存在；前者需随 CON-102 兼容实现整合，后者是 TR-406 必须新增的主任务终态/AC12/AC13 矩阵。
- 当前任务计划所称“published”没有对应 DocumentJob/translation-QA 状态或动作；只能复用现有资源发布测试作为 published resource 证据，不能证明 blocked/unreviewed 草稿的批准/发布拒绝。必须由实现阶段确认 CON-103/104 owner 后补专门 selector 或明确范围。
- component fixture manifest 只有一个长期样本，而 phase2-core 输入来自工作区 `mineru_result/`；样本存在不代表人工 DOCX/视觉签字已完成。
- `check_release.py` 是聚合发布门禁，包含内置大选择器集；运行它会比 TR-406 定向测试更广，且仍不会证明真实 MySQL/线上 Provider/Word 人工验收。
