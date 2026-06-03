<!-- frontend/src/components/JobActions.vue: Shared refresh, download, and retry controls for jobs. -->
<template>
  <div class="job-actions">
    <el-button size="small" :icon="Refresh" @click="$emit('refresh')">刷新</el-button>
    <el-button
      size="small"
      type="primary"
      :icon="Download"
      :loading="downloadLoading"
      :disabled="job.status !== 'succeeded'"
      @click="$emit('download', job)"
    >
      下载
    </el-button>
    <el-button
      size="small"
      type="warning"
      :icon="RefreshRight"
      :loading="retryLoading"
      :disabled="job.status !== 'failed'"
      @click="$emit('retry', job)"
    >
      重试
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { Download, Refresh, RefreshRight } from "@element-plus/icons-vue";

import type { DocumentJobResponse } from "@/api/types";

defineProps<{
  job: DocumentJobResponse;
  downloadLoading?: boolean;
  retryLoading?: boolean;
}>();

defineEmits<{
  refresh: [];
  download: [job: DocumentJobResponse];
  retry: [job: DocumentJobResponse];
}>();
</script>

<style scoped lang="scss">
.job-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
