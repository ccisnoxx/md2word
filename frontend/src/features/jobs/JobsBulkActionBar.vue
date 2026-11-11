<template>
  <div class="bulk-action-bar app-bulk-action-bar" aria-label="批量操作">
    <div class="bulk-summary app-bulk-summary">
      <strong>已选 {{ selectedCount }} 个任务</strong>
      <span>可重试 {{ selectedRetryableJobs.length }} · 可取消 {{ selectedCancelableJobs.length }} · 可归档 {{ selectedArchivableJobs.length }}</span>
    </div>
    <div class="bulk-actions app-bulk-actions">
      <el-button :disabled="!selectedRetryableJobs.length" :loading="batchLoading" @click="handleBatchRetry">
        批量重试
      </el-button>
      <el-button :disabled="!selectedCancelableJobs.length" :loading="batchLoading" @click="handleBatchCancel">
        批量取消
      </el-button>
      <el-button :disabled="!selectedArchivableJobs.length" :loading="batchLoading" @click="handleBatchArchive">
        批量归档
      </el-button>
      <el-button text @click="clearSelection">清除选择</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { UnwrapRef } from "vue";
import type { JobsActions } from "./useJobsActions";

const {
  selectedCount,
  selectedRetryableJobs,
  selectedCancelableJobs,
  selectedArchivableJobs,
  batchLoading,
  handleBatchRetry,
  handleBatchCancel,
  handleBatchArchive,
  clearSelection,
} = defineProps<{
  selectedCount: number;
  selectedRetryableJobs: UnwrapRef<JobsActions["selectedRetryableJobs"]>;
  selectedCancelableJobs: UnwrapRef<JobsActions["selectedCancelableJobs"]>;
  selectedArchivableJobs: UnwrapRef<JobsActions["selectedArchivableJobs"]>;
  batchLoading: UnwrapRef<JobsActions["batchLoading"]>;
  handleBatchRetry: JobsActions["handleBatchRetry"];
  handleBatchCancel: JobsActions["handleBatchCancel"];
  handleBatchArchive: JobsActions["handleBatchArchive"];
  clearSelection: () => void;
}>();
</script>

<style scoped lang="scss">
.bulk-action-bar {
  position: fixed;
  right: max(16px, calc((100vw - var(--app-content-wide)) / 2 + 24px));
  bottom: 16px;
  left: max(16px, calc((100vw - var(--app-content-wide)) / 2 + 24px));
  z-index: 35;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-4);
  padding: var(--app-space-3) var(--app-space-4);
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-elevated);
  box-shadow: var(--app-shadow-panel);
  backdrop-filter: var(--app-backdrop-panel);
  -webkit-backdrop-filter: var(--app-backdrop-panel);
}

.bulk-summary {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.bulk-summary strong {
  color: var(--app-color-text);
  font-size: 14px;
}

.bulk-summary span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.bulk-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

@media (prefers-color-scheme: dark) {
  .bulk-action-bar {
    border-color: var(--app-color-primary-border);
    background: var(--app-color-surface-elevated);
    color: var(--app-color-primary-hover);
  }
}

@media (max-width: 760px) {
  .bulk-action-bar {
    right: 12px;
    bottom: 12px;
    left: 12px;
    align-items: stretch;
    flex-direction: column;
  }

  .bulk-actions {
    justify-content: flex-start;
  }
}
</style>
