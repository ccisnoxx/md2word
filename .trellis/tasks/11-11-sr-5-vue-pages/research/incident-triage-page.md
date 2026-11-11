# IncidentTriagePage 拆分边界（定稿）

原文件 2059 行（模板 410、脚本 1090、样式 555）。

## 数据 owner

| owner | 文件 | 持有的状态 |
|---|---|---|
| 队列与 URL 同步 | `features/incidents/useIncidentQueue.ts` | 筛选 refs、分页、表格偏好、队列数据与汇总、`selectedItems`、`routeSyncInProgress`、自动刷新定时器、`route.query` watcher、挂载/卸载；URL 的唯一写入口（含 `replaceIncidentJobQuery`） |
| 诊断抽屉 | `features/incidents/useIncidentDiagnostic.ts` | `selectedIncidentJobId`、`activeJobId`、抽屉开关/加载/错误/诊断数据、`drawerLoadToken`（旧响应保护） |
| 处置动作 | `features/incidents/useIncidentActions.ts` | `actionPending`、`batchLoading`、`batchResult`/`batchResultExpanded` |
| 编排 | `features/incidents/useIncidentShortcuts.ts` | 无业务状态：`manualRefresh` 与 R/J/K/Esc/Cmd+Enter 快捷键 |
| 保存视图 CRUD | `composables/useWorkbenchSavedViews.ts` | 与 Jobs 共用 |
| 纯映射 | `features/incidents/incidentQuery.ts` | query 解析/构造、筛选芯片、保存视图状态、阶段/失败类型标签 |

- `incident_job_id` 在 URL 中与筛选并存：抽屉 owner 持有当前任务，队列 owner 通过 `selectedIncidentJobId()` getter 读取并负责写回 URL，抽屉通过注入的 `replaceIncidentJobQuery` 请求写回。这样路由写入只有一个出口，`routeSyncInProgress` 防重入逻辑保持在一处。
- 自动刷新条件"抽屉未打开且无批量处理"通过 `canAutoRefresh` 回调读取另外两个 owner。
- 与设计初稿差异：初稿 `useIncidentList` / `useIncidentDisposition` 定稿为 `useIncidentQueue` / `useIncidentActions`，并把抽屉单独作为 owner（它有独立的加载令牌与路由同步）。
- `loadIncidents` 保留原语义：已有请求时直接跳过，不引入请求轮次（原页面没有，本任务不改行为）。

## 区块组件

| 组件 | DOM 根 | 说明 |
|---|---|---|
| `IncidentCommandHeader.vue` | `WorkbenchPageHeader`（`.incident-command-header`） | 同步状态胶囊、刷新（快捷键 R 提示） |
| `IncidentQueuePanel.vue` | `section.incident-list-panel[aria-label=异常队列]` | 筛选芯片、批量结果、队列表格、分页；`defineExpose({ clearSelection, toggleRowSelection, doLayout })` |
| `IncidentFilterToolbar.vue` | `div.toolbar.filter-toolbar` | 通过 `toolbar` 插槽放入，8 个筛选值用 `defineModel` |
| `IncidentBulkActionBar.vue` | `div.bulk-action-bar[aria-label=批量异常操作]` | 批量重试/刷新 |
| `IncidentDiagnosticDrawer.vue` | `el-drawer.incident-diagnostic-drawer` | 诊断摘要、下一步建议、关键证据、事件时间线、文件与入口、底部操作 |

`WorkbenchSummaryStrip`、`SavedViewStrip` 保留在页面壳。

## 样式归属

- 留在页面：`.incident-page`、`.incident-summary-strip`/`.summary-item`、三条 `:global(...)` 规则、页面级断点。
- `.mono` 同时用于队列表格和抽屉，复制到两个组件。
- 组合规则（如 `.command-actions, .toolbar, .bulk-actions, .drawer-actions`、`.active-filter-chips, .job-meta, .evidence-chips`、900px 断点中的多选择器规则）按选择器拆分到各自 owner，声明与顺序不变。

## smoke 选择器

`.incident-table .el-table__body-wrapper tbody tr`、`.incident-table .el-table__header-wrapper`、`.incident-diagnostic-drawer`、`.incident-diagnostic-drawer .diagnostic-panel`、`.incident-diagnostic-drawer .event-meta`、`.filter-toolbar .el-select`、`.status-cell`、`.batch-result-strip`、`.el-checkbox__input`、`getByLabel("快捷键提示")`、`getByRole("heading", { name: "异常处理" })`、按钮文案"搜索/可直接重试/批量刷新/批量重试/执行重试/关闭"、文本"已选 N 个异常"、"事件时间线"。
