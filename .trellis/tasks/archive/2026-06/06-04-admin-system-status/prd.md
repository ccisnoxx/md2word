# Admin system status

## Goal

把路线图中 `admin-system-status` 子任务落成一个小范围、只读、Admin-only 的系统状态页面。

页面应让 Admin 不离开内部工作台即可查看后端 readiness、metrics、worker、metadata store、artifact storage、默认资源状态，并能跳转到失败任务和运行中任务筛选视图。它不提供任何在线修改配置、管理 worker、删除文件或重新触发主转换流程的能力。

## Requirements

- 角色边界
  - 仅 Admin 可从主导航进入并访问系统状态页面。
  - Operator 不应看到系统状态入口；直接访问路由时应沿用现有路由守卫回到任务工作台。
- 数据来源
  - 优先复用现有 `GET /api/v1/health/ready` 和 `GET /api/v1/health/metrics`。
  - 本子任务不新增 `GET /api/v1/system/status`，除非实现阶段发现前端无法可靠表达当前 health 合同。
  - 不修改 readiness/metrics 的后端语义，不新增数据库字段。
- 页面内容
  - 展示整体 readiness：ready / blocked / degraded / unknown，并列出 blockers 和 warnings。
  - 展示 backend/storage/worker 基础状态：metadata store、artifact storage、worker mode、stage dispatcher、stage message store、artifact writable、disk free。
  - 展示任务/队列计数：running/pending/queued/failed/succeeded/canceled 等可用计数，stage message pending/running/failed/stale。
  - 展示默认资源状态：默认 template、term rule set、translation term set、translation profile；没有字段时明确显示 unavailable / not reported。
  - 提供失败任务、运行中任务的跳转入口；只用于筛选任务列表，不执行任何任务操作。
  - 提供手动刷新和加载/错误状态。
- 范围约束
  - 不重跑 pdf-mineru 解析、翻译或生成 Word 主流程。
  - 不实现完整术语规则 CRUD 工作台。
  - 不做真实文件删除、清理计划、worker 管理、告警配置、全量审计页面。
  - 不增加危险运维按钮；页面只读。
- URL 筛选约定
  - 若系统状态页链接到 `/jobs?status=failed` 或 `/jobs?status=running`，任务列表需要能读取该 query 并应用已有筛选能力。

## Acceptance Criteria

- [ ] Admin 打开 `/system-status` 能看到 readiness、backend/storage/worker、任务/队列 metrics、默认资源状态。
- [ ] Operator 主导航不显示系统状态；直接访问 `/system-status` 时不会进入页面。
- [ ] 页面只调用 health/metrics 类只读接口；不调用 document job 创建、重试、取消、归档、下载、文件删除或任何主流程执行接口。
- [ ] readiness blockers/warnings、stage message 异常和资源缺失能以可读文案呈现，不要求复杂图表。
- [ ] 失败任务和运行中任务入口能把用户带到任务列表对应筛选视图。
- [ ] health 接口失败时页面显示标准错误提示，并保留刷新入口。
- [ ] 最小验证通过：前端类型检查/build；如改动后端合同，则补充并运行对应后端测试。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- Parent roadmap: `.trellis/tasks/06-03-product-roadmap/`.
- Existing placeholder page: `frontend/src/pages/SystemStatusPage.vue`.
