# Translation provider batching and recovery Phase 2 diagnostics UI

## Goal

让运营/排障人员能在单个 document job 维度查看 Phase 1 已持久化的 translation provider batch 诊断摘要，快速判断任务是否卡在排队、运行、截断拆分、失败重试或 fan-in 前后。

用户价值：当英译中/俄译中 PDF 翻译出现 provider 截断、非法 JSON、单批失败或重试时，操作员不需要读数据库、事件原文或完整 AI 内容，就能从任务详情定位批次状态、页范围、item 数、attempt、finish_reason、错误摘要和 AI call log 关联。

## Background

- Phase 1 后端任务已归档在 `.trellis/tasks/archive/2026-06/06-26-translation-provider-batching-recovery/`，本任务是新的 Phase 2 planning task，不继续归档任务。
- Phase 1 明确把前端批次可视化和运维控制台增强后置，并已完成批次表、异步 provider batch task、并发控制、失败批次重试、fan-in 合并、审计/事件和最小只读 batch diagnostics JSON API。
- Phase 2 应优先消费现有只读 API，不重做后端 provider batch 执行核心，不改 provider 协议，不引入新的任务级分批策略。

## Confirmed Facts

- 后端已有只读接口 `GET /api/v1/document-jobs/{job_id}/translation-batches`，由 `DocumentJobService.list_translation_batches` 返回 job-scoped provider batch 摘要（`app/domains/document_jobs/router.py:342`）。
- 后端响应 schema 已声明 `DocumentJobTranslationBatchSummaryResponse` / `DocumentJobTranslationBatchListResponse`，包含 `status`、`page_start`、`page_end`、`item_count`、`char_count`、`attempt_count`、`max_attempts`、`split_level`、`parent_batch_id`、`finish_reason`、`error_code`、`error_message`、`ai_call_log_file_ids` 等字段，并在 docstring 中声明不包含原文或译文内容（`app/domains/document_jobs/schemas.py:209`）。
- OpenAPI 已包含该 endpoint 和 schema（`docs/api/openapi.json:4080`、`docs/api/openapi.json:20573`）。
- Phase 1 FastAPI 测试已覆盖成功和 split 场景的 `translation-batches` API 返回（`tests/test_fastapi_jobs_backend.py:9442`、`tests/test_fastapi_jobs_backend.py:9763`）。
- `frontend/src/api/documentJobs.ts` 当前有 `get`、`listEvents`、`listFiles`、`getCallbackMessageSummary`、`getTranslationQa` 等 wrapper，但没有 `listTranslationBatches`。
- `frontend/src/api/types.ts` 当前有翻译 QA 类型，但没有 `DocumentJobTranslationBatchSummaryResponse` / `DocumentJobTranslationBatchListResponse` 前端类型；这与 OpenAPI 当前合约不一致。
- `frontend/src/pages/JobDetailPage.vue` 已有“诊断” tab、诊断刷新按钮、事件预览、Word 质量证据、回调消息和失败信息区域，当前 `loadAll` 只刷新 job/events/files/callback summary，没有读取 translation batch diagnostics（`frontend/src/pages/JobDetailPage.vue:158`、`frontend/src/pages/JobDetailPage.vue:1255`）。
- 任务详情路由要求 `document_jobs:read` 权限（`frontend/src/router/index.ts:59`），后端接口也通过当前用户依赖读取 job-scoped 数据。
- `docs/api/document-jobs.md` 当前记录 job detail、events、files、translation-qa 等接口，但没有记录 `translation-batches` read API（`docs/api/document-jobs.md:168`）。

## Requirements

