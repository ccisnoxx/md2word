<template>
  <section class="jobs-list-panel app-filter-panel app-page-shell app-page-shell--wide" aria-label="任务列表">
    <WorkbenchSectionHeader
      :kicker="`当前视图：${activeFilterLabel}`"
      title="转换任务"
      subtitle="查看当前账号可见的 document_jobs。处理中任务会自动刷新。"
      header-class="table-header"
    >
      <template #extra>
        <slot name="toolbar" />
      </template>
    </WorkbenchSectionHeader>

    <div class="quick-filter-row app-quick-filter-row" aria-label="快捷筛选">
      <el-button :type="statusGroupFilter === 'active' ? 'primary' : undefined" @click="applyQuickFilter('active')">处理中</el-button>
      <el-button :type="statusFilter === 'failed' ? 'primary' : undefined" @click="applyQuickFilter('failed')">失败</el-button>
      <el-button :type="includeArchived ? 'primary' : undefined" @click="applyQuickFilter('archived')">含归档</el-button>
    </div>

    <div v-if="activeFilterChips.length" class="active-filter-chips app-active-filter-chips" aria-label="当前筛选条件">
      <el-tag
        v-for="chip in activeFilterChips"
        :key="chip.key"
        closable
        effect="plain"
        @close="removeFilter(chip.key)"
      >
        {{ chip.label }}
      </el-tag>
    </div>

    <ApiErrorAlert :error="error" :diagnostic-context="jobsErrorDiagnosticContext" />
    <el-alert
      v-if="staleVisibleJobs.length"
      class="inline-result-alert"
      type="warning"
      :closable="false"
      show-icon
      :title="`${staleVisibleJobs.length} 个处理中任务长时间未更新`"
    >
      <div class="stale-job-list">
        <RouterLink
          v-for="job in staleVisibleJobs.slice(0, 3)"
          :key="job.id"
          class="mono"
          :to="{ path: `/jobs/${job.id}`, query: returnQueryForDetail }"
        >
          {{ job.id }}
        </RouterLink>
        <span v-if="staleVisibleJobs.length > 3">等 {{ staleVisibleJobs.length }} 个任务</span>
      </div>
    </el-alert>
    <el-alert
      v-if="failedVisibleJobs.length"
      class="inline-result-alert"
      type="error"
      :closable="false"
      show-icon
      :title="`${failedVisibleJobs.length} 个失败任务需要处理`"
    >
      <div class="failed-job-list">
        <RouterLink v-for="job in failedVisibleJobs.slice(0, 3)" :key="job.id" :to="`/jobs/${job.id}`">
          <span class="mono">{{ job.id }}</span>
          <span>{{ job.failed_stage || job.stage }}</span>
          <span>{{ job.error_code || "unknown_error" }}</span>
          <span>{{ job.error_message || "进入详情查看诊断。" }}</span>
        </RouterLink>
      </div>
    </el-alert>
    <el-alert
      v-if="lastDownloadLink"
      class="inline-result-alert"
      :type="lastDownloadLink.notice ? 'warning' : 'success'"
      :closable="true"
      show-icon
      :title="lastDownloadLink.label"
      @close="lastDownloadLink = null"
    >
      <div class="download-link-notice">
        <strong v-if="lastDownloadLink.notice" class="download-policy-notice" role="status">{{ lastDownloadLink.notice }}</strong>
        <span>有效期至 {{ formatDateTime(lastDownloadLink.expiresAt) }}</span>
        <a :href="lastDownloadLink.url" target="_blank" rel="noopener">打开下载链接</a>
        <el-button text size="small" @click="copyLastDownloadLink">复制链接</el-button>
      </div>
    </el-alert>
    <BatchResultStrip
      v-if="normalizedBatchResult"
      v-model:expanded="batchResultExpanded"
      class="inline-result-alert"
      :result="normalizedBatchResult"
      @close="clearBatchResult"
    />

    <div v-if="summaryEntries.length" class="summary-row" aria-label="状态汇总">
      <span class="summary-caption">当前筛选状态汇总</span>
      <el-tag v-for="[status, count] in summaryEntries" :key="status" effect="plain">
        {{ statusLabel(status) }}: {{ count }}
      </el-tag>
    </div>

    <el-card class="jobs-table-card card-flat app-panel app-table-card" shadow="never">
      <WorkbenchEmptyState
        v-if="showEmptyState"
        root-class="empty-state"
        :icon="Files"
        :title="emptyStateTitle"
        :description="emptyStateDescription"
      >
        <template #actions>
          <el-button v-if="hasActiveFilters" :icon="Filter" @click="clearAllFilters">清空筛选</el-button>
          <el-button
            v-if="canCreateJob"
            type="primary"
            :icon="Plus"
            @click="goCreateJob"
          >
            创建任务
          </el-button>
        </template>
      </WorkbenchEmptyState>
      <JobTable
        ref="jobTableRef"
        :jobs="jobs"
        :loading="loading"
        :page="page"
        :page-size="pageSize"
        :total="total"
        :action-pending="actionPending"
        :density="tablePreferences.density"
        :visible-columns="tablePreferences.visibleColumns"
        @page-change="handlePageChange"
        @selection-change="handleSelectionChange"
        @download="handleDownload"
        @retry="handleRetry"
        @clone="handleClone"
        @cancel="handleCancel"
        @archive="handleArchive"
        @unarchive="handleUnarchive"
        @delete="handleDelete"
      />
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, type UnwrapRef } from "vue";
import { Files, Filter, Plus } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import BatchResultStrip from "@/components/BatchResultStrip.vue";
import JobTable from "@/components/JobTable.vue";
import WorkbenchEmptyState from "@/components/WorkbenchEmptyState.vue";
import WorkbenchSectionHeader from "@/components/WorkbenchSectionHeader.vue";
import { formatDateTime } from "@/utils/format";
import { statusLabel } from "./jobsListQuery";
import type { JobsActions } from "./useJobsActions";
import type { JobsList } from "./useJobsList";

