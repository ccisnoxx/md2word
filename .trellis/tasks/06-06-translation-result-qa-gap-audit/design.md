# Phase 3 Translation Result QA Gap Audit Design

## Audit Verdict

归档任务 `06-04-translation-result-qa` 描述的第一版 Translation Result QA 能力已经基本实现。当前 Phase 3 不应重复实现基础 QA 页面和 `GET/PATCH /document-jobs/{job_id}/translation-qa`，下一步应补齐可见性、文档一致性、段落级证据深度和回接列表筛选。

## Evidence Read

- Phase 2 收口：`.trellis/tasks/archive/2026-06/06-03-product-roadmap/acceptance.md`
- Phase 3 路线图：`.trellis/tasks/archive/2026-06/06-03-product-roadmap/design.md`
- 已归档任务：`.trellis/tasks/archive/2026-06/06-04-translation-result-qa/{prd.md,design.md,implement.md}`
- 后端：`app/domains/document_jobs/{models.py,schemas.py,router.py,service.py}`
- 前端：`frontend/src/pages/{TranslationResultQaPage.vue,JobDetailPage.vue,JobsPage.vue}`、`frontend/src/components/JobTable.vue`、`frontend/src/api/{documentJobs.ts,types.ts}`、`frontend/src/router/index.ts`
- 测试和文档：`tests/test_fastapi_jobs_backend.py`、`tests/test_openapi_export.py`、`docs/api/openapi.json`、`docs/api/document-jobs.md`

## Completed Capabilities

- 后端任务模型已包含 `translation_qa_status`、`translation_qa_issue_type`、`translation_qa_note`、`translation_qa_reviewed_by`、`translation_qa_reviewed_at`。
- 后端已提供 `GET /api/v1/document-jobs/{job_id}/translation-qa` 和 `PATCH /api/v1/document-jobs/{job_id}/translation-qa`。
- QA 响应已汇总任务状态、资源文件、AI call summary、术语 trace、段落 evidence 和可选 debug archive。
- direct job 被正确挡在 QA API 外，避免误用 PDF 翻译专用能力。
- PATCH 会写入 QA 状态并记录非敏感事件。
- 前端已有 `TranslationResultQaPage.vue`，展示任务摘要、QA 状态表单、证据文件、段落、术语命中、AI call 和 debug 提示。
- `JobDetailPage.vue` 已为 `en2zh_pdf_to_word` job 提供 `翻译 QA` 入口。
- OpenAPI JSON 已包含 Translation QA schema 和 endpoints。
- 已有后端测试覆盖 QA artifact 聚合、状态更新、direct job 不可用。

## Verified Checks

- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_fastapi_jobs_backend -k translation_qa`
- `/Users/sc/miniconda3/envs/md2word/bin/python -m unittest tests.test_openapi_export`
- `npm --prefix frontend run build`

上述验证没有运行 PDF 解析、翻译 provider 或 Word 生成主流程。

## Phase 3 Gaps

### P0: 文档和验收记录不一致

- `docs/api/openapi.json` 已包含 Translation QA endpoints，但收口前 `docs/api/document-jobs.md` 还没有对应 API 说明。
- 已归档 `translation-result-qa` 任务的 PRD/实现记录仍可能让后续代理误判该能力未完成，需要用收口文档或任务状态说明校正。

### P1: 任务级 QA 状态可见性不足

- Job 详情页只有进入 QA 的按钮，没有在主任务信息区直接展示当前 QA 状态、reviewer、checked time 或 notes 摘要。
- Job 列表没有 QA 状态列，也没有真正的 QA 状态筛选。Phase 3 路线图里“回接任务详情和列表筛选”仍未完成。

### P1: 结果证据展示深度不足

- 当前页面能展示段落、术语 trace 和 AI call summary，但段落、术语命中、AI call 之间还没有形成强关联视图。
- `source_text`、`ai_output_text` 等深度证据依赖 debug archive，可用性受运行时设置限制。需要在 UI 上更明确地区分“无证据文件”和“证据文件存在但为空/不可解析”。

### P2: 前端交互测试不足

- 当前验证覆盖后端和前端构建，但没有浏览器 smoke 测试覆盖 QA 页面加载、保存状态、debug archive 缺失提示、direct job 不可用提示。

## Non-gaps

- 不需要重新实现 Translation QA 基础路由、页面、API、模型字段。
- 不需要重新设计 term rules、translation term sets、proposal review 的 Phase 2 能力。
- 不需要为了 Phase 3 audit 运行实际翻译任务或生成 Word。

## Recommended Task Split

1. `translation-qa-visibility-hardening`

   目标是补齐任务级 QA 状态与结果证据展示的可见性，并修正文档/验收记录不一致。范围包括 `docs/api/document-jobs.md`、任务详情 QA 状态展示、列表 QA 状态列和筛选设计。

2. `translation-qa-segment-trace-hardening`

   目标是把段落、术语命中、AI call trace 做成更强的关联证据视图，明确 debug archive 缺失和证据不可用状态。

3. `translation-qa-browser-smoke`

   目标是补充 QA 页面前端 smoke 测试，覆盖可用任务、不可用任务、保存状态、证据提示和列表入口。

第一个 Phase 3 小任务建议从 `translation-qa-visibility-hardening` 开始，因为它能先把当前已经完成的 QA 能力暴露到日常工作台，并减少后续继续实现时的状态误判。
