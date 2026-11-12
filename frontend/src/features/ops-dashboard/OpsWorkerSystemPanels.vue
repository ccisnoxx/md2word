<template>
  <section class="dashboard-panels app-page-shell app-page-shell--wide" aria-label="worker 和系统详情">
    <el-card class="card-flat dashboard-panel app-panel-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Worker / Queue</h2>
          <p class="section-subtitle">来自 health readiness 和 metrics 的 stage message 与 callback message 观察值。</p>
        </div>
        <router-link to="/system-status">系统状态</router-link>
      </div>
      <div class="metric-table app-key-value-list">
        <div v-for="item in queueMetricItems" :key="item.label" class="metric-row app-key-value-row">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </el-card>

    <el-card class="card-flat dashboard-panel app-panel-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Runtime</h2>
          <p class="section-subtitle">metadata、artifact storage 和 readiness 关键字段。</p>
        </div>
      </div>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-for="item in runtimeItems" :key="item.label" :label="item.label">
          <span class="mono">{{ item.value }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="card-flat dashboard-panel app-panel-card" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Resources</h2>
          <p class="section-subtitle">默认资源版本和版本数量。</p>
        </div>
      </div>
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-for="item in resourceItems" :key="item.label" :label="item.label">
          <span class="mono">{{ item.value }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </section>
</template>

<script setup lang="ts">
// worker 与系统详情。
import type { UnwrapRef } from "vue";
import type { OpsHealthView } from "./useOpsHealthView";

const {
  queueMetricItems,
  runtimeItems,
  resourceItems,
} = defineProps<{
  queueMetricItems: UnwrapRef<OpsHealthView["queueMetricItems"]>;
  runtimeItems: UnwrapRef<OpsHealthView["runtimeItems"]>;
  resourceItems: UnwrapRef<OpsHealthView["resourceItems"]>;
}>();
</script>

<style scoped lang="scss">
.dashboard-panels {
  display: grid;
  gap: var(--app-space-4);
}

.dashboard-panels {
  grid-template-columns: repeat(3, minmax(0, 1fr));
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

.metric-table {
  min-width: 0;
}

.mono {
  font-family: var(--app-font-mono);
  font-size: 12px;
}

@media (max-width: 1100px) {
  .dashboard-panels {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .dashboard-panels {
    grid-template-columns: 1fr;
  }
}
</style>
