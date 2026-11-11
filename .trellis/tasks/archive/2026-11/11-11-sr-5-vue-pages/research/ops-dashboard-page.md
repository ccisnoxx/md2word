# OpsDashboardPage 拆分边界（定稿）

原文件 3004 行（模板 1197、脚本 1456、样式 346）。

## 数据 owner（`features/ops-dashboard/`）

| owner | 文件 | 持有的状态 |
|---|---|---|
| 快照 | `useOpsDashboardData.ts` | `loadDashboard` 并行读取的全部只读数据（readiness、metrics、ops alerts、集成能力、恢复动作 registry、alert/S3 合同、provider 语义核验、失败/运行中任务样例）、`loading`、`error`、`refreshedAt`，以及 readiness 字段读取与派生计数 |
| 健康视图 | `useOpsHealthView.ts` | 无状态派生：摘要指标、整体状态、告警卡片、队列/运行时/资源明细、S3 合同展示项 |
| 告警投递 | `useOpsAlertDelivery.ts` | active 告警选择、去重窗口、fake outbox 与 Phase 7 real-send 的预览/对话框/执行 |
| 告警 destination | `useOpsAlertDestination.ts` | destination ID 输入、dry-run 结果（读取告警投递 owner 的 `selectedActiveAlertCodes`） |
| Provider cancellation | `useProviderCancellation.ts` | 目标表单、预览、fake-cancel 对话框与结果 |
| 任务恢复 | `useOpsJobRecovery.ts` | registry preview、执行确认，执行后调用快照 owner 的 `loadDashboard` |
| 纯映射 | `opsDashboardFormat.ts` | 类型、Phase 7 pilot 常量、标签映射与展示格式化 |

- `loadDashboard` 在原实现中顺带修剪告警选择：快照 owner 通过 `onActiveAlertCodesLoaded` 回调通知告警投递 owner，不直接写对方状态。
- 与设计初稿差异：初稿 `useOpsDashboardData` / `useOpsAlertDelivery` / `useProviderCancellation` 三个；定稿把派生视图（约 350 行）从快照 owner 拆出为 `useOpsHealthView`，把 destination dry-run 与任务恢复各自作为独立 owner，避免单文件超过 500 行。
- 合同与语义核验数据（`alertDeliveryContract`、`s3DeleteContract`、`providerCancellationSemantics`）由快照一次加载写入，因此归快照 owner，展示派生分别放在使用它们的 owner 中。

## 区块组件

| 组件 | DOM 根 |
|---|---|
| `OpsIntegrationControlPanel` | `section[aria-label=真实集成控制面]` |
| `OpsAlertDeliveryPanel` | `section[aria-label=告警 fake outbox 投递]`，`pilot`/`result` 插槽；`alertDeliveryDedupeWindow` 用 `defineModel` |
| `OpsSlackPilotSection` | `section[aria-label=Phase 7 Slack webhook pilot]` |
| `OpsAlertDeliveryResult` | `section[aria-label=告警投递结果]` |
| `OpsS3DeleteContractPanel` | `section[aria-label=S3 delete LocalStack fake parity contract]` |
| `OpsAlertDestinationPanel` | `section[aria-label=告警 destination 配置 dry-run]`；`alertDestinationIdsInput` 用 `defineModel` |
| `OpsProviderCancellationPanel` | `section[aria-label=Provider cancellation fake control]`，`semantics`/`result` 插槽 |
| `OpsProviderSemanticsSection` / `OpsProviderCancellationResult` | 各自的 `section[aria-label]` |
| `OpsActionSafetyPanel` / `OpsWorkerSystemPanels` / `OpsJobSamplesPanel` / `OpsJobRecoveryPreview` | 各自的 `section[aria-label]` |
| `OpsDialogs` | fake-send、real-send、fake-cancel 三个 `el-dialog` |

页面壳保留页头、错误提示、safe operations 提示、指标条、告警卡片与"运维相关入口"。

## 样式归属

与 FileRetention 相同的自动归属规则。拆分中发现并修正一处：`.delivery-actions .el-button { margin-left: 0 }` 里的 `el-button` 是组件生成类，最初被误判为无人使用而留在页面，导致按钮多出 12px 外边距；修正为归属判断时忽略 `el-*` 类后，采集对比恢复 0 差异。未压缩 CSS 由 6.6 kB 增至 16.0 kB。

## smoke 选择器

`getByRole("heading", { name: "运维看板", level: 1 })`、`getByRole("button", { name: "Real-send", exact: true })`（先禁用后启用）、`getByRole("button", { name: "Preview real-send gates" })`、文本"必须先完成一次无 missing gates 的 real-send preview"、`real_send_preview`。
