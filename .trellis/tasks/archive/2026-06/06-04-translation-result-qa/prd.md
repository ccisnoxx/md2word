# Translation result QA

## Goal

为 `en2zh_pdf_to_word` 文档任务补一个轻量翻译结果 QA 入口，让内部 Operator/Admin 能在不重跑解析、翻译或 Word 生成主流程的前提下，查看现有翻译证据、术语命中摘要、AI 调用审计摘要，并记录任务级复核结论。

本任务是产品成熟化路线图中 `translation-result-qa` 的第一版小切片，不做完整段落质检工作台，不扩展术语规则 CRUD，不做文件删除或主流程重算。

## Requirements

- 只针对已有 `document_jobs` 工作台内的 `en2zh_pdf_to_word` 任务。
- 从现有产物读取证据：
  - `document_ir`：用于展示最终渲染文本片段和 layout / quality flags。
  - `ai_call_log`：用于展示 metadata-only AI 调用摘要和术语命中 trace。
  - `ai_debug_archive`：仅当文件存在且未过期时，可选补充原文/AI 译文对照；默认不要求存在。
- 新增任务级 QA 状态，至少支持：
  - 未复核
  - 通过
  - 需修正
  - 阻塞/无法判断
- QA 记录需保存复核人、复核时间、问题归因和备注，并在任务事件流中留下非敏感事件。
- 前端从任务详情进入轻量 QA 页面；页面必须清楚标注哪些证据可用、哪些因为现有产物缺失而不可用。
- 保持现有提案流不变；QA 页面可以链接回任务详情/术语建议入口，但不新增完整术语管理功能。

## Acceptance Criteria

- [ ] `en2zh_pdf_to_word` 任务详情页能进入翻译 QA 页面；`direct_pdf_to_word` 任务不展示误导性的翻译 QA 操作。
- [ ] QA 页面展示任务身份、状态、绑定资源版本、可用证据文件、layout quality flags、AI 调用摘要、术语命中摘要和最终文本片段。
- [ ] 当缺少 `ai_debug_archive` 或其已过期时，页面仍可展示可用证据，并明确“源文/AI 译文对照不可用”的原因。
- [ ] Operator/Admin 可保存任务级复核结论；后端校验任务可见性并持久化 QA 字段。
- [ ] 保存复核结论后，任务详情 API 返回最新 QA 字段，事件流出现 `translation_qa_updated` 事件且不包含全文正文。
- [ ] 不触发 pdf-mineru 解析、翻译、生成 Word 主流程，不删除任何文件，不新增完整术语规则 CRUD。
- [ ] 完成实现后运行最小必要验证：后端 targeted unittest；前端类型检查或构建；如新增/修改 API，更新并校验 OpenAPI 快照。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