- R1. 前端必须新增 typed contract：在 `frontend/src/api/types.ts` 定义 `DocumentJobTranslationBatchSummaryResponse` 和 `DocumentJobTranslationBatchListResponse`，字段名和可空性以当前 OpenAPI/backend schema 为准。
- R2. `frontend/src/api/documentJobs.ts` 必须新增只读 wrapper `listTranslationBatches(jobId)`，请求 `GET /api/v1/document-jobs/{job_id}/translation-batches`，不新增写操作。
- R3. Job Detail 的“诊断” tab 必须展示 translation provider batches；MVP 默认承载在现有任务详情页，不新建独立运维页面。
- R4. 每个 batch 行必须展示：状态、页范围、item 数、attempt 次数、finish_reason、错误摘要、AI call log file id 关联；可补充展示 char_count、split_level、parent/root batch、result file id、updated_at，以帮助排障。
- R5. UI 必须清晰区分失败、截断/拆分、重试中/运行中、成功等状态；`failed`、`split`、`truncation_retry`、`retryable`、`finish_reason=length` 应有可扫描的视觉提示。
- R6. 页面必须提供 batch 汇总：总 batch 数、成功/运行/失败/拆分数量、当前 generation、provider call budget 或 deterministic batch count（若接口返回）。
- R7. 对没有 translation batches 的任务，UI 应展示低噪声空状态，不把 direct PDF 转 Word 或尚未进入翻译批次的任务误报为异常。
- R8. Batch diagnostics 加载失败时，只显示该区域的 `ApiErrorAlert` 和单独刷新入口，不阻断任务详情、事件、文件、回调等其他诊断信息。
- R9. 活跃翻译任务轮询时可以刷新 batch diagnostics，但必须复用现有 bounded polling 节奏，避免每 4 秒无条件额外打接口造成诊断 API 压力。
- R10. 不展示完整 prompt、response、source text 或 translated text；只展示后端已返回的摘要字段、错误码/错误信息和文件 ID。不得在 Phase 2 UI 中读取或渲染 AI call log/debug archive 文件内容。
- R11. 不新增批次级重试、取消、强制 fan-in 等运维动作。若后续要做写操作，必须另起设计，先定义权限、接口边界、审计和幂等语义。
- R12. 更新 `docs/api/document-jobs.md`，补充 `translation-batches` endpoint 的用途、字段摘要、只读属性和 redaction 边界。

## Acceptance Criteria

- [ ] 打开英译中/俄译中 document job 详情页时，“诊断” tab 能读取并展示 `GET /api/v1/document-jobs/{job_id}/translation-batches` 返回的 batch 列表。
- [ ] Batch 列表至少展示 status、page range、item_count、attempt_count/max_attempts、finish_reason、error_code/error_message 摘要、ai_call_log_file_ids 和 updated_at。
- [ ] 失败 batch 使用 error/danger 视觉样式；split、truncation_retry 或 `finish_reason=length` 使用 warning 视觉样式；running/queued/pending 与 succeeded 能快速区分。
- [ ] 任务没有 batch 数据时显示空状态，不显示错误提示。
- [ ] Batch API 失败时只影响 translation batch 区域，任务详情其他诊断区域仍可用，并能单独刷新 batch diagnostics。
- [ ] 页面源码和测试不渲染完整 prompt、response、source text 或 translated text 字段；AI call log 只展示文件 ID/数量关系。
- [ ] 前端 API wrapper 有单元测试证明请求路径和 method 正确。
- [ ] Batch display helper 有单元测试覆盖状态文案、tag 类型、页范围、AI log 摘要和错误摘要。
- [ ] `docs/api/document-jobs.md` 记录 `translation-batches` read API 及敏感内容边界。
- [ ] 验证通过：目标前端 unit tests、`npm run build` 或等价 typecheck/build、`git diff --check`。

## Out Of Scope

- 不重做 Phase 1 后端 batch 执行核心、持久化、并发、重试、fan-in 或 provider adapter。
- 不改 provider 协议，不引入新的 batch planner，不改变后端 retry/cancel 权限模型。
- 不在 Phase 2 MVP 中新增批次级重试、取消、重新入队、人工合并等写操作。
- 不在 Job Detail 中展示完整 AI prompt/response、源文本、译文或 debug archive 内容。
- 不处理无关 `.agents`、`.codex`、`.trellis` churn。

## Resolved Decisions

- 2026-06-26 用户确认 Phase 2 MVP scope：只落在 Job Detail 的“诊断” tab，包含只读 batch summary/table、前端 typed API、文档和测试。
- Incident Triage / Operations Cockpit 聚合入口不进 MVP；后续若需要，只做指向 Job Detail batch diagnostics 的聚合或深链设计。
- 批次级 retry/cancel/requeue/fan-in 等写操作不进 MVP；后续若需要，必须另起设计并先定义权限、接口边界、审计和幂等语义。
