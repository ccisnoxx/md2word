<!-- frontend/src/components/JobProgress.vue: Combined stage label and progress bar for a job. -->
<template>
  <div class="job-progress" :class="progressClass">
    <div class="progress-label">
      <span>{{ stageText }}</span>
      <span class="muted">{{ normalizedProgress }}%</span>
    </div>
    <el-progress
      :percentage="normalizedProgress"
      :status="progressStatus"
      :stroke-width="8"
      :show-text="false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type { DocumentJobStage, DocumentJobStatus } from "@/api/types";
import { jobStageText } from "@/utils/format";

const props = defineProps<{
  status: DocumentJobStatus | string;
  stage: DocumentJobStage | string;
  progress: number;
}>();

const normalizedProgress = computed(() => Math.min(100, Math.max(0, props.progress || 0)));
const stageText = computed(() => jobStageText[props.stage as DocumentJobStage] || props.stage);
const progressClass = computed(() => `is-${String(props.status)}`);
const progressStatus = computed(() => {
  if (props.status === "succeeded") {
    return "success";
  }
  if (props.status === "failed") {
    return "exception";
  }
  return undefined;
});
</script>

<style scoped lang="scss">
.job-progress {
  min-width: 150px;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.job-progress :deep(.el-progress-bar__outer) {
  background-color: var(--app-color-surface-muted);
}

.job-progress :deep(.el-progress-bar__inner) {
  background-color: var(--app-color-primary);
  transition: width 180ms ease-out;
}

.job-progress.is-succeeded :deep(.el-progress-bar__inner) {
  background-color: var(--app-color-success);
}

.job-progress.is-failed :deep(.el-progress-bar__inner) {
  background-color: var(--app-color-danger);
}

.job-progress.is-running :deep(.el-progress-bar__inner),
.job-progress.is-pending :deep(.el-progress-bar__inner),
.job-progress.is-queued :deep(.el-progress-bar__inner) {
  background-color: var(--app-color-warning);
}
</style>
