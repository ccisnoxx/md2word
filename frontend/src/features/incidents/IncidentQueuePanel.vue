<template>
  <section class="incident-list-panel app-filter-panel app-page-shell app-page-shell--wide" aria-label="异常队列">
    <WorkbenchSectionHeader
      :kicker="`当前视图：${activeFilterLabel}`"
      title="异常队列"
      subtitle="默认按处理优先级排序；抽屉状态通过 incident_job_id 恢复。"
      header-class="table-header"
    >
      <template #extra>
        <ShortcutHintList :items="incidentListShortcutHints" />
      </template>
    </WorkbenchSectionHeader>

    <slot name="toolbar" />

    <div v-if="activeFilterChips.length" class="active-filter-chips app-active-filter-chips" aria-label="当前筛选条件">
      <el-tag v-for="chip in activeFilterChips" :key="chip.key" closable effect="plain" @close="removeFilter(chip.key)">
        {{ chip.label }}
      </el-tag>
    </div>

    <ApiErrorAlert :error="error" :diagnostic-context="incidentErrorDiagnosticContext" />

    <BatchResultStrip
      v-if="normalizedBatchResult"
      v-model:expanded="batchResultExpanded"
      :result="normalizedBatchResult"
      @close="clearBatchResult"
    >
      <template #actions>
        <el-button size="small" text :icon="Refresh" @click="manualRefresh">刷新队列</el-button>
        <el-button size="small" text :disabled="!failedBatchItems.length" @click="reselectFailedItems">重选失败/跳过</el-button>
      </template>
    </BatchResultStrip>

    <div class="incident-table-wrap app-scrollbar-persistent">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="items"
        border
        :class="['incident-table', `is-${tablePreferences.density}-density`]"
        empty-text="当前筛选下暂无异常"
        table-layout="fixed"
        :row-class-name="incidentRowClassName"
        @selection-change="handleSelectionChange"
        @row-click="openDiagnostic"
      >
        <template #empty>
          <WorkbenchEmptyState
            :title="incidentEmptyStateTitle"
            :description="incidentEmptyStateDescription"
          >
            <template #actions>
              <el-button v-if="hasActiveFilters" :icon="Filter" @click="clearIncidentFilters">清空筛选</el-button>
              <el-button :icon="Refresh" @click="manualRefresh">刷新队列</el-button>
            </template>
          </WorkbenchEmptyState>
        </template>
        <el-table-column v-if="isTableColumnVisible('selection')" type="selection" width="44" />
        <el-table-column v-if="isTableColumnVisible('identity')" label="任务 / 证据" min-width="360">
          <template #default="{ row }">
            <div class="incident-main">
              <button type="button" class="job-title-button" @click.stop="openDiagnostic(row)">
                {{ getJobSourceFilename(row.job) }}
              </button>
              <div class="job-meta">
                <RouterLink class="mono job-id" :to="`/jobs/${row.job.id}`" @click.stop>{{ row.job.id }}</RouterLink>
                <el-tag size="small" effect="plain">{{ incidentPriorityLabel(row) }}</el-tag>
                <el-tag size="small" :type="failureTypeTagType(row)" effect="plain">
                  {{ failureTypeLabel(row) }}
                </el-tag>
              </div>
              <div class="evidence-line">
                <span>{{ row.suggested_action }}</span>
                <small v-if="row.evidence_summary.length">{{ row.evidence_summary[0] }}</small>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="isTableColumnVisible('status')" label="状态" width="150">
          <template #default="{ row }">
            <div class="status-cell">
              <JobStatusBadge :status="row.job.status" />
              <span>{{ stageLabel(row) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="isTableColumnVisible('retry')" label="重试" width="150">
          <template #default="{ row }">
            <div class="retry-cell">
              <el-tag size="small" :type="row.retryable ? 'success' : 'info'" effect="plain">
                {{ row.retryable ? "可重试" : "不可重试" }}
              </el-tag>
              <span>次数 {{ row.job.retry_count }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="isTableColumnVisible('updated')" label="更新" width="172">
          <template #default="{ row }">
            <div class="time-cell">
              <span>{{ formatDateTime(row.job.updated_at) }}</span>
              <small v-if="row.stalled_minutes !== null">停滞 {{ row.stalled_minutes }} 分钟</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="isTableColumnVisible('actions')" label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button
                size="small"
                text
                type="warning"
                :disabled="!row.retryable || isActionBusy(row.job.id)"
                :loading="actionPending[row.job.id] === 'retry'"
                @click.stop="handleSingleRetry(row)"
              >
                重试
              </el-button>
              <el-button size="small" text type="primary" @click.stop="openDiagnostic(row)">诊断</el-button>
              <el-button size="small" text @click.stop="openJobDetail(row)">详情</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-row app-pagination-row">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="handlePageChange"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, type UnwrapRef } from "vue";
import type { TableInstance } from "element-plus";
import { Filter, Refresh } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import BatchResultStrip from "@/components/BatchResultStrip.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import ShortcutHintList from "@/components/ShortcutHintList.vue";
import WorkbenchEmptyState from "@/components/WorkbenchEmptyState.vue";
import WorkbenchSectionHeader from "@/components/WorkbenchSectionHeader.vue";
import { formatDateTime, getJobSourceFilename } from "@/utils/format";
import { incidentPriorityLabel } from "@/utils/incidents";
import { failureTypeLabel, failureTypeTagType, stageLabel } from "./incidentQuery";
import { incidentListShortcutHints } from "./useIncidentShortcuts";
import type { IncidentActions } from "./useIncidentActions";
import type { IncidentDiagnostic } from "./useIncidentDiagnostic";
import type { IncidentQueue } from "./useIncidentQueue";

const batchResultExpanded = defineModel<UnwrapRef<IncidentActions["batchResultExpanded"]>>("batchResultExpanded", { required: true });
const {
  activeFilterLabel,
  activeFilterChips,
  error,
  incidentErrorDiagnosticContext,
  normalizedBatchResult,
  failedBatchItems,
  loading,
  items,
  tablePreferences,
  hasActiveFilters,
  actionPending,
  page,
  pageSize,
  total,
  removeFilter,
  clearBatchResult,
  manualRefresh,
  reselectFailedItems,
  incidentRowClassName,
  handleSelectionChange,
  openDiagnostic,
  clearIncidentFilters,
  isTableColumnVisible,
  isActionBusy,
  handleSingleRetry,
  openJobDetail,
  handlePageChange,
} = defineProps<{
  activeFilterLabel: UnwrapRef<IncidentQueue["activeFilterLabel"]>;
  activeFilterChips: UnwrapRef<IncidentQueue["activeFilterChips"]>;
  error: UnwrapRef<IncidentQueue["error"]>;
  incidentErrorDiagnosticContext: UnwrapRef<IncidentQueue["incidentErrorDiagnosticContext"]>;
  normalizedBatchResult: UnwrapRef<IncidentActions["normalizedBatchResult"]>;
  failedBatchItems: UnwrapRef<IncidentActions["failedBatchItems"]>;
  loading: UnwrapRef<IncidentQueue["loading"]>;
  items: UnwrapRef<IncidentQueue["items"]>;
  tablePreferences: UnwrapRef<IncidentQueue["tablePreferences"]>;
  hasActiveFilters: UnwrapRef<IncidentQueue["hasActiveFilters"]>;
  actionPending: UnwrapRef<IncidentActions["actionPending"]>;
  page: UnwrapRef<IncidentQueue["page"]>;
  pageSize: UnwrapRef<IncidentQueue["pageSize"]>;
  total: UnwrapRef<IncidentQueue["total"]>;
  removeFilter: IncidentQueue["removeFilter"];
  clearBatchResult: IncidentActions["clearBatchResult"];
  manualRefresh: () => Promise<void>;
  reselectFailedItems: IncidentActions["reselectFailedItems"];
  incidentRowClassName: IncidentDiagnostic["incidentRowClassName"];
  handleSelectionChange: IncidentQueue["handleSelectionChange"];
  openDiagnostic: IncidentDiagnostic["openDiagnostic"];
  clearIncidentFilters: IncidentQueue["clearIncidentFilters"];
  isTableColumnVisible: IncidentQueue["isTableColumnVisible"];
  isActionBusy: IncidentActions["isActionBusy"];
  handleSingleRetry: IncidentActions["handleSingleRetry"];
  openJobDetail: IncidentDiagnostic["openJobDetail"];
  handlePageChange: IncidentQueue["handlePageChange"];
}>();

const tableRef = ref<TableInstance | null>(null);
const incidentEmptyStateTitle = computed(() => (hasActiveFilters ? "当前筛选暂无异常任务" : "异常队列为空"));
const incidentEmptyStateDescription = computed(() =>
  hasActiveFilters
    ? "可以清空筛选回到默认优先级视图，或刷新队列确认最新异常状态。"
    : "当前没有需要优先分诊的异常 document_jobs。",
);

// 页面的清除选择、重选失败项和列设置变化都需要直接操作表格实例。
defineExpose({
  clearSelection: () => tableRef.value?.clearSelection(),
  toggleRowSelection: (row: UnwrapRef<IncidentQueue["items"]>[number], selected: boolean) =>
    tableRef.value?.toggleRowSelection(row, selected),
  doLayout: () => tableRef.value?.doLayout(),
});
</script>

<style scoped lang="scss">
.incident-list-panel {
  position: relative;
}

.incident-list-panel {
  display: grid;
  gap: var(--app-space-3);
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.active-filter-chips,
.job-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.incident-table-wrap {
  overflow-x: auto;
}

.incident-table {
  min-width: 980px;
}

.incident-table.is-compact-density {
  :deep(.el-table__cell) {
    padding: 6px 0;
  }
}

.incident-main {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.incident-table.is-compact-density .incident-main,
.incident-table.is-compact-density .status-cell,
.incident-table.is-compact-density .retry-cell,
.incident-table.is-compact-density .time-cell {
  gap: 4px;
}

.job-title-button {
  max-width: 100%;
  padding: 0;
  border: 0;
  overflow: hidden;
  background: transparent;
  color: var(--el-color-primary);
  font: inherit;
  font-weight: 650;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.job-id {
  color: var(--app-color-text-muted);
}

.evidence-line {
  display: grid;
  gap: 2px;
  color: var(--app-color-text);
}

.evidence-line small {
  overflow: hidden;
  color: var(--app-color-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-cell,
.retry-cell,
.time-cell {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.time-cell small,
.retry-cell span,
.status-cell span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.incident-table.is-compact-density .action-row {
  gap: 2px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

@media (max-width: 900px) {
  .section-header {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
