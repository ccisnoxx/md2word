<template>
  <section class="integration-control-panel app-page-shell app-page-shell--wide" aria-label="真实集成控制面">
    <WorkbenchPanelCard
      title="Integration Control Plane"
      subtitle="真实外部/破坏性能力默认 blocked；此处只展示 gate，不提供执行控件。"
      card-class="dashboard-panel app-table-card"
    >
      <template #actions>
        <div class="toolbar">
          <el-tag :type="integrationOverallStatusTag" effect="plain">
            {{ integrationCapabilities?.overall_status || "not reported" }}
          </el-tag>
          <el-tag effect="plain">ready={{ readyIntegrationCapabilityCount }}</el-tag>
          <el-tag type="warning" effect="plain">blocked={{ blockedIntegrationCapabilityCount }}</el-tag>
        </div>
      </template>

      <el-alert class="delivery-warning" type="warning" title="real integrations disabled by default" :closable="false" show-icon>
        Control plane 只读取 settings 和安全摘要；不会发送通知、调用 provider、执行 S3 delete、运行 scheduler、执行 quota enforcement 或写 audit。
      </el-alert>

      <el-table
        :data="integrationCapabilityRows"
        empty-text="暂无 integration capability 状态"
        table-layout="fixed"
        class="integration-capability-table"
      >
        <el-table-column label="Capability" min-width="230">
          <template #default="{ row }">
            <div class="action-title">
              <span class="mono">{{ row.capability_id }}</span>
              <small>{{ row.label }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="Category" min-width="150" />
        <el-table-column prop="status" label="Status" min-width="130">
          <template #default="{ row }">
            <el-tag size="small" :type="integrationCapabilityStatusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Flags" min-width="230">
          <template #default="{ row }">
            <span class="mono">
              enabled={{ booleanLabel(row.real_execution_enabled) }} /
              dry_run={{ booleanLabel(row.dry_run_only) }} /
              kill={{ booleanLabel(row.kill_switch_active) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Blocking Reasons" min-width="360" show-overflow-tooltip>
          <template #default="{ row }">{{ row.blocking_reasons.join(" / ") || "none" }}</template>
        </el-table-column>
      </el-table>

      <el-descriptions v-if="integrationSafetyItems.length" class="delivery-safety" :column="5" border size="small">
        <el-descriptions-item v-for="item in integrationSafetyItems" :key="item.label" :label="item.label">
          <span class="mono">{{ item.value }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </WorkbenchPanelCard>
  </section>
</template>

<script setup lang="ts">
// 真实集成控制面：能力 readiness、阻断与安全标记。
import type { UnwrapRef } from "vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { integrationCapabilityStatusTag, booleanLabel } from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";

const {
  integrationOverallStatusTag,
  integrationCapabilities,
  readyIntegrationCapabilityCount,
  blockedIntegrationCapabilityCount,
  integrationCapabilityRows,
  integrationSafetyItems,
} = defineProps<{
  integrationOverallStatusTag: UnwrapRef<OpsDashboardData["integrationOverallStatusTag"]>;
  integrationCapabilities: UnwrapRef<OpsDashboardData["integrationCapabilities"]>;
  readyIntegrationCapabilityCount: UnwrapRef<OpsDashboardData["readyIntegrationCapabilityCount"]>;
  blockedIntegrationCapabilityCount: UnwrapRef<OpsDashboardData["blockedIntegrationCapabilityCount"]>;
  integrationCapabilityRows: UnwrapRef<OpsDashboardData["integrationCapabilityRows"]>;
  integrationSafetyItems: UnwrapRef<OpsDashboardData["integrationSafetyItems"]>;
}>();
</script>

<style scoped lang="scss">
.integration-control-panel {
  display: grid;
  gap: var(--app-space-4);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.delivery-warning {
  margin-bottom: var(--app-space-4);
}

.delivery-safety {
  margin-bottom: 12px;
}

.integration-capability-table {
  width: 100%;
}

.dashboard-panel {
  border-color: var(--app-color-border);
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.action-title {
  display: grid;
  gap: 3px;
}

.action-title small {
  color: var(--app-color-text-muted);
}

@media (max-width: 720px) {
  .toolbar {
    justify-content: flex-start;
  }
}
</style>
