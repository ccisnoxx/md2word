# Document Job Workbench Closure

## Goal

补齐文档任务工作台的日常闭环能力，让内部操作员 / 管理员可以在不进入底层主流程、不依赖系统状态页的情况下完成任务查找、状态判断、失败处理、结果下载、归档恢复和重新发起任务。

本任务只规划 `document-jobs` 工作台体验和配套 API 合同，不改动 PDF-MinerU 解析、翻译、Word 生成主流程。

## Requirements

- `/jobs` 列表需要成为任务运营入口，覆盖搜索、状态筛选、QA 状态筛选、归档视图、时间范围筛选、快速定位失败 / 运行中任务、批量操作入口。
- `/jobs` 列表近期补齐批量取消；已有批量 retry / archive 继续保留，但展示动作是否可用必须以服务端返回为准。
- `/jobs/:jobId` 详情需要把概览、文件、事件日志、失败诊断、运行上下文分区清楚，支持从列表进入后稳定返回上级层级。
- 全局采用 breadcrumb / 层级导航模式，替代各页面零散手写返回按钮。配置中心、任务列表、任务详情、QA 详情等页面都应有一致的上级路径。
- 后端在 `DocumentJobResponse` 增加 `available_actions`，每个 action 至少包含 `enabled` 和 `disabled_reason`。前端可以保留轻量兜底判断，但按钮展示、禁用原因和主路径逻辑以服务端为准。
- 任务动作语义保持清晰：
  - `retry` 仅表示对失败任务按原任务语义重试。
  - `clone/rerun as new job` 表示创建一个新任务，复制源任务输入和可复用配置快照，原任务不被修改。
  - `archive` 只是从默认列表隐藏任务。
  - `unarchive` 用于误归档恢复。
- 近期不做真实删除任务，不做按任务删除文件；文件删除继续由文件库 / retention / cleanup 的预览、确认、审计流程承担。
- 近期不做批量上传。
- 近期不做独立任务配置预设页；创建 / clone / rerun 使用默认业务资源或显式发布版本。
- 后端操作需要记录足够的任务事件或审计信息，至少覆盖 retry、clone/rerun、cancel、archive、unarchive 等用户可见动作。
- 优先复用现有 `document-jobs` API 和任务模型；只有当前合同无法表达动作可用性、恢复归档、clone/rerun 时才新增接口或字段。

## Acceptance Criteria

- [ ] 操作员可以从 `/jobs` 完成任务搜索、状态筛选、QA 状态筛选、时间范围筛选、打开详情、下载结果、查看失败原因。
- [ ] 管理员可以在服务端允许时批量 retry / cancel / archive，并在不允许时看到明确 `disabled_reason`。
- [ ] 单任务详情可以执行 cancel、retry、archive、unarchive、clone/rerun as new job；动作可用性来自 `available_actions`。
- [ ] `retry` 与 `clone/rerun as new job` 在 UI 文案、API 语义和数据记录上保持分离。
- [ ] `clone/rerun as new job` 创建新任务，并能追溯 `source_job_id`、源配置快照或等价审计信息。
- [ ] 归档任务可通过 `unarchive` 恢复到默认工作流视图。
- [ ] 全局 breadcrumb 覆盖任务列表、任务详情、QA 详情和配置中心子页，至少解决“配置中心 -> 模板配置不能返回”的导航断点。
- [ ] 不实现真实删除任务、按任务删除文件、批量上传、独立任务配置预设页。
- [ ] 本任务进入实现前需要补 `design.md` 和 `implement.md`，明确前后端接口、数据字段、迁移和验收方式。

## Notes

- Parent roadmap: `.trellis/tasks/06-09-md2word-product-maturity-roadmap/`.
- 当前阶段为 planning；不要在本任务中重新跑 PDF-MinerU 解析 / 翻译 / Word 生成主流程。
