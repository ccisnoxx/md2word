# JobsPage 拆分边界（定稿）

原文件 2106 行（模板 260、脚本 1160、样式 680）。

## 数据 owner

| owner | 文件 | 持有的状态 |
|---|---|---|
| 列表与 URL 同步 | `features/jobs/useJobsList.ts` | 筛选 refs、分页、表格偏好、列表数据与汇总、`selectedJobs`、请求轮次 `jobsRequestRound`、`disposed`、`routeSyncInProgress`、自动刷新定时器、`route.query` watcher、挂载/卸载 |
| 行级/批量动作 | `features/jobs/useJobsActions.ts` | `actionPending`、`batchLoading`、`batchResult`/`batchResultExpanded`、`lastDownloadLink` |
| 保存视图 CRUD | `composables/useWorkbenchSavedViews.ts`（与 Incidents 共用） | `savedViews`、`savedViewsLoading` |
| 纯映射 | `features/jobs/jobsListQuery.ts` | 无状态：query 解析/构造、筛选芯片、保存视图状态 |

- 与设计初稿差异：初稿名 `useJobsListQuery` / `useJobsBatchActions`，定稿合并为 `useJobsList`（query 同步与请求竞态必须在同一 owner）和 `useJobsActions`（行级与批量动作共享 `actionPending`、错误恢复与批量结果）。
- `batchResult` 由动作 owner 持有；筛选/分页/应用视图/路由变化需要清空它，因此 `useJobsList` 通过 `onResultReset` 回调通知，不直接写对方状态。
- 保存视图 CRUD 在 JobsPage 与 IncidentTriagePage 中逐行重复（仅 `page_key` 不同），抽成共享 composable；"应用视图"仍留在各自的列表 owner 中，因为它要写路由。
- 创建权限（`auth.hasPermission`）、`goCreateJob`、`clearSelection`（需要表格实例）留在页面壳。

## 区块组件

| 组件 | DOM 根 | 说明 |
|---|---|---|
| `JobsCommandHeader.vue` | `WorkbenchPageHeader`（`.jobs-command-header`） | 同步状态胶囊、创建、刷新 |
| `JobsWorkQueueStrip.vue` | `WorkbenchSummaryStrip`（`.work-queue-strip`） | 优先工作队列四项的计数与激活态 |
| `JobsListPanel.vue` | `section.jobs-list-panel[aria-label=任务列表]` | 快捷筛选、筛选芯片、停滞/失败/下载提示、批量结果、状态汇总、表格卡片；`defineExpose({ clearSelection })` |
| `JobsFilterToolbar.vue` | `div.toolbar.primary-toolbar` | 通过 `JobsListPanel` 的 `toolbar` 插槽放入，筛选值用 `defineModel` |
| `JobsBulkActionBar.vue` | `div.bulk-action-bar[aria-label=批量操作]` | 批量重试/取消/归档 |

DOM 结构、类名、`aria-label` 与原页面逐元素一致（不新增包装元素）。

## 样式归属

- 留在页面：`.jobs-page` 根与伪元素、`.jobs-page :deep(...)` 系列、`.saved-view-strip`、`.table-kicker`、页面级断点。
- 其余规则按 DOM 所有者迁入对应组件，保持原有书写顺序；组合规则 `.jobs-command-header, .work-queue-strip, .saved-view-strip, .jobs-list-panel` 按选择器拆分到各自 owner。
- 迁移后的 header/queue/toolbar 样式经脚本与原规则逐条比对一致。

## 单元测试

- `jobRequestRaces.test.ts` 的 JobsPage 用例原先用 `executePageRequests` 从 `.vue` 源码里抽函数执行；改为直接调用 `useJobsList`，断言不变。`executePageRequests` 因此不再有使用者，已删除。
- 新增 `jobsListQuery.test.ts`（query 往返、非法值回落）与 `useWorkbenchSavedViews.test.ts`（相邻排序、越界不请求、失败交给页面错误）。

## smoke 选择器（拆分后逐元素对比确认仍存在）

`.jobs-table-card .el-table__body-wrapper .el-checkbox`、`.jobs-table-card .el-table__header-wrapper`、`.jobs-table-card .table.is-compact-density`、`.job-table .more-action`、`.work-queue-strip`、`#jobs-table-settings`（`settings-id`）、`getByRole("heading", { name: "任务列表" })`、`getByLabel("批量操作")`、按钮文案"更多筛选/搜索/刷新/创建任务/批量重试/批量取消/批量归档/清除选择"。
