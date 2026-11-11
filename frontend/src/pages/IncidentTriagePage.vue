<!-- 文件：frontend/src/pages/IncidentTriagePage.vue -->
<!-- 用途：展示轻量 document_job 异常分诊队列和诊断抽屉；队列、诊断与处置分别由 features/incidents 的 composable 持有。 -->
<template>
  <main class="incident-page app-page" :class="{ 'has-bulk-actions': selectedItems.length }" aria-labelledby="incident-title">
    <IncidentCommandHeader v-bind="{ loading, backgroundRefreshing, syncStatusText, lastRefreshedAt, manualRefresh }" />

    <WorkbenchSummaryStrip
      label="异常队列汇总"
      :items="incidentSummaryItems"
      wide
      section-class="incident-summary-strip"
      @select="handleIncidentSummarySelect"
    />

    <SavedViewStrip
      class="app-page-shell app-page-shell--wide"
      :system-views="incidentSystemSavedViews"
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

    <IncidentQueuePanel
      ref="queuePanelRef"
      v-model:batch-result-expanded="batchResultExpanded"
      v-bind="{
        activeFilterLabel, activeFilterChips, error, incidentErrorDiagnosticContext, normalizedBatchResult,
        failedBatchItems, loading, items, tablePreferences, hasActiveFilters, actionPending, page, pageSize, total,
        removeFilter, clearBatchResult, manualRefresh, reselectFailedItems, incidentRowClassName,
        handleSelectionChange, openDiagnostic, clearIncidentFilters, isTableColumnVisible, isActionBusy,
        handleSingleRetry, openJobDetail, handlePageChange,
      }"
    >
      <template #toolbar>
        <IncidentFilterToolbar
          v-model:search-keyword="searchKeyword"
          v-model:status-filter="statusFilter"
          v-model:stage-filter="stageFilter"
          v-model:failure-type-filter="failureTypeFilter"
          v-model:retryable-filter="retryableFilter"
          v-model:retry-count-filter="retryCountFilter"
          v-model:stalled-minutes-filter="stalledMinutesFilter"
          v-model:sort-filter="sortFilter"
          v-bind="{
            loading, advancedFilterCount, tablePreferences, incidentTableColumns, handleFilter, resetAdvancedFilters,
            handleTablePreferencesUpdate, handleTablePreferencesReset,
          }"
        />
      </template>
    </IncidentQueuePanel>

    <IncidentBulkActionBar
      v-if="selectedItems.length"
      v-bind="{
        selectedRetryableCount, selectedNonRetryableCount, batchLoading, handleBatchRetry, handleBatchRefresh,
        clearSelection,
      }"
      :selected-count="selectedItems.length"
    />

    <IncidentDiagnosticDrawer
      v-bind="{
        drawerVisible, drawerSize, drawerLoading, drawerError, diagnostic, diagnosticTitle, selectedIncidentJobId,
        drawerErrorDiagnosticContext, incidentDiagnosticGuidance, incidentKeyEvidenceItems, actionPending,
        handleDrawerModelValue, closeDiagnostic, refreshDiagnostic, openSelectedJobDetail, openJobDetail,
        handleSingleRetry,
      }"
    />
  </main>
</template>

