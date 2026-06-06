# Translation QA Visibility Hardening

## Goal

在不改动翻译主流程的前提下，把已经实现的 Translation QA 状态和证据能力回接到日常任务工作台，并修正 API/验收文档不一致，降低 Phase 3 后续工作的状态误判风险。

## Requirements

- 在 `docs/api/document-jobs.md` 补充 Translation QA API 说明，覆盖 `GET`、`PATCH`、状态枚举、仅支持 `en2zh_pdf_to_word`、证据文件可用性和非敏感事件约束。
- 更新已归档 `translation-result-qa` 的收口状态说明，明确基础 QA 页面/API/测试已经实现，后续不应重复实现。
- 在 `JobDetailPage` 的任务信息或操作区展示当前 QA 状态、reviewer、checked time 和 notes 摘要，让用户不进入 QA 页也能判断是否已检查。
- 在 Jobs 工作台展示 QA 状态，并提供可用于日常排查的筛选方式。
- 列表筛选必须避免“只筛当前页”的误导；如果做筛选，应由后端任务列表 API 支持，或在产品文案中明确其局限。
- 保持 direct job、非 PDF 翻译 job、没有 QA 状态的旧 job 的展示兼容性。

## Acceptance Criteria

- [x] `docs/api/document-jobs.md` 与 OpenAPI JSON 中 Translation QA endpoints 一致。
- [x] 已归档 `translation-result-qa` 任务有明确收口说明，不再表现为未完成基础实现。
- [x] 任务详情页能直接展示 Translation QA 当前状态和最近检查信息。
- [x] Jobs 工作台能展示 `en2zh_pdf_to_word` job 的 QA 状态，并能可靠筛选或明确说明筛选范围。
- [x] direct job 不显示误导性的 Translation QA 状态或入口。
- [x] 新增/调整的后端列表筛选有单元测试；前端变更至少通过 build，必要时补充组件或浏览器 smoke。

## Non-goals

- 不实现段落级 trace 关联视图。
- 不改动 term rules、translation term sets、proposal review 的既有功能。
- 不运行 PDF 解析、翻译 provider 或 Word 生成主流程。
- 不重新实现 Translation QA 基础详情页和 API。
