# Frontend information architecture

## Goal

补齐 md2word 内部工作台第一阶段的信息架构入口，让 Operator/Admin 登录后能从主导航进入任务工作台、术语建议/提案审核、配置中心和系统状态入口，同时用前端路由守卫保护 Admin-only 页面。

本子任务只处理前端入口和权限边界，不接入或重跑 pdf-mineru 解析、翻译、生成 Word 主流程。

## Requirements

- 主导航必须暴露第一阶段内部工作入口：
  - 所有登录用户可进入任务工作台。
  - 所有登录用户可进入术语建议页面；Admin 在同一页面看到审核相关 tab。
  - Admin 可进入配置中心。
  - Admin 可进入系统状态入口。
- Admin-only 页面必须同时满足：
  - Operator 不在主导航中看到入口。
  - Operator 直接访问 Admin-only URL 时被前端路由拦截，不进入页面。
- 系统状态本次只做信息架构入口和轻量页面壳，不实现完整只读状态看板；完整 readiness/metrics 展示留给 `admin-system-status` 子任务。
- 不新增后端 API，不修改现有接口契约。
- 不实现完整术语规则 CRUD 工作台，不做真实文件删除，不触碰 pdf-mineru 主流程。
- 改动保持小而聚焦，优先复用现有 `AppLayout.vue`、`router/index.ts`、`RoleGate.vue` 和现有页面结构。

## Acceptance Criteria

- [x] Admin 登录后主导航包含：任务工作台、配置中心、提案审核、系统状态。
- [x] Operator 登录后主导航包含：任务工作台、术语建议；不显示配置中心和系统状态。
- [x] Operator 直接访问 `/settings`、`/settings/templates`、`/settings/term-rule-sets`、`/settings/translation-profiles`、`/settings/templates/:templateId` 或 `/system-status` 时会被路由守卫带回 `/jobs`。
- [x] Admin 可以直接访问配置中心及其子页面、系统状态入口页。
- [x] 术语建议/提案审核仍复用现有 `TermProposalsPage`，不扩大为完整术语 CRUD 工作台。
- [x] 本子任务不产生任何后端 API 变更，不运行 pdf-mineru 解析/翻译/生成 Word 主流程。
- [x] 最小验证通过：`npm run build`（frontend）和 Trellis task validation。

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
- Parent roadmap: `.trellis/tasks/06-03-product-roadmap`.
