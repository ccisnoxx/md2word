<!-- frontend/src/components/JobProgress.vue: Combined stage label and progress bar for a job. -->
<template>
  <div class="job-progress">
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
  font-size: 12px;
}
</style>
