<template>
  <section class="action-safety-panel app-page-shell app-page-shell--wide" aria-label="恢复动作安全注册表">
    <el-card class="card-flat dashboard-panel app-panel-card app-table-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Recovery Action Safety Registry</h2>
          <p class="section-subtitle">Admin-only 动作目录；文档任务动作先 preview eligibility，再交给既有 document-jobs 端点执行。</p>
        </div>
        <el-tag type="info" effect="plain">{{ recoveryActionSummary }}</el-tag>
      </div>
      <el-table :data="recoveryActions" empty-text="暂无 recovery action registry" table-layout="fixed" class="action-table">
        <el-table-column label="Action" min-width="230">
          <template #default="{ row }">
            <div class="action-title">
              <span class="mono">{{ row.action_id }}</span>
              <small>{{ row.label }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Target" min-width="130">
          <template #default="{ row }">{{ row.target_type }}</template>
        </el-table-column>
        <el-table-column label="Gates" min-width="220">
          <template #default="{ row }">{{ recoveryActionGateSummary(row) }}</template>
        </el-table-column>
        <el-table-column label="Risk" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">{{ recoveryActionRiskSummary(row) }}</template>
        </el-table-column>
        <el-table-column label="Status" width="150">
          <template #default="{ row }">
            <el-tag :type="recoveryActionAvailabilityTag(row).type" effect="plain">
              {{ recoveryActionAvailabilityTag(row).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Gap / Route" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <router-link v-if="row.suggested_route" :to="row.suggested_route">{{ recoveryActionGapSummary(row) }}</router-link>
            <span v-else>{{ recoveryActionGapSummary(row) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
// 恢复动作安全注册表（只读）。
import type { UnwrapRef } from "vue";
import { recoveryActionGateSummary, recoveryActionRiskSummary, recoveryActionAvailabilityTag, recoveryActionGapSummary } from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";

const {
  recoveryActionSummary,
  recoveryActions,
} = defineProps<{
  recoveryActionSummary: UnwrapRef<OpsDashboardData["recoveryActionSummary"]>;
  recoveryActions: UnwrapRef<OpsDashboardData["recoveryActions"]>;
}>();
</script>

<style scoped lang="scss">
.action-safety-panel {
  display: grid;
  gap: var(--app-space-4);
}

.dashboard-panel {
  border-color: var(--app-color-border);
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  margin-bottom: var(--app-space-3);
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.action-table {
  width: 100%;
}

.action-title {
  display: grid;
  gap: 3px;
}

.action-title small {
  color: var(--app-color-text-muted);
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
