<!-- frontend/src/components/JobActions.vue: Shared refresh, download, retry, cancel, and archive controls for jobs. -->
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
    <el-button
      size="small"
      type="danger"
      :icon="CircleClose"
      :loading="cancelLoading"
      :disabled="!isCancelableJobStatus(job.status)"
      @click="$emit('cancel', job)"
    >
      取消
    </el-button>
    <el-button
      size="small"
      type="danger"
      :icon="Delete"
      :loading="archiveLoading"
      :disabled="!isArchivableJobStatus(job.status)"
      @click="$emit('archive', job)"
    >
      归档
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { CircleClose, Delete, Download, Refresh, RefreshRight } from "@element-plus/icons-vue";

import type { DocumentJobResponse } from "@/api/types";
import { isArchivableJobStatus, isCancelableJobStatus } from "@/utils/format";

defineProps<{
  job: DocumentJobResponse;
  downloadLoading?: boolean;
  retryLoading?: boolean;
  cancelLoading?: boolean;
  archiveLoading?: boolean;
}>();

defineEmits<{
  refresh: [];
  download: [job: DocumentJobResponse];
  retry: [job: DocumentJobResponse];
  cancel: [job: DocumentJobResponse];
  archive: [job: DocumentJobResponse];
}>();
</script>

<style scoped lang="scss">
.job-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
