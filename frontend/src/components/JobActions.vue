<!-- frontend/src/components/JobActions.vue: Shared lifecycle action controls for document jobs. -->
<template>
  <div class="job-actions">
    <el-button size="small" :icon="Refresh" @click="$emit('refresh')">刷新</el-button>
    <span :title="documentJobActionDisabledReason(job, 'download')">
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
    </span>
    <span :title="documentJobActionDisabledReason(job, 'retry')">
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
    </span>
    <span :title="documentJobActionDisabledReason(job, 'clone')">
      <el-button
        size="small"
        :icon="DocumentCopy"
        :loading="cloneLoading"
        :disabled="!canCloneDocumentJob(job)"
        @click="$emit('clone', job)"
      >
        重新发起
      </el-button>
    </span>
    <span :title="documentJobActionDisabledReason(job, 'cancel')">
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
    </span>
    <span :title="documentJobActionDisabledReason(job, 'archive')">
      <el-button
        size="small"
        :icon="FolderChecked"
        :loading="archiveLoading"
        :disabled="!canArchiveDocumentJob(job)"
        @click="$emit('archive', job)"
      >
        归档
      </el-button>
    </span>
    <span :title="documentJobActionDisabledReason(job, 'unarchive')">
      <el-button
        size="small"
        :icon="FolderOpened"
        :loading="unarchiveLoading"
        :disabled="!canUnarchiveDocumentJob(job)"
        @click="$emit('unarchive', job)"
      >
        取消归档
      </el-button>
    </span>
  </div>
</template>

<script setup lang="ts">
import { CircleClose, DocumentCopy, Download, FolderChecked, FolderOpened, Refresh, RefreshRight } from "@element-plus/icons-vue";

import type { DocumentJobResponse } from "@/api/types";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canCloneDocumentJob,
  canDownloadDocumentJob,
  canRetryDocumentJob,
  canUnarchiveDocumentJob,
  documentJobActionDisabledReason,
} from "@/utils/format";

defineProps<{
  job: DocumentJobResponse;
  downloadLoading?: boolean;
  retryLoading?: boolean;
  cloneLoading?: boolean;
  cancelLoading?: boolean;
  archiveLoading?: boolean;
  unarchiveLoading?: boolean;
}>();

defineEmits<{
  refresh: [];
  download: [job: DocumentJobResponse];
  retry: [job: DocumentJobResponse];
  clone: [job: DocumentJobResponse];
  cancel: [job: DocumentJobResponse];
  archive: [job: DocumentJobResponse];
  unarchive: [job: DocumentJobResponse];
}>();
</script>

<style scoped lang="scss">
.job-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
