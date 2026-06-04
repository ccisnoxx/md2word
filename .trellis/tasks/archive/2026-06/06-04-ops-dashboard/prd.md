# Ops dashboard

## Goal

为 Admin/QA-Ops 提供一个轻量、只读的运维看板，集中查看 worker、队列、readiness 警告、失败/运行中任务和资源状态，并给出安全恢复建议与跳转入口。

本子任务不执行恢复动作，不重跑 pdf-mineru 解析、翻译或 Word 生成主流程，不做真实文件删除，也不扩大为完整运维控制台。

## Requirements

- 用户角色
  - Admin：可访问运维看板，查看 worker/queue/readiness/任务风险摘要，并跳转到现有任务列表、任务详情、审计日志、文件保留计划。
  - QA/Ops：通过 Admin 视图判断是否存在 failed stage message、stale running message、失败任务积压、运行中任务积压、资源默认版本缺失或 storage readiness 风险。
  - Operator：不能访问 Admin-only 运维看板。
- 范围
  - 新增一个 Admin-only 前端页面 `OpsDashboardPage`。
  - 页面复用现有 API：
    - `GET /api/v1/health/ready`
    - `GET /api/v1/health/metrics`
    - `GET /api/v1/document-jobs` 的现有筛选能力，用于读取少量失败任务和运行中任务样例。
  - 从现有系统状态页链接到运维看板，保持主导航不膨胀。
  - 展示 worker mode、stage dispatcher、stage message store、stage message counts、stale running、oldest running age、readiness blockers/warnings、artifact/storage 状态、资源默认版本、失败/运行中任务摘要。
  - 根据当前 health/metrics 派生只读告警，例如：
    - `readiness_blockers` 非空。
    - `stage_spool_failed_messages > 0`。
    - `stage_spool_running_stale_messages > 0`。
    - `stage_spool_replayable_messages > 0`。
    - 失败任务数或运行中任务数大于 0。
  - 每条告警提供安全下一步：跳转现有任务筛选、审计日志、系统状态、文件保留计划，或显示排障建议。
- 非目标
  - 不新增后端 API。
  - 不新增 worker 管理、队列消费、重启 worker、强杀任务、批量 retry、bulk recovery、MinerU recovery、cleanup-local-files、物理文件删除或告警配置。
  - 不做真实恢复动作按钮；不调用 `retry`、`recover-mineru-result`、`cleanup-local-files`。
  - 不实现完整术语规则 CRUD 工作台或路线图之外的功能。
  - 不运行 pdf-mineru 解析、翻译或生成 Word 主流程。
- 约束
  - 保持改动小而聚焦，优先前端只读聚合。
  - 不改变现有任务状态机、下载、归档、取消、重试和文件保留语义。
  - 不暴露 secrets、token、客户文件内容或本地绝对 artifact 路径之外的敏感信息；仅展示现有 health/metrics 已公开字段。
  - 页面文案必须说明 dashboard 是观察和排障入口，不是运维执行面板。

## Acceptance Criteria

- [x] Admin 可以打开 Ops Dashboard，并看到 worker/queue/readiness/storage/resource/job 风险摘要。
- [x] Operator 访问 Ops Dashboard 会被现有路由权限拦回任务工作台。
- [x] 页面只调用 `health` 和 `document-jobs` 读接口，不调用 retry/cancel/archive/recover/cleanup/write 类接口。
- [x] 页面能展示 readiness blockers/warnings、stage failed/running/pending/replayable/stale 数量、oldest running age、worker mode、stage dispatcher、metadata store、artifact storage。
- [x] 页面展示少量失败任务和运行中任务样例，并提供跳转到现有 `/jobs` 筛选视图或任务详情的入口。
- [x] 页面提供安全恢复建议文案，不提供真实恢复执行按钮。
- [x] 系统状态页提供到 Ops Dashboard 的入口；主导航不新增多余顶级项。
- [x] 最小验证通过；验证不得运行 pdf-mineru 解析、翻译或 Word 生成主流程。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- Current planning status: not approved for implementation yet.