const lastDownloadLink = defineModel<UnwrapRef<JobsActions["lastDownloadLink"]>>("lastDownloadLink", { required: true });
const batchResultExpanded = defineModel<UnwrapRef<JobsActions["batchResultExpanded"]>>("batchResultExpanded", { required: true });
const {
  activeFilterLabel,
  statusFilter,
  statusGroupFilter,
  includeArchived,
  activeFilterChips,
  error,
  jobsErrorDiagnosticContext,
  staleVisibleJobs,
  failedVisibleJobs,
  returnQueryForDetail,
  normalizedBatchResult,
  summaryEntries,
  showEmptyState,
  hasActiveFilters,
  canCreateJob,
  jobs,
  loading,
  page,
  pageSize,
  total,
  actionPending,
  tablePreferences,
  applyQuickFilter,
  removeFilter,
  clearAllFilters,
  goCreateJob,
  clearBatchResult,
  copyLastDownloadLink,
  handlePageChange,
  handleSelectionChange,
  handleDownload,
  handleRetry,
  handleClone,
  handleCancel,
  handleArchive,
  handleUnarchive,
  handleDelete,
} = defineProps<{
  activeFilterLabel: UnwrapRef<JobsList["activeFilterLabel"]>;
  statusFilter: UnwrapRef<JobsList["statusFilter"]>;
  statusGroupFilter: UnwrapRef<JobsList["statusGroupFilter"]>;
  includeArchived: UnwrapRef<JobsList["includeArchived"]>;
  activeFilterChips: UnwrapRef<JobsList["activeFilterChips"]>;
  error: UnwrapRef<JobsList["error"]>;
  jobsErrorDiagnosticContext: UnwrapRef<JobsList["jobsErrorDiagnosticContext"]>;
  staleVisibleJobs: UnwrapRef<JobsList["staleVisibleJobs"]>;
  failedVisibleJobs: UnwrapRef<JobsList["failedVisibleJobs"]>;
  returnQueryForDetail: UnwrapRef<JobsList["returnQueryForDetail"]>;
  normalizedBatchResult: UnwrapRef<JobsActions["normalizedBatchResult"]>;
  summaryEntries: UnwrapRef<JobsList["summaryEntries"]>;
  showEmptyState: UnwrapRef<JobsList["showEmptyState"]>;
  hasActiveFilters: UnwrapRef<JobsList["hasActiveFilters"]>;
  canCreateJob: boolean;
  jobs: UnwrapRef<JobsList["jobs"]>;
  loading: UnwrapRef<JobsList["loading"]>;
  page: UnwrapRef<JobsList["page"]>;
  pageSize: UnwrapRef<JobsList["pageSize"]>;
  total: UnwrapRef<JobsList["total"]>;
  actionPending: UnwrapRef<JobsActions["actionPending"]>;
  tablePreferences: UnwrapRef<JobsList["tablePreferences"]>;
  applyQuickFilter: JobsList["applyQuickFilter"];
  removeFilter: JobsList["removeFilter"];
  clearAllFilters: JobsList["clearAllFilters"];
  goCreateJob: () => void;
  clearBatchResult: JobsActions["clearBatchResult"];
  copyLastDownloadLink: JobsActions["copyLastDownloadLink"];
  handlePageChange: JobsList["handlePageChange"];
  handleSelectionChange: JobsList["handleSelectionChange"];
  handleDownload: JobsActions["handleDownload"];
  handleRetry: JobsActions["handleRetry"];
  handleClone: JobsActions["handleClone"];
  handleCancel: JobsActions["handleCancel"];
  handleArchive: JobsActions["handleArchive"];
  handleUnarchive: JobsActions["handleUnarchive"];
  handleDelete: JobsActions["handleDelete"];
}>();

const jobTableRef = ref<{ clearSelection: () => void } | null>(null);
const emptyStateTitle = computed(() => (hasActiveFilters ? "没有匹配的任务" : "还没有任务"));
const emptyStateDescription = computed(() =>
  hasActiveFilters
    ? "当前筛选条件下没有 document job。清空筛选后可查看全部可见任务。"
    : "当前账号还没有可见的 document job。可以先上传 PDF 并创建转换任务。",
);