<script setup lang="ts">
import { nextTick, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import SavedViewStrip from "@/components/SavedViewStrip.vue";
import WorkbenchSummaryStrip from "@/components/WorkbenchSummaryStrip.vue";
import IncidentBulkActionBar from "@/features/incidents/IncidentBulkActionBar.vue";
import IncidentCommandHeader from "@/features/incidents/IncidentCommandHeader.vue";
import IncidentDiagnosticDrawer from "@/features/incidents/IncidentDiagnosticDrawer.vue";
import IncidentFilterToolbar from "@/features/incidents/IncidentFilterToolbar.vue";
import IncidentQueuePanel from "@/features/incidents/IncidentQueuePanel.vue";
import { useIncidentActions } from "@/features/incidents/useIncidentActions";
import { useIncidentDiagnostic } from "@/features/incidents/useIncidentDiagnostic";
import { useIncidentQueue } from "@/features/incidents/useIncidentQueue";
import { useIncidentShortcuts } from "@/features/incidents/useIncidentShortcuts";

const route = useRoute();
const router = useRouter();
const queuePanelRef = ref<InstanceType<typeof IncidentQueuePanel> | null>(null);
const queue = useIncidentQueue(route, router, {
  selectedIncidentJobId: () => diagnosticOwner.selectedIncidentJobId.value,
  onRouteDiagnosticSync: () => diagnosticOwner.syncDiagnosticFromRoute(),
  onResultReset: () => actions.clearBatchResult(),
  canAutoRefresh: () => !diagnosticOwner.drawerVisible.value && !actions.batchLoading.value,
  onTableLayout: () => void nextTick(() => queuePanelRef.value?.doLayout()),
});
const diagnosticOwner = useIncidentDiagnostic(route, router, {
  items: queue.items,
  replaceIncidentJobQuery: queue.replaceIncidentJobQuery,
});
const actions = useIncidentActions(queue, diagnosticOwner, {
  clearSelection,
  toggleRowSelection: (item, selected) => queuePanelRef.value?.toggleRowSelection(item, selected),
});
const { manualRefresh } = useIncidentShortcuts(queue, diagnosticOwner, actions);
const {
  items,
  loading,
  backgroundRefreshing,
  error,
  page,
  pageSize,
  total,
  incidentTableColumns,
  tablePreferences,
  statusFilter,
  stageFilter,
  failureTypeFilter,
  retryableFilter,
  retryCountFilter,
  stalledMinutesFilter,
  searchKeyword,
  sortFilter,
  selectedItems,
  lastRefreshedAt,
  incidentErrorDiagnosticContext,
  syncStatusText,
  activeFilterLabel,
  hasActiveFilters,
  advancedFilterCount,
  activeFilterChips,
  incidentSummaryItems,
  incidentSystemSavedViews,
  personalSavedViewItems,
  activeSavedView,
  savedViewsLoading,
  applySavedView,
  saveCurrentSavedView,
  updateSavedViewFromCurrent,
  renameSavedView,
  deleteSavedView,
  setDefaultSavedView,
  moveSavedView,
  handleFilter,
  handlePageChange,
  isTableColumnVisible,
  handleTablePreferencesUpdate,
  handleTablePreferencesReset,
  handleIncidentSummarySelect,
  resetAdvancedFilters,
  clearIncidentFilters,
  removeFilter,
  handleSelectionChange,
} = queue;
const {
  selectedIncidentJobId,
  drawerVisible,
  drawerLoading,
  drawerError,
  diagnostic,
  drawerSize,
  drawerErrorDiagnosticContext,
  diagnosticTitle,
  incidentDiagnosticGuidance,
  incidentKeyEvidenceItems,
  incidentRowClassName,
  openDiagnostic,
  refreshDiagnostic,
  closeDiagnostic,
  handleDrawerModelValue,
  openJobDetail,
  openSelectedJobDetail,
} = diagnosticOwner;
const {
  batchLoading,
  batchResultExpanded,
  actionPending,
  selectedRetryableCount,
  selectedNonRetryableCount,
  failedBatchItems,
  normalizedBatchResult,
  clearBatchResult,
  isActionBusy,
  handleSingleRetry,
  handleBatchRetry,
  handleBatchRefresh,
  reselectFailedItems,
} = actions;

function clearSelection(): void {
  selectedItems.value = [];
  queuePanelRef.value?.clearSelection();
}
</script>

<style scoped lang="scss">
.incident-page {
  position: relative;
  isolation: isolate;
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-4);
  margin: -20px -24px -36px;
  padding: 28px 24px 42px;
  overflow: visible;
  color: var(--app-color-text);
  background: transparent;
}

.incident-summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.summary-item {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-areas:
    "count label"
    "count helper";
  gap: 2px 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.summary-item span {
  grid-area: count;
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}

.summary-item strong {
  grid-area: label;
}

.summary-item small {
  grid-area: helper;
  color: var(--app-color-text-muted);
}

.summary-item.is-active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 1px var(--el-color-primary-light-5);
}

:global(.incident-table .is-active-incident-row > td) {
  background: var(--el-color-primary-light-9) !important;
}

:global(.incident-diagnostic-drawer.el-drawer) {
  max-width: 100vw;
}

:global(.incident-diagnostic-drawer .el-drawer__body) {
  padding: 0;
}

@media (max-width: 900px) {
  .incident-page {
    margin: -16px -16px -28px;
    padding: 20px 16px 88px;
  }

  .incident-summary-strip {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 520px) {
  .incident-summary-strip {
    grid-template-columns: 1fr;
  }
}
</style>
