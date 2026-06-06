# Translation QA Segment Trace Hardening

## Goal

在现有 Translation QA 页面/API 的基础上，加固“段落 / 术语命中 / AI call trace”的关联证据视图，让 QA/Ops 能快速判断某个最终文本片段对应了哪些术语命中、来自哪些 AI 调用摘要，以及源文/AI 译文对照为什么可用或不可用。

本任务只做 Phase 3 第二个小切片的规划，不启动实现。

## Requirements

- 围绕已有 `GET /api/v1/document-jobs/{job_id}/translation-qa` 响应和 `TranslationResultQaPage.vue` 做证据关联增强。
- 将 `segments`、`term_traces`、`ai_calls` 的展示关系从并列列表提升为可追踪视图。
- 保持 `ai_call_log` metadata-only 边界，不展示完整 prompt、response、正文或密钥。
- 明确 `ai_debug_archive` 缺失、过期、不可解析、无文本时的 UI 状态，不把“无源文对照”误判为翻译失败。
- 只针对 `en2zh_pdf_to_word` 的 Translation QA 详情页，不新增跨任务 QA 工作台。
- 不修改 PDF 解析、翻译 provider、Word 生成、term rules、translation term sets、proposal review 主功能。

## Acceptance Criteria

- [ ] 设计文档明确段落、术语命中、AI call trace 的目标关联模型。
- [ ] 设计文档明确哪些能力可以复用现有 API 字段，哪些需要后端做 additive response 字段。
- [ ] 设计文档明确 evidence unavailable 状态的产品文案和数据来源。
- [ ] 设计文档明确不展示敏感全文、prompt、response、token 或 provider secret。
- [ ] 实现计划拆成小步，避免同时引入浏览器 smoke 或列表筛选改造。
- [ ] 验证计划只包含后端 targeted tests、OpenAPI 如有必要更新、前端 build 或组件级检查；不运行主流程。

## Non-goals

- 不做浏览器 smoke。该项留给后续独立任务。
- 不新增任务级 QA 状态或列表筛选；这些已由 `translation-qa-visibility-hardening` 收口。
- 不做在线编辑译文、段落级标注保存、术语提案 CRUD 或自动评分。
- 不运行 `pdf-mineru` 解析、翻译 provider 调用或 Word 生成主流程。