// 批量操作条的“清除选择”需要同步清空表格内部勾选状态。
defineExpose({
  clearSelection: () => jobTableRef.value?.clearSelection(),
});
</script>

<style scoped lang="scss">
.jobs-list-panel {
  margin-top: 16px;
  border-color: color-mix(in srgb, var(--app-color-primary-border) 72%, transparent);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--app-color-surface) 86%, var(--app-color-primary-soft)), var(--app-color-glass-muted)),
    var(--app-gradient-panel-depth);
  box-shadow: var(--app-shadow-panel);
}

.table-header {
  align-items: flex-start;
  margin-bottom: 12px;
}

.section-title {
  font-size: 20px;
}

.quick-filter-row,
.active-filter-chips,
.summary-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.quick-filter-row {
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--app-color-primary-border) 62%, transparent);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--app-color-primary-soft) 84%, transparent), transparent),
    var(--app-color-surface-muted);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.36);
}

.summary-caption {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.inline-result-alert {
  margin-bottom: 12px;
}

.download-link-notice {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.download-policy-notice {
  flex-basis: 100%;
  overflow-wrap: anywhere;
}

.download-link-notice span {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.download-link-notice a {
  color: var(--app-color-primary);
  font-weight: 700;
  text-decoration: none;
}

.stale-job-list,
.failed-job-list {
  display: grid;
  gap: 6px;
}

.stale-job-list {
  display: flex;
  flex-wrap: wrap;
}

.failed-job-list a {
  display: grid;
  grid-template-columns: minmax(120px, auto) minmax(72px, auto) minmax(120px, auto) minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  color: inherit;
  text-decoration: none;
}

.jobs-table-card {
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.jobs-table-card :deep(.el-card__body) {
  padding: 0;
}

.empty-state {
  display: grid;
  justify-items: center;
  gap: 10px;
  padding: 36px 20px 30px;
  border-bottom: 1px solid var(--app-color-border);
  background: var(--app-color-surface-muted);
  text-align: center;
}

.empty-state .el-icon {
  width: 42px;
  height: 42px;
  border-radius: var(--app-radius-md);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary);
  font-size: 22px;
}

.empty-state h3 {
  margin: 2px 0 0;
  color: var(--app-color-text);
  font-size: 18px;
}

.empty-state p {
  max-width: 520px;
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 14px;
  line-height: 1.7;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 4px;
}

.jobs-table-card :deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: color-mix(in srgb, var(--app-color-primary-soft) 72%, var(--app-color-surface));
  --el-table-row-hover-bg-color: color-mix(in srgb, var(--app-color-primary-soft) 74%, transparent);
  --el-table-border-color: var(--app-color-border-soft);
  --el-table-text-color: var(--app-color-text);
  --el-table-header-text-color: var(--app-color-text-muted);

  color: var(--app-color-text);
  background: transparent;
}

.jobs-table-card :deep(.el-table__inner-wrapper::before),
.jobs-table-card :deep(.el-table__fixed-right::before),
.jobs-table-card :deep(.el-table__fixed::before) {
  background: var(--app-color-border);
}

.jobs-table-card :deep(.el-table th.el-table__cell) {
  font-weight: 760;
  background: var(--el-table-header-bg-color);
}

.jobs-table-card :deep(.el-table td.el-table__cell),
.jobs-table-card :deep(.el-table th.el-table__cell) {
  border-bottom-color: var(--app-color-border);
}

.jobs-table-card :deep(.mono) {
  color: var(--app-color-primary);
}

.jobs-table-card :deep(.muted) {
  color: var(--app-color-text-faint);
}

.jobs-table-card :deep(.error-code) {
  color: var(--app-color-danger);
}

.jobs-table-card :deep(.el-pagination.is-background .btn-prev),
.jobs-table-card :deep(.el-pagination.is-background .btn-next),
.jobs-table-card :deep(.el-pagination.is-background .el-pager li) {
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
  color: var(--app-color-text);
}

.jobs-table-card :deep(.el-pagination.is-background .el-pager li.is-active) {
  background: var(--app-color-primary);
  color: #ffffff;
}

.jobs-list-panel {
  position: relative;
  z-index: 1;
}

.jobs-list-panel {
  border: 1px solid var(--app-color-border);
  margin-top: var(--app-space-3);
  background: var(--app-color-surface-elevated);
  box-shadow: var(--app-shadow-subtle);
}

.jobs-list-panel::before {
  display: none;
}

.jobs-list-panel:hover,
.jobs-table-card:hover {
  border-color: var(--app-color-border);
  box-shadow: var(--app-shadow-subtle);
  transform: none;
}

@media (prefers-color-scheme: dark) {
  .jobs-table-card :deep(.el-table) {
    --el-table-header-bg-color: var(--app-color-surface-muted);
    --el-table-row-hover-bg-color: var(--app-color-primary-soft);
  }
}

@media (max-width: 760px) {
  .table-header {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 520px) {
  .jobs-list-panel {
    padding: 16px;
  }
}
</style>
