# FileRetentionPage 拆分边界（定稿）

原文件 2329 行（模板 1060、脚本 1005、样式 262）。

## 数据 owner

| owner | 文件 | 持有的状态 |
|---|---|---|
| 页面壳 | `pages/FileRetentionPage.vue` | 页面级 `error`（各 owner 共享写入）、`activeFileManagementTab` 与 `?tab=` 双向同步、工作区导航卡片、`refreshRetentionPage`、挂载时并行加载 |
| 文件库 | `features/file-retention/useRetentionLibrary.ts` | 筛选、排序、分页、搜索结果 |
| 容量与配额 | `features/file-retention/useRetentionCapacity.ts` | storage usage、quota dry-run 表单与结果、quota ops summary |
| 保留策略 | `features/file-retention/useRetentionPolicy.ts` | 策略列表、影响预览、draft 对话框、需要 reason 的治理动作 |
| 清理历史与调度器 | `features/file-retention/useRetentionHistory.ts` | durable history 列表/详情、scheduler dry-run 表单与报告；提供 `showCleanupRunHistory(runId)` |
| 清理执行 | `features/file-retention/useRetentionCleanup.ts` | retention 计划、候选选择、物理删除与 manual cleanup run 的预览/确认/执行 |
| 纯映射 | `features/file-retention/retentionFormat.ts` | 状态标签、安全标记分类、unknown 报告字段读取 |

- 与设计初稿差异：初稿只有 `useRetentionPolicy`、`useRetentionCleanup` 两个 owner；定稿按数据源拆为 5 个，因为文件库、容量、历史各自有独立请求与加载态，合并会超过 500 行且混淆 owner。
- `error` 由页面创建并注入各 owner，保持原页面"任一区块请求开始清空、失败写入同一个提示"的行为。
- 清理执行需要在预览/执行后刷新历史并展示同一 run 的详情：通过注入 `history.loadCleanupRunHistory` / `history.showCleanupRunHistory` 完成，调用顺序与原实现逐行一致（预览：先详情后列表；执行与调度器：先列表后详情）。

## 区块组件（`features/file-retention/`）

| 页签 | 组件 | DOM 根 |
|---|---|---|
| 文件库 | `RetentionLibraryPanel` | `section[aria-label=文件库搜索]`；`librarySort`/`libraryPage`/`libraryPageSize` 用 `defineModel` |
| 容量与策略 | `RetentionStoragePanel` | `section[aria-label=存储使用和容量 readiness]`，`quota` 插槽 |
| | `RetentionQuotaPanel` | `div.quota-dry-run-panel`，`ops` 插槽 |
| | `RetentionQuotaOpsPanel` | `div.quota-ops-panel` |
| | `RetentionPlanSummary` | `section[aria-label=文件清理计划摘要]` |
| | `RetentionPolicyPanel` | 两个根：`section[aria-label=保留策略治理]` 与 `v-if` 的影响预览 |
| 清理执行 | `RetentionCandidatesPanel` | `section[aria-label=过期候选文件]` |
| | `RetentionDeleteReportPanel` / `RetentionCleanupRunPanel` / `RetentionSchedulerPanel` / `RetentionHistoryPanel` | 各自的 `section[aria-label]` |
| 对话框 | `RetentionDialogs` | 三个 `el-dialog`（原地渲染，未 append-to-body） |

reactive 表单对象（`libraryFilters`、`quotaPolicyForm`、`deleteDialog` 等）按 `JobActionDialogs` 先例作为 prop 传入，子组件通过 `v-model="obj.field"` 修改字段。

## 样式归属

多个区块共用 `retention-table-section`、`section-header`、`safety-grid`、`cleanup-run-card` 等类。按"组件模板中实际出现的类名"自动归属：一条规则的类（忽略 `:deep()` 内部与 Element Plus 的 `el-*` 类）全部出现在某组件模板中即复制到该组件，保持原顺序与声明；无任何模板使用的规则留在页面。代价是未压缩 CSS 由 4.3 kB 增至 11.1 kB。

## smoke 选择器

`getByRole("heading", { name: "文件管理与清理", level: 1 })`、`getByRole("heading", { name: "文件库搜索" })`、`getByRole("button", { name: /清理执行/ })`、`getByRole("heading", { name: "过期候选" })`、按钮"执行物理删除""执行 cleanup run"（禁用态）、文本 `smoke.pdf`。
