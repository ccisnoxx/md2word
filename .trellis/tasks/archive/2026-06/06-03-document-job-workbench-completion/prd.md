# Document job workbench completion

## Goal

补齐内部任务工作台中“任务列表 + 任务详情”的日常操作闭环，让 Operator/Admin 可以在不重新运行 pdf-mineru 解析、翻译、生成 Word 主流程的前提下，完成任务查询、监控、下载、失败重试、处理中取消、终态归档和轻量批量操作。

本子任务是 `.trellis/tasks/06-03-product-roadmap/implement.md` 中 Phase 1 的 `document-job-workbench-completion`，只负责任务列表与任务详情工作台补强。文件/结果区、任务上下文提案、Admin 创建/重试配置选择、系统状态页和完整术语规则 CRUD 分别由其他子任务覆盖。

## Requirements

- 任务列表
  - 保留现有上传入口和任务列表结构。
  - 支持状态筛选、轻量搜索、排序、归档筛选。
  - 行操作支持查看、下载成功任务、重试失败任务、取消 pending/queued/running 任务、归档 succeeded/failed/canceled 任务。
  - 支持轻量批量重试失败任务、轻量批量归档终态任务；第一阶段允许前端逐个调用已有单任务 API。
- 任务详情
  - 顶部 action panel 暴露刷新、下载、重试、取消、归档。
  - 失败信息和事件流继续按后端返回展示，不在前端推断主流程状态。
  - 取消文案必须说明只标记取消并停止后续处理，不承诺强杀已经进入外部服务的长耗时阶段。
  - 归档文案必须说明归档只从默认列表隐藏，不删除文件、事件或结果。
- 后端查询
  - 复用现有 `POST /api/v1/document-jobs/{job_id}/retry`、`POST /api/v1/document-jobs/{job_id}/cancel`、`DELETE /api/v1/document-jobs/{job_id}`、`GET /api/v1/document-jobs/{job_id}/download-url`。
  - 增强 `GET /api/v1/document-jobs` 查询参数，支持 `q`、`sort`、`include_archived`、`created_from`、`created_to`，并保持现有 `status`、`page`、`page_size` 行为兼容。
- 权限与角色
  - 保留后端当前 owner/admin 可见性规则。
  - Operator 不获得 Admin-only 配置选择能力；Admin 只因已有可见性规则看到更多任务。
- 约束
  - 不重跑 pdf-mineru 解析、翻译、生成 Word 主流程。
  - 不新增批量后端 API。
  - 不做真实文件删除。
  - 不做完整术语规则 CRUD 工作台。
  - 不做文件/结果区、任务上下文提案、Admin 配置选择和系统状态页。
  - 改动保持小而聚焦，优先复用现有组件、API wrapper、格式化工具和后端 service/repository 边界。

## Acceptance Criteria

- [ ] `GET /api/v1/document-jobs` 默认仍隐藏已归档任务；`include_archived=true` 可查看已归档任务。
- [ ] `GET /api/v1/document-jobs` 支持按 `q` 搜索任务 ID、源文件 ID、源文件名、错误码或错误信息。
- [ ] `GET /api/v1/document-jobs` 支持有限排序枚举，至少覆盖创建时间和更新时间的正/倒序；非法排序返回明确 400。
- [ ] `GET /api/v1/document-jobs` 支持创建时间范围筛选，并不改变现有分页响应 shape。
- [ ] 任务列表页面能组合状态、搜索、排序、归档筛选后刷新列表。
- [ ] 任务列表行操作可按状态正确启用/禁用：成功下载、失败重试、活动任务取消、终态任务归档。
- [ ] 批量重试只对选中的失败任务发起逐个重试；批量归档只对选中的终态未归档任务发起逐个归档，并汇报成功/失败数量。
- [ ] 任务详情 action panel 支持取消和归档，并在操作成功后刷新任务和事件。
- [ ] 取消和归档确认文案准确表达语义：取消不承诺强杀外部长任务；归档不是删除。
- [ ] 前端 build 通过，后端最小 API 测试通过。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
