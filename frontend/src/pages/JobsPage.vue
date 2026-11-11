<!-- 文件：frontend/src/pages/JobsPage.vue -->
<!-- 用途：展示带筛选和批量动作的文档任务工作台；数据与动作由 features/jobs 的 composable 持有。 -->
<template>
  <main class="jobs-page app-page" :class="{ 'has-bulk-actions': selectedJobs.length }" aria-labelledby="jobs-title">
    <JobsCommandHeader
      v-bind="{
        loading, syncStatusText, lastRefreshedAt, lastRefreshedLabel, canCreateJob, createDisabledReason,
        goCreateJob, loadJobs,
      }"
    />

    <JobsWorkQueueStrip
      v-bind="{
        filteredSummary, translationQaSummary, statusFilter, statusGroupFilter, sortFilter, qaStatusFilter,
        applyWorkQueueFilter,
      }"
      :stale-count="staleVisibleJobs.length"
    />

    <SavedViewStrip
      class="app-page-shell app-page-shell--wide"
      :system-views="jobsSystemSavedViews"
      :personal-views="personalSavedViewItems"
      :active-view-id="activeSavedView"
      :loading="savedViewsLoading"
      @apply="applySavedView"
      @save-current="saveCurrentSavedView"
      @update="updateSavedViewFromCurrent"
      @rename="renameSavedView"
      @delete="deleteSavedView"
      @set-default="setDefaultSavedView"
      @move="moveSavedView"
    />

    <JobsListPanel
      ref="listPanelRef"
      v-model:last-download-link="lastDownloadLink"
      v-model:batch-result-expanded="batchResultExpanded"
      v-bind="{
        activeFilterLabel, statusFilter, statusGroupFilter, includeArchived, activeFilterChips, error,
        jobsErrorDiagnosticContext, staleVisibleJobs, failedVisibleJobs, returnQueryForDetail,
        normalizedBatchResult, summaryEntries, showEmptyState, hasActiveFilters, canCreateJob, jobs, loading,
        page, pageSize, total, actionPending, tablePreferences, applyQuickFilter, removeFilter, clearAllFilters,
        goCreateJob, clearBatchResult, copyLastDownloadLink, handlePageChange, handleSelectionChange,
        handleDownload, handleRetry, handleClone, handleCancel, handleArchive, handleUnarchive, handleDelete,
      }"
    >
      <template #toolbar>
        <JobsFilterToolbar
          v-model:search-keyword="searchKeyword"
          v-model:status-filter="statusFilter"
          v-model:qa-status-filter="qaStatusFilter"
          v-model:sort-filter="sortFilter"
          v-model:created-range="createdRange"
          v-model:include-archived="includeArchived"
          v-bind="{
            loading, advancedFilterCount, tablePreferences, jobsTableColumns, handleFilter,
            handleStatusFilterChange, resetAdvancedFilters, handleTablePreferencesUpdate,
            handleTablePreferencesReset,
          }"
        />
      </template>
    </JobsListPanel>

    <JobsBulkActionBar
      v-if="selectedJobs.length"
      v-bind="{
        selectedRetryableJobs, selectedCancelableJobs, selectedArchivableJobs, batchLoading, handleBatchRetry,
        handleBatchCancel, handleBatchArchive, clearSelection,
      }"
      :selected-count="selectedJobs.length"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import SavedViewStrip from "@/components/SavedViewStrip.vue";
import JobsBulkActionBar from "@/features/jobs/JobsBulkActionBar.vue";
import JobsCommandHeader from "@/features/jobs/JobsCommandHeader.vue";
import JobsFilterToolbar from "@/features/jobs/JobsFilterToolbar.vue";
import JobsListPanel from "@/features/jobs/JobsListPanel.vue";
import JobsWorkQueueStrip from "@/features/jobs/JobsWorkQueueStrip.vue";
import { useJobsActions } from "@/features/jobs/useJobsActions";
import { useJobsList } from "@/features/jobs/useJobsList";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();
const list = useJobsList(useRoute(), router, { onResultReset: () => actions.clearBatchResult() });
const actions = useJobsActions(list, router);
const {
  jobs,
  loading,
  error,
  page,
  pageSize,
  total,
  jobsTableColumns,
  tablePreferences,
  statusFilter,
  statusGroupFilter,
  qaStatusFilter,
  searchKeyword,
  sortFilter,
  includeArchived,
  createdRange,
  selectedJobs,
  filteredSummary,
  translationQaSummary,
  lastRefreshedAt,
  jobsErrorDiagnosticContext,
  summaryEntries,
  hasActiveFilters,
  showEmptyState,
  advancedFilterCount,
  activeFilterLabel,
  activeFilterChips,
  returnQueryForDetail,
  failedVisibleJobs,
  staleVisibleJobs,
  syncStatusText,
  lastRefreshedLabel,
  jobsSystemSavedViews,
  personalSavedViewItems,
  activeSavedView,
  savedViewsLoading,
  loadJobs,
  applySavedView,
  saveCurrentSavedView,
  updateSavedViewFromCurrent,
  renameSavedView,
  deleteSavedView,
  setDefaultSavedView,
  moveSavedView,
  handlePageChange,
  handleTablePreferencesUpdate,
  handleTablePreferencesReset,
  handleFilter,
  handleStatusFilterChange,
  handleSelectionChange,
  applyQuickFilter,
  applyWorkQueueFilter,
  resetAdvancedFilters,
  clearAllFilters,
  removeFilter,
} = list;
const {
  batchLoading,
  batchResultExpanded,
  lastDownloadLink,
  actionPending,
  selectedRetryableJobs,
  selectedCancelableJobs,
  selectedArchivableJobs,
  normalizedBatchResult,
  clearBatchResult,
  copyLastDownloadLink,
  handleDownload,
  handleRetry,
  handleClone,
  handleCancel,
  handleArchive,
  handleUnarchive,
  handleDelete,
  handleBatchRetry,
  handleBatchArchive,
  handleBatchCancel,
} = actions;
const listPanelRef = ref<InstanceType<typeof JobsListPanel> | null>(null);
const canCreateJob = computed(() => auth.hasPermission("document_jobs:create"));
const createDisabledReason = computed(() => (canCreateJob.value ? "" : "当前账号没有创建 document job 的权限。"));

