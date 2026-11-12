<template>
  <div class="bulk-action-bar app-bulk-action-bar" aria-label="批量异常操作">
    <div class="bulk-summary app-bulk-summary">
      <strong>已选 {{ selectedCount }} 个异常</strong>
      <span>可重试 {{ selectedRetryableCount }} · 将跳过 {{ selectedNonRetryableCount }}</span>
    </div>
    <div class="bulk-actions app-bulk-actions">
      <el-button type="warning" :loading="batchLoading" @click="handleBatchRetry">批量重试</el-button>
      <el-button :loading="batchLoading" @click="handleBatchRefresh">批量刷新</el-button>
      <el-button text @click="clearSelection">清除选择</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { UnwrapRef } from "vue";
import type { IncidentActions } from "./useIncidentActions";

const {
  selectedCount,
  selectedRetryableCount,
  selectedNonRetryableCount,
  batchLoading,
  handleBatchRetry,
  handleBatchRefresh,
  clearSelection,
} = defineProps<{
  selectedCount: number;
  selectedRetryableCount: UnwrapRef<IncidentActions["selectedRetryableCount"]>;
  selectedNonRetryableCount: UnwrapRef<IncidentActions["selectedNonRetryableCount"]>;
  batchLoading: UnwrapRef<IncidentActions["batchLoading"]>;
  handleBatchRetry: IncidentActions["handleBatchRetry"];
  handleBatchRefresh: IncidentActions["handleBatchRefresh"];
  clearSelection: () => void;
}>();
</script>

<style scoped lang="scss">
.bulk-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
}

.bulk-action-bar {
  position: fixed;
  right: 24px;
  bottom: 20px;
  left: calc(var(--app-sidebar-width, 260px) + 24px);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-3);
  padding: 12px 14px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-lg);
}

.bulk-summary {
  display: grid;
  gap: 3px;
}

.bulk-summary span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

@media (max-width: 900px) {
  .bulk-action-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .bulk-action-bar {
    right: 12px;
    left: 12px;
    bottom: 12px;
  }
}
</style>
