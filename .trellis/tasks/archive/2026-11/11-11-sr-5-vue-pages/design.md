# 设计

## 1. 约定（沿用 `features/job-detail`）

```text
frontend/src/features/<page>/
  <Section>Panel.vue        纯展示 + 本区块交互；props 输入、emits 输出；本区块 scoped 样式
  <Name>Dialog.vue          对话框；v-model:visible + submit 事件；关闭后焦点返回由页面持有的触发器 ref 负责
  use<Page><Owner>.ts       数据 owner：ref/computed、加载、轮询、错误归一化；每个数据源只有一个 owner
  <page>Format.ts           纯格式化/映射函数（从页面 script 中迁出的无状态 helper）
```

页面壳：

```vue
<script setup lang="ts">
const data = useOpsDashboardData(route);
const alerts = useOpsAlertDelivery(data);
</script>
<template>
  <IntegrationControlPanel :state="data.integration" @refresh="data.reload" />
  ...
</template>
```

## 2. 拆分边界（初稿）

| 页面 | 区块组件 | composable |
|---|---|---|
| OpsDashboard | IntegrationControlPanel、AlertDeliveryPanel、AdapterContractPanel、AlertDestinationPanel、ProviderCancellationPanel、ActionSafetyPanel、WorkerSystemPanels、JobSamplesPanel、OpsReferenceGrid；三个对话框（fake-send、real-send、fake-cancel） | `useOpsDashboardData`（快照加载/刷新）、`useOpsAlertDelivery`（fake/real 投递与 destination dry-run）、`useProviderCancellation` |
| FileRetention | 按页面 section 划分：策略配置、清理预览/运行、历史、详情抽屉 | `useRetentionPolicy`、`useRetentionCleanup` |
| JobsPage | 筛选栏、批量动作条、表格区（复用现有 `JobTable`）、对话框 | `useJobsListQuery`（URL query 同步 + 加载）、`useJobsBatchActions` |
| IncidentTriage | 筛选/分组、事件列表、详情抽屉、处置对话框 | `useIncidentList`、`useIncidentDisposition` |

第 0 步逐个页面阅读 script，按"状态被谁写入"划分 owner，并把定稿后的划分写入 `research/<page>.md`；如果与初稿不同，以定稿为准。

## 3. 关键风险与处理

- **URL query 与列表状态同步**（JobsPage、IncidentTriage）：`watch(route.query)` 和请求竞态防护（已有 `jobRequestRaces.test.ts`）必须整体迁入同一个 composable，不能拆散到多个组件中。
- **scoped 样式归属**：每个区块的样式随组件迁移；页面级布局类（`app-page-shell` 等全局类）保留在原 DOM 上。迁移后用浏览器 computed style 抽查滚动根。
- **焦点返回**：对话框关闭后的焦点返回目标由页面持有 ref，并通过 prop 传给对话框，行为与现状一致。
- **smoke 选择器**：拆分前用 `rg` 收集 smoke spec 中针对这 4 个页面的 `getByRole/getByLabel/locator` 选择器，拆分后逐一确认仍然存在。

## 4. 被拒绝的方案

- 为每个页面新建 Pinia store：状态只属于单个页面实例，放进全局 store 会延长生命周期并带来跨路由残留。
- 使用 `provide/inject` 跨层传递：层级只有 1–2 层，props/emits 更显式。
