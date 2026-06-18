<!-- frontend/src/components/JobActions.vue: Shared lifecycle action controls for document jobs. -->
<template>
  <div class="job-actions">
    <el-button size="small" :icon="Refresh" @click="$emit('refresh')">刷新</el-button>
    <el-tooltip
      :disabled="!documentJobActionDisabledReason(job, 'download')"
      :content="documentJobActionDisabledReason(job, 'download')"
      placement="top"
    >
      <span>
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
    </el-tooltip>
    <el-tooltip
      :disabled="!documentJobActionDisabledReason(job, 'retry')"
      :content="documentJobActionDisabledReason(job, 'retry')"
      placement="top"
    >
      <span>
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
    </el-tooltip>
    <el-tooltip
      :disabled="!documentJobActionDisabledReason(job, 'clone')"
      :content="documentJobActionDisabledReason(job, 'clone')"
      placement="top"
    >
      <span>
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
    </el-tooltip>
    <el-tooltip
      :disabled="!documentJobActionDisabledReason(job, 'cancel')"
      :content="documentJobActionDisabledReason(job, 'cancel')"
      placement="top"
    >
      <span>
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
    </el-tooltip>
    <el-tooltip
      :disabled="!documentJobActionDisabledReason(job, 'archive')"
      :content="documentJobActionDisabledReason(job, 'archive')"
      placement="top"
    >
      <span>
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
    </el-tooltip>
    <el-tooltip
      :disabled="!documentJobActionDisabledReason(job, 'unarchive')"
      :content="documentJobActionDisabledReason(job, 'unarchive')"
      placement="top"
    >
      <span>
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
    </el-tooltip>
    <el-tooltip
      v-if="showDeleteAction"
      :disabled="!documentJobActionDisabledReason(job, 'delete')"
      :content="documentJobActionDisabledReason(job, 'delete')"
      placement="top"
    >
      <span>
        <el-button
          size="small"
          type="danger"
          :icon="DeleteIcon"
          :loading="deleteLoading"
          :disabled="!canDeleteDocumentJob(job)"
          @click="$emit('delete', job)"
        >
          删除
        </el-button>
      </span>
    </el-tooltip>
    <small v-if="firstDisabledReason" class="job-actions__reason">
      {{ firstDisabledReason }}
    </small>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { CircleClose, Delete as DeleteIcon, DocumentCopy, Download, FolderChecked, FolderOpened, Refresh, RefreshRight } from "@element-plus/icons-vue";

import type { DocumentJobActionId, DocumentJobResponse } from "@/api/types";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canCloneDocumentJob,
  canDeleteDocumentJob,
  canDownloadDocumentJob,
  canRetryDocumentJob,
  canUnarchiveDocumentJob,
  documentJobActionDisabledReason,
  shouldShowDocumentJobAction,
} from "@/utils/format";

const props = defineProps<{
  job: DocumentJobResponse;
  downloadLoading?: boolean;
  retryLoading?: boolean;
  cloneLoading?: boolean;
  cancelLoading?: boolean;
  archiveLoading?: boolean;
  unarchiveLoading?: boolean;
  deleteLoading?: boolean;
}>();

const actionOrder: DocumentJobActionId[] = ["download", "retry", "clone", "cancel", "archive", "unarchive", "delete"];
const showDeleteAction = computed(() => shouldShowDocumentJobAction(props.job, "delete"));
const firstDisabledReason = computed(() => {
  for (const action of actionOrder) {
    if (!shouldShowDocumentJobAction(props.job, action)) {
      continue;
    }
    const reason = documentJobActionDisabledReason(props.job, action);
    if (reason) {
      return `不可用：${reason}`;
    }
  }
  return "";
});

defineEmits<{
  refresh: [];
  download: [job: DocumentJobResponse];
  retry: [job: DocumentJobResponse];
  clone: [job: DocumentJobResponse];
  cancel: [job: DocumentJobResponse];
  archive: [job: DocumentJobResponse];
  unarchive: [job: DocumentJobResponse];
  delete: [job: DocumentJobResponse];
}>();
</script>

<style scoped lang="scss">
.job-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.job-actions__reason {
  flex-basis: 100%;
  color: #6b7280;
  line-height: 1.4;
}
</style>
