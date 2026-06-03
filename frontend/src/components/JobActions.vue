<!-- frontend/src/components/JobActions.vue: Shared lifecycle action controls for document jobs. -->
<template>
  <div class="job-actions">
    <el-button size="small" :icon="Refresh" @click="$emit('refresh')">刷新</el-button>
    <el-button
      size="small"
      type="primary"
      :icon="Download"
      :loading="downloadLoading"
      :disabled="!canDownloadDocumentJob(job)"
      @click="$emit('download', job)"
    >
      下载
    </el-button>
    <el-button
      size="small"
      type="warning"
      :icon="RefreshRight"
      :loading="retryLoading"
      :disabled="!canRetryDocumentJob(job)"
      @click="$emit('retry', job)"
    >
      重试
    </el-button>
    <el-button
      size="small"
      type="danger"
      :icon="CircleClose"
      :loading="cancelLoading"
      :disabled="!canCancelDocumentJob(job)"
      @click="$emit('cancel', job)"
    >
      取消
    </el-button>
    <el-button
      size="small"
      :icon="FolderChecked"
      :loading="archiveLoading"
      :disabled="!canArchiveDocumentJob(job)"
      @click="$emit('archive', job)"
    >
      归档
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { CircleClose, Download, FolderChecked, Refresh, RefreshRight } from "@element-plus/icons-vue";

import type { DocumentJobResponse } from "@/api/types";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canDownloadDocumentJob,
  canRetryDocumentJob,
} from "@/utils/format";

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