function goCreateJob(): void {
  void router.push("/jobs/new");
}

function clearSelection(): void {
  selectedJobs.value = [];
  listPanelRef.value?.clearSelection();
}
</script>

<style scoped lang="scss">
.jobs-page {
  position: relative;
  isolation: isolate;
  margin: -20px -24px -36px;
  padding: 28px 24px 42px;
  overflow: visible;
  color: var(--app-color-text);
  background: transparent;
  color-scheme: var(--app-color-scheme);
}

.jobs-page::before {
  position: absolute;
  inset: 0 0 auto 0;
  z-index: 0;
  height: 340px;
  content: "";
  background:
    linear-gradient(100deg, color-mix(in srgb, var(--app-color-primary) 24%, transparent), transparent 60%),
    linear-gradient(180deg, color-mix(in srgb, var(--app-color-accent-cyan) 16%, transparent), transparent 74%),
    linear-gradient(90deg, transparent, color-mix(in srgb, var(--app-color-accent-emerald) 14%, transparent), transparent);
  pointer-events: none;
}

.jobs-page::after {
  position: absolute;
  inset: 18px 24px auto;
  z-index: 0;
  height: 180px;
  content: "";
  background-image:
    linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px);
  background-size: 30px 30px;
  mask-image: linear-gradient(90deg, transparent, #000 18%, #000 74%, transparent);
  opacity: 0.95;
  pointer-events: none;
}

.table-kicker {
  margin-bottom: 10px;
}

.jobs-page :deep(.el-button) {
  border-radius: var(--app-radius-md);
}

.jobs-page :deep(.el-button--primary) {
  border: 1px solid var(--app-color-primary);
  background: var(--app-gradient-action);
  box-shadow: 0 8px 18px color-mix(in srgb, var(--app-color-primary) 18%, transparent);
}

.jobs-page :deep(.el-select__wrapper),
.jobs-page :deep(.el-input__wrapper) {
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: 0 0 0 1px var(--app-color-border) inset;
}

.jobs-page :deep(.el-select__placeholder),
.jobs-page :deep(.el-select__selected-item),
.jobs-page :deep(.el-input__inner) {
  color: var(--app-color-text);
}

.jobs-page :deep(.el-tag) {
  border-color: var(--app-color-border);
  border-radius: 999px;
  background: var(--app-color-surface);
}

.jobs-page {
  margin: -20px -24px -36px;
  padding: 20px 24px 42px;
  background: transparent;
  animation: none;
  transform: none;
}

.jobs-page.has-bulk-actions {
  padding-bottom: 124px;
}

.jobs-page::before,
.jobs-page::after {
  display: none;
}

.saved-view-strip {
  position: relative;
  z-index: 1;
}

.saved-view-strip {
  margin-top: var(--app-space-2);
}

@media (prefers-color-scheme: dark) {
  .jobs-page {
    background: var(--app-color-bg);
    color-scheme: var(--app-color-scheme);
  }

  .jobs-page :deep(.el-tag) {
    background: var(--app-color-surface-muted);
  }
}

@media (max-width: 980px) {
  .jobs-page {
    margin: -16px -16px -36px;
    padding: 24px 16px 36px;
  }
}

@media (max-width: 760px) {
  .jobs-page {
    margin: -16px -16px -36px;
    padding: 18px 12px 30px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .jobs-page :deep(.el-button) {
    transition: none;
  }
}
</style>
