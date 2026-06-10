# Configuration Governance UX Consolidation

## Goal

把现有配置中心从“多个平级配置页面”收口为清楚的内部配置治理工作台，让 admin 能区分 draft、published default、runtime live、proposal 和 rollback 之间的关系，并能在发布前看见 diff、preflight、proposal 关联和验证证据。

本任务只规划配置治理 UX consolidation。进入实现前必须先完成 `design.md` 和 `implement.md` 审阅，并显式启动 Trellis task；当前阶段不改业务代码。

## Current State

- `/settings` 已作为配置中心入口，列出模板配置、术语规则集、术语规则检查、翻译配置、翻译术语集。
- 全局 `AppBreadcrumb` 已覆盖配置二级页，二级页可返回 `/settings`。
- `/settings/term-rule-sets` 已有 Term Rule Set draft rule CRUD、diff、preflight、publish、set-default、rollback、proposal context 和 YAML 高级兜底。
- `/settings/term-rules` 已是 live runtime store 的只读查看和模拟页，不提供编辑入口。
- `/settings/translation-profiles` 已覆盖 Translation Profile draft 基础字段、publish、set-default、rollback，但不编辑 prompt 正文或 secret。
- `/settings/translation-term-sets` 已覆盖 Translation Term Set CSV draft import/export、diff/preflight、proposal compatibility、publish、set-default、rollback。
- `/settings/templates` 和 `/settings/templates/:templateId` 已覆盖模板版本、验证任务、publish、set-default 和 disable。

## Requirements

- 配置中心信息架构必须从五个同权入口调整为治理意图更清楚的分组入口：
  - 术语工作台：`当前生效规则` 与 `草稿与发布` 两个子视图。
  - 模板与版式：模板版本、验证证据、发布和默认版本。
  - 翻译治理：翻译配置与翻译术语集。
- 术语规则必须逻辑合并为一个“术语工作台”，但实现上保留两个现有能力边界：
  - `当前生效规则`：读取 live runtime store，只做查看、筛选和模拟。
  - `草稿与发布`：读取 versioned Term Rule Set draft，承载结构化编辑、diff、preflight、proposal 关联和发布。
- 现有深链不能失效，尤其是 proposal 审核页跳转到 Term Rule Set 治理页时携带的 `proposal_id`、`source_term`、`target_rule_id`、`return_tab` 等 query。
- 所有配置发布页必须用一致语言说明资源状态：
  - `draft`：可编辑草稿，不影响已创建 job 或 runtime live。
  - `published`：不可变历史版本。
  - `default`：后续新 job 默认绑定的 published version。
  - `runtime live`：当前转换路径实际消费的 live/runtime 文件或已同步状态。
- 发布前必须能看到风险或证据入口：
  - Term Rule Set：blocking preflight、diff 和 approved-unpublished proposal。
  - Translation Term Set：validation、diff/preflight 和 pending proposal compatibility。
  - Template Version：验证任务 ID、验证说明和发布原因。
  - Translation Profile：基础字段 draft 与 published versions，明确不含 secret 和 prompt body 编辑。
- Operator 不应获得生产配置修改入口；operator 的配置反馈仍通过 proposal / QA 入口流入治理。
- Admin-only 操作被禁用时应保留可理解原因或状态说明，不应只让用户猜测。
- 页面改造应复用现有 API wrapper 和页面能力，优先做 UX consolidation，不引入第二套配置 source of truth。

## Non-Goals

- 不新增通用“系统设置页”。
- 不新增外部客户门户、复杂 RBAC、批量上传、在线译文编辑或 Word 再生成流程。
- 不开放 legacy live term-rules 写入口；MySQL versioned mode 下生产术语修改仍走 Term Rule Set draft/publish。
- 不新增 prompt 正文编辑、secret 管理、provider/S3/worker 环境配置编辑。
- 不把 Translation Term Set CSV 工作流扩展为逐行编辑；逐行编辑作为后续增强。
- 不做 backend API 重写。只有当前端状态说明无法由现有响应支持时，才允许提出最小 additive 合同。

## Acceptance Criteria

- [ ] `/settings` 能以治理分组呈现配置入口，admin 能一眼区分术语、模板、翻译配置和翻译术语的用途。
- [ ] 术语规则入口在 UI 上呈现为“术语工作台”，包含 `当前生效规则` 与 `草稿与发布` 两个子视图 / tabs。
- [ ] `/settings/term-rules` 和 `/settings/term-rule-sets` 的既有 URL、query 深链和 proposal 返回路径保持可用。
- [ ] `当前生效规则` 页面清楚标注为只读 live 检查 / 模拟入口，不出现生产编辑动作。
- [ ] `草稿与发布` 页面清楚标注 draft 编辑不会立即生效，publish / set-default / rollback 才影响默认版本和 runtime 同步。
- [ ] 发布前风险区域能稳定暴露 diff、preflight、blocking finding 和 proposal 关联；blocking 时发布动作不可提交。
- [ ] 模板、翻译配置、翻译术语集页面的状态文案与术语工作台一致，不制造第二套状态解释。
- [ ] Operator 访问 admin-only 配置路由仍被 auth guard 拦截；operator 只能通过 proposal / QA 相关入口提交反馈。
- [ ] 后续实现通过前端 build、最小浏览器 smoke 和相关后端 focused tests（如触及 API 合同）验证。

## Notes

- Parent roadmap: `.trellis/tasks/06-09-md2word-product-maturity-roadmap/roadmap.md`
- This task is the third confirmed product maturity child task after `document-job-workbench-closure` and `translation-qa-review-loop`.
