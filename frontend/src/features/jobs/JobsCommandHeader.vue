<template>
  <WorkbenchPageHeader
    title-id="jobs-title"
    kicker="任务工作台"
    title="任务列表"
    description="按异常、停滞、待 QA 和阻塞状态优先处理 document_jobs。"
    wide
    section-class="jobs-command-header"
  >
    <template #actions>
      <div class="live-pill" :class="{ 'is-loading': loading }">
        <span aria-hidden="true"></span>
        <strong>{{ syncStatusText }}</strong>
        <small v-if="lastRefreshedAt">{{ lastRefreshedLabel }}</small>
      </div>
      <span :title="createDisabledReason">
        <el-button
          type="primary"
          :icon="Plus"
          :disabled="!canCreateJob"
          @click="goCreateJob"
        >
          创建任务
        </el-button>
      </span>
      <el-button :icon="Refresh" :loading="loading" @click="() => loadJobs()">刷新</el-button>
    </template>
  </WorkbenchPageHeader>
</template>

<script setup lang="ts">
import type { UnwrapRef } from "vue";
import { Plus, Refresh } from "@element-plus/icons-vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import type { JobsList } from "./useJobsList";

const {
  loading,
  syncStatusText,
  lastRefreshedAt,
  lastRefreshedLabel,
  canCreateJob,
  createDisabledReason,
  goCreateJob,
  loadJobs,
} = defineProps<{
  loading: UnwrapRef<JobsList["loading"]>;
  syncStatusText: UnwrapRef<JobsList["syncStatusText"]>;
  lastRefreshedAt: UnwrapRef<JobsList["lastRefreshedAt"]>;
  lastRefreshedLabel: UnwrapRef<JobsList["lastRefreshedLabel"]>;
  canCreateJob: boolean;
  createDisabledReason: string;
  goCreateJob: () => void;
  loadJobs: JobsList["loadJobs"];
}>();
</script>

<style scoped lang="scss">
.live-pill {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: var(--app-radius-md);
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
  font-size: 13px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.24);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.live-pill small {
  flex-basis: 100%;
  color: rgba(255, 255, 255, 0.72);
  font-size: 11px;
}

.live-pill span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 4px var(--app-color-success-soft);
}

.live-pill.is-loading span {
  color: var(--app-color-primary);
  animation: app-status-pulse var(--app-motion-slow) ease-out infinite alternate;
}

.jobs-command-header {
  position: relative;
  z-index: 1;
}

.jobs-command-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--app-space-4);
  align-items: center;
  padding: var(--app-space-4) var(--app-space-5);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-elevated);
  box-shadow: var(--app-shadow-subtle);
}

.command-copy {
  min-width: 0;
}

.command-copy .page-title {
  font-size: 24px;
}

.command-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.jobs-command-header .live-pill {
  min-height: 34px;
  border-color: var(--app-color-border);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text);
  box-shadow: none;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.jobs-command-header .live-pill small {
  flex-basis: auto;
  color: var(--app-color-text-muted);
}

@media (max-width: 760px) {
  .jobs-command-header {
    grid-template-columns: 1fr;
  }

  .command-actions {
    justify-content: flex-start;
  }
}
</style>
