# Job context proposals

## Goal

让 Operator/Admin 能从任务详情页带着当前任务上下文提交术语规则提案或翻译术语提案，并让 Admin 在现有提案审核页看到来源任务回链。

本子任务只补齐路线图 Phase 1 的任务上下文提案闭环，不重新运行 pdf-mineru 解析、翻译、生成 Word 主流程。

## Requirements

- 任务详情页提供明确的“提交术语规则建议”和“提交翻译术语建议”入口。
- 入口必须携带当前任务上下文：
  - `source_job_id`
  - `source_file_id`
  - 当前任务绑定的 Term Rule Set 版本
  - 英文翻译任务绑定的 Translation Term Set 版本
- 术语规则提案表单复用现有审核流，提交时带上任务来源和已观测术语规则版本。
- 翻译术语提案补一个轻量创建表单，提交一条 add/update/delete change，进入现有 Translation Term Proposal 审核流。
- 提案审核页在术语规则提案和翻译术语提案详情里展示来源任务，并可跳回对应任务详情。
- Operator 只能看到自己的提案和创建入口；Admin 继续看到审核/全部队列。
- 不新增后端主流程，不新增完整术语规则 CRUD 工作台，不做真实文件删除。

## Non-goals

- 不实现完整术语规则 CRUD 工作台。
- 不实现 Translation Term Set 管理台。
- 不做段落对照质检页或翻译结果页。
- 不从 PDF/Word 自动抽取原文片段。
- 不新增物理文件删除、任务删除或重跑主流程能力。
- 不改变 proposal 审核、approve/publish/reject 的后端语义。

## Acceptance Criteria

- [x] 从任务详情页点击术语规则建议入口，会进入提案页的新建表单，并预填/锁定当前 `job_id`、`source_file_id` 和 observed Term Rule Set 版本。
- [x] 从英文翻译任务详情页点击翻译术语建议入口，会进入轻量翻译术语提案表单，并预填当前 `job_id`、`source_file_id` 和 observed Translation Term Set 版本。
- [x] 翻译术语建议表单至少支持提交单条 add/update/delete change；add 必填 `source_term` 和 `target_term`。
- [x] 术语规则提案提交请求包含现有后端已支持的上下文字段，不需要新增后端字段。
- [x] 翻译术语提案提交请求包含现有后端已支持的上下文字段，不需要新增后端字段。
- [x] 审核详情展示来源任务并提供 `/jobs/{job_id}` 回链；无来源任务时保持当前空态。
- [x] Operator 看不到 Admin-only 审核队列；Admin 原有审核流程不退化。
- [x] 最小验证通过：前端类型检查/构建成功；不运行 pdf-mineru 主流程。

## Notes

- Existing backend contracts already expose most required context fields:
  - Term Rule Proposal: `source_job_id`, `source_file_id`, `page_number`, `context_before`, `context_after`, `observed_term_rule_set_id`, `observed_term_rule_version`.
  - Translation Term Proposal: `source_job_id`, `source_file_id`, `observed_translation_term_set_id`, `observed_translation_term_version`.
- Frontend has no dedicated Trellis spec under `.trellis/spec/`; use existing Vue/Element Plus patterns from current pages/components.
