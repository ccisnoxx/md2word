<!-- File: frontend/src/pages/JobsPage.vue -->
<!-- Purpose: Render the document job list workbench with filtering and batch actions. -->
<template>
  <main class="jobs-page app-page" aria-labelledby="jobs-title">
    <section class="jobs-hero app-page-header app-page-shell app-page-shell--wide">
      <div class="hero-copy">
        <p class="hero-eyebrow page-kicker">Document Jobs</p>
        <h1 id="jobs-title" class="page-title">任务列表</h1>
        <p class="page-description">集中查看 PDF 转 Word 任务状态、失败原因和交付结果。上传创建任务已独立为更宽松的创建流程。</p>
      </div>
      <div class="hero-actions">
        <div class="live-pill" :class="{ 'is-loading': loading }">
          <span aria-hidden="true"></span>
          <strong>{{ syncStatusText }}</strong>
          <small v-if="lastRefreshedAt">{{ lastRefreshedLabel }}</small>
        </div>
        <span :title="createDisabledReason">
          <el-button
            type="primary"
            :icon="Plus"
            :disabled="!canCreateJob"
            @click="goCreateJob"
          >
            创建任务
          </el-button>
        </span>
        <el-button class="hero-refresh" :icon="Refresh" :loading="loading" @click="() => loadJobs()">刷新任务</el-button>
      </div>
    </section>

    <section class="metric-grid app-metric-grid app-page-shell app-page-shell--wide" aria-label="任务概览">
      <article v-for="metric in metrics" :key="metric.key" class="metric-card app-metric-card" :class="`metric-${metric.tone}`">
        <span class="metric-icon" aria-hidden="true">
          <el-icon><component :is="metric.icon" /></el-icon>
        </span>
        <div>
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <em>{{ metric.helper }}</em>
        </div>
      </article>
    </section>

    <section class="jobs-list-panel app-filter-panel app-page-shell app-page-shell--wide" aria-label="任务列表">
      <div class="section-header table-header">
        <div>
          <p class="table-kicker page-kicker">当前视图：{{ activeFilterLabel }}</p>
          <h2 class="section-title">转换任务</h2>
          <p class="section-subtitle">查看当前账号可见的 document_jobs。处理中任务会自动刷新。</p>
        </div>
        <div class="toolbar primary-toolbar">
          <el-input
            v-model="searchKeyword"
            class="search-input"
            clearable
            placeholder="搜索任务/文件/错误"
            :prefix-icon="Search"
            @clear="handleFilter"
            @keyup.enter="handleFilter"
          />
          <el-select v-model="statusFilter" clearable placeholder="全部状态" class="filter-select" @change="handleStatusFilterChange">
            <el-option v-for="status in statuses" :key="status" :label="jobStatusText[status]" :value="status" />
          </el-select>
          <el-select v-model="qaStatusFilter" clearable placeholder="全部 QA" class="filter-select" @change="handleFilter">
            <el-option
              v-for="status in qaStatuses"
              :key="status"
              :label="translationQaStatusText[status]"
              :value="status"
            />
          </el-select>
          <el-popover placement="bottom-end" :width="430" trigger="click">
            <template #reference>
              <el-button :icon="Filter">
                更多筛选
                <span v-if="advancedFilterCount" class="filter-count">{{ advancedFilterCount }}</span>
              </el-button>
            </template>
            <div class="advanced-filter-panel">
              <label>
                <span>排序</span>
                <el-select v-model="sortFilter" @change="handleFilter">
                  <el-option v-for="option in sortOptions" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </label>
              <label>
                <span>创建时间</span>
                <el-date-picker
                  v-model="createdRange"
                  type="datetimerange"
                  start-placeholder="创建开始"
                  end-placeholder="创建结束"
                  value-format="YYYY-MM-DDTHH:mm:ssZ"
                  @change="handleFilter"
                />
              </label>
              <div class="advanced-filter-footer">
                <el-switch v-model="includeArchived" active-text="含归档" inactive-text="默认" @change="handleFilter" />
                <el-button text @click="resetAdvancedFilters">清空高级筛选</el-button>
              </div>
            </div>
          </el-popover>
          <el-button :icon="Refresh" :loading="loading" @click="handleFilter">搜索</el-button>
        </div>
      </div>

      <div class="quick-filter-row" aria-label="快捷筛选">
        <el-button :type="statusGroupFilter === 'active' ? 'primary' : undefined" @click="applyQuickFilter('active')">处理中</el-button>
        <el-button :type="statusFilter === 'failed' ? 'primary' : undefined" @click="applyQuickFilter('failed')">失败</el-button>
        <el-button :type="includeArchived ? 'primary' : undefined" @click="applyQuickFilter('archived')">含归档</el-button>
      </div>

      <div v-if="activeFilterChips.length" class="active-filter-chips" aria-label="当前筛选条件">
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

      <div v-if="selectedJobs.length" class="selection-bar" aria-label="批量操作">
        <span>已选 {{ selectedJobs.length }} 个任务</span>
        <div class="selection-actions">
          <el-button :disabled="!selectedRetryableJobs.length" :loading="batchLoading" @click="handleBatchRetry">
            批量重试 {{ selectedRetryableJobs.length }}
          </el-button>
          <el-button :disabled="!selectedCancelableJobs.length" :loading="batchLoading" @click="handleBatchCancel">
            批量取消 {{ selectedCancelableJobs.length }}
          </el-button>
          <el-button :disabled="!selectedArchivableJobs.length" :loading="batchLoading" @click="handleBatchArchive">
            批量归档 {{ selectedArchivableJobs.length }}
          </el-button>
        </div>
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
        type="success"
        :closable="true"
        show-icon
        :title="lastDownloadLink.label"
        @close="lastDownloadLink = null"
      >
        <div class="download-link-notice">
          <span>有效期至 {{ formatDateTime(lastDownloadLink.expiresAt) }}</span>
          <a :href="lastDownloadLink.url" target="_blank" rel="noopener">打开下载链接</a>
          <el-button text size="small" @click="copyLastDownloadLink">复制链接</el-button>
        </div>
      </el-alert>
      <el-alert
        v-if="batchResult && batchResult.failed > 0"
        class="inline-result-alert"
        type="warning"
        :closable="true"
        show-icon
        :title="`${batchResultLabel}存在失败项`"
        @close="batchResult = null"
      >
        <div class="batch-failure-list">
          <p>{{ batchResultLabel }}失败 {{ batchResult.failed }} 个，成功 {{ batchResult.succeeded }} 个。</p>
          <ul>
            <li v-for="item in failedBatchItems" :key="item.job_id">
              <span class="mono">{{ item.job_id }}</span>
              <span>{{ item.error_code || item.status_code }}</span>
              <span>{{ item.detail || "后端未返回失败详情。" }}</span>
            </li>
          </ul>
        </div>
      </el-alert>

      <div v-if="summaryEntries.length" class="summary-row" aria-label="状态汇总">
        <span class="summary-caption">当前筛选状态汇总</span>
        <el-tag v-for="[status, count] in summaryEntries" :key="status" effect="plain">
          {{ statusLabel(status) }}: {{ count }}
        </el-tag>
      </div>

      <el-card class="jobs-table-card card-flat app-panel app-table-card" shadow="never">
        <div v-if="showEmptyState" class="empty-state" aria-live="polite">
          <el-icon><Files /></el-icon>
          <h3>{{ emptyStateTitle }}</h3>
          <p>{{ emptyStateDescription }}</p>
          <div class="empty-actions">
            <el-button v-if="hasActiveFilters" :icon="Filter" @click="clearAllFilters">清空筛选</el-button>
            <el-button
              v-if="canCreateJob"
              type="primary"
              :icon="Plus"
              @click="goCreateJob"
            >
              创建任务
            </el-button>
          </div>
        </div>
        <JobTable
          :jobs="jobs"
          :loading="loading"
          :page="page"
          :page-size="pageSize"
          :total="total"
          :action-pending="actionPending"
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
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { CircleCheck, Files, Filter, Plus, Refresh, Search, Timer, Warning } from "@element-plus/icons-vue";
import { useRoute, useRouter, type LocationQuery } from "vue-router";

import type {
  DocumentJobActionId,
  DocumentJobBulkResponse,
  DocumentJobListSort,
  DocumentJobResponse,
  DocumentJobStatus,
  DocumentJobStatusGroup,
  TranslationQaStatus,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobTable from "@/components/JobTable.vue";
import { useAuthStore } from "@/stores/auth";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canRetryDocumentJob,
  formatDateTime,
  jobStatusText,
  shouldShowDocumentJobAction,
  translationQaStatusText,
} from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { copyDownloadLink, openDownloadLink, type DownloadLinkNotice } from "@/utils/download";

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const jobs = ref<DocumentJobResponse[]>([]);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const statusFilter = ref<DocumentJobStatus | "">("");
const statusGroupFilter = ref<DocumentJobStatusGroup | "">("");
const qaStatusFilter = ref<TranslationQaStatus | "">("");
const searchKeyword = ref("");
const sortFilter = ref<DocumentJobListSort>("created_at_desc");
const includeArchived = ref(false);
const createdRange = ref<[string, string] | null>(null);
const selectedJobs = ref<DocumentJobResponse[]>([]);
const batchLoading = ref(false);
const batchResult = ref<DocumentJobBulkResponse | null>(null);
const batchResultLabel = ref("");
const lastDownloadLink = ref<DownloadLinkNotice | null>(null);
const filteredSummary = ref<Record<string, number>>({});
const actionPending = ref<Record<string, DocumentJobActionId | undefined>>({});
const statuses: DocumentJobStatus[] = ["pending", "queued", "running", "succeeded", "failed", "canceled"];
const qaStatuses: TranslationQaStatus[] = ["unreviewed", "approved", "needs_fix", "blocked"];
const sortOptions: Array<{ label: string; value: DocumentJobListSort }> = [
  { label: "创建时间新到旧", value: "created_at_desc" },
  { label: "创建时间旧到新", value: "created_at_asc" },
  { label: "更新时间新到旧", value: "updated_at_desc" },
  { label: "更新时间旧到新", value: "updated_at_asc" },
];

type FilterChipKey = "status" | "status_group" | "translation_qa_status" | "q" | "sort" | "include_archived" | "created_range";
type LoadJobsOptions = {
  preserveError?: boolean;
  background?: boolean;
};

const ACTIVE_AUTO_REFRESH_MS = 8000;
const ACTIVE_STALE_MS = 10 * 60 * 1000;
const activeJobStatuses: DocumentJobStatus[] = ["pending", "queued", "running"];
const lastRefreshedAt = ref<string | null>(null);
const backgroundRefreshing = ref(false);
const nowMs = ref(Date.now());
let refreshTimer: number | undefined;

const jobsErrorDiagnosticContext = computed(() => ({
  route: route.fullPath,
  operation: "document_jobs.list",
}));
const summaryEntries = computed(() => Object.entries(filteredSummary.value).filter(([, count]) => count > 0));
const canCreateJob = computed(() => auth.hasPermission("document_jobs:create"));
const createDisabledReason = computed(() => (canCreateJob.value ? "" : "当前账号没有创建 document job 的权限。"));
const hasActiveFilters = computed(() =>
  Boolean(
    statusFilter.value ||
      statusGroupFilter.value ||
      qaStatusFilter.value ||
      searchKeyword.value.trim() ||
      includeArchived.value ||
      createdRange.value ||
      sortFilter.value !== "created_at_desc",
  ),
);
const showEmptyState = computed(() => !loading.value && !error.value && jobs.value.length === 0);
const emptyStateTitle = computed(() => (hasActiveFilters.value ? "没有匹配的任务" : "还没有任务"));
const emptyStateDescription = computed(() =>
  hasActiveFilters.value
    ? "当前筛选条件下没有 document job。清空筛选后可查看全部可见任务。"
    : "当前账号还没有可见的 document job。可以先上传 PDF 并创建转换任务。",
);
const advancedFilterCount = computed(() => {
  let count = 0;
  if (sortFilter.value !== "created_at_desc") {
    count += 1;
  }
  if (includeArchived.value) {
    count += 1;
  }
  if (createdRange.value) {
    count += 1;
  }
  return count;
});
const activeFilterLabel = computed(() => {
  const statusText = statusFilter.value
    ? statusLabel(statusFilter.value)
    : statusGroupFilter.value === "active"
      ? "处理中"
      : "全部状态";
  const qaText = qaStatusFilter.value ? `QA ${translationQaStatusText[qaStatusFilter.value]}` : "全部 QA";
  const archiveText = includeArchived.value ? "含归档" : "默认";
  const dateText = createdRange.value ? `${createdRange.value[0]} ~ ${createdRange.value[1]}` : "不限日期";
  return `${statusText} · ${qaText} · ${archiveText} · ${dateText}`;
});
const activeFilterChips = computed<Array<{ key: FilterChipKey; label: string }>>(() => {
  const chips: Array<{ key: FilterChipKey; label: string }> = [];
  if (statusFilter.value) {
    chips.push({ key: "status", label: `状态：${statusLabel(statusFilter.value)}` });
  } else if (statusGroupFilter.value === "active") {
    chips.push({ key: "status_group", label: "状态组：处理中" });
  }
  if (qaStatusFilter.value) {
    chips.push({ key: "translation_qa_status", label: `QA：${translationQaStatusText[qaStatusFilter.value]}` });
  }
  if (searchKeyword.value.trim()) {
    chips.push({ key: "q", label: `搜索：${searchKeyword.value.trim()}` });
  }
  if (includeArchived.value) {
    chips.push({ key: "include_archived", label: "含归档" });
  }
  if (createdRange.value) {
    chips.push({ key: "created_range", label: "创建时间已筛选" });
  }
  if (sortFilter.value !== "created_at_desc") {
    const sortOption = sortOptions.find((option) => option.value === sortFilter.value);
    chips.push({ key: "sort", label: `排序：${sortOption?.label || sortFilter.value}` });
  }
  return chips;
});
const returnQueryForDetail = computed(() => jobsRouteQuery());
const activeCount = computed(
  () => countByStatus("pending") + countByStatus("queued") + countByStatus("running"),
);
const selectedRetryableJobs = computed(() => selectedJobs.value.filter(canRetryDocumentJob));
const selectedCancelableJobs = computed(() => selectedJobs.value.filter(canCancelDocumentJob));
const selectedArchivableJobs = computed(() => selectedJobs.value.filter(canArchiveDocumentJob));
const failedBatchItems = computed(() => batchResult.value?.items.filter((item) => !item.ok) || []);
const activeVisibleJobs = computed(() => jobs.value.filter((job) => activeJobStatuses.includes(job.status)));
const failedVisibleJobs = computed(() => jobs.value.filter((job) => job.status === "failed"));
const staleVisibleJobs = computed(() => activeVisibleJobs.value.filter((job) => {
  const updatedAt = new Date(job.updated_at).getTime();
  return Number.isFinite(updatedAt) && nowMs.value - updatedAt > ACTIVE_STALE_MS;
}));
const syncStatusText = computed(() => {
  if (loading.value || backgroundRefreshing.value) {
    return "同步中";
  }
  if (staleVisibleJobs.value.length) {
    return "有停滞";
  }
  return "已同步";
});
const lastRefreshedLabel = computed(() => (lastRefreshedAt.value ? `最近 ${formatDateTime(lastRefreshedAt.value)}` : ""));
const metrics = computed(() => [
  {
    key: "total",
    label: "全部任务",
    value: total.value,
    helper: "当前筛选结果",
    icon: Files,
    tone: "primary",
  },
  {
    key: "active",
    label: "处理中",
    value: activeCount.value,
    helper: "等待或运行中",
    icon: Timer,
    tone: "indigo",
  },
  {
    key: "succeeded",
    label: "已完成",
    value: countByStatus("succeeded"),
    helper: "可下载交付",
    icon: CircleCheck,
    tone: "green",
  },
  {
    key: "failed",
    label: "需处理",
    value: countByStatus("failed"),
    helper: "失败任务",
    icon: Warning,
    tone: "amber",
  },
]);

async function loadJobs(options: LoadJobsOptions = {}): Promise<void> {
  if (loading.value || backgroundRefreshing.value) {
    return;
  }
  if (options.background) {
    backgroundRefreshing.value = true;
  } else {
    loading.value = true;
  }
  if (!options.preserveError) {
    error.value = null;
  }
  try {
    const response = await documentJobsApi.list({
      page: page.value,
      page_size: pageSize,
      status: statusFilter.value || undefined,
      status_group: statusGroupFilter.value || undefined,
      translation_qa_status: qaStatusFilter.value || undefined,
      q: searchKeyword.value.trim() || undefined,
      sort: sortFilter.value,
      include_archived: includeArchived.value,
      created_from: createdRange.value?.[0],
      created_to: createdRange.value?.[1],
    });
    jobs.value = response.items;
    selectedJobs.value = [];
    total.value = response.total;
    filteredSummary.value = response.filtered_summary ?? response.summary;
    lastRefreshedAt.value = new Date().toISOString();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    if (options.background) {
      backgroundRefreshing.value = false;
    } else {
      loading.value = false;
    }
  }
}

function shouldAutoRefreshJobs(): boolean {
  if (typeof document !== "undefined" && document.hidden) {
    return false;
  }
  return statusGroupFilter.value === "active" || activeVisibleJobs.value.length > 0;
}

function startAutoRefresh(): void {
  refreshTimer = window.setInterval(() => {
    nowMs.value = Date.now();
    if (shouldAutoRefreshJobs()) {
      void loadJobs({ preserveError: true, background: true });
    }
  }, ACTIVE_AUTO_REFRESH_MS);
}

function handlePageChange(nextPage: number): void {
  void syncRouteAndLoad(nextPage);
}

function handleFilter(): void {
  batchResult.value = null;
  void syncRouteAndLoad(1);
}

function handleStatusFilterChange(): void {
  statusGroupFilter.value = "";
  handleFilter();
}

function goCreateJob(): void {
  void router.push("/jobs/new");
}

function handleSelectionChange(selection: DocumentJobResponse[]): void {
  selectedJobs.value = selection;
}

function statusLabel(status: string): string {
  return jobStatusText[status as DocumentJobStatus] || status;
}

function countByStatus(status: DocumentJobStatus): number {
  return filteredSummary.value[status] || 0;
}

function firstQueryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

function isDocumentJobStatus(value: string): value is DocumentJobStatus {
  return statuses.includes(value as DocumentJobStatus);
}

function isDocumentJobSort(value: string): value is DocumentJobListSort {
  return sortOptions.some((option) => option.value === value);
}

function isDocumentJobStatusGroup(value: string): value is DocumentJobStatusGroup {
  return value === "active";
}

// 校验路由中的 QA 状态筛选值，避免把非法 query 传给后端。
function isTranslationQaStatus(value: string): value is TranslationQaStatus {
  return qaStatuses.includes(value as TranslationQaStatus);
}

function applyRouteQueryFilters(): void {
  const nextStatus = firstQueryValue(route.query.status);
  const nextStatusGroup = firstQueryValue(route.query.status_group);
  const nextSort = firstQueryValue(route.query.sort);
  const nextQaStatus = firstQueryValue(route.query.translation_qa_status);
  const nextQuery = firstQueryValue(route.query.q);
  const nextPage = Number(firstQueryValue(route.query.page));
  const createdFrom = firstQueryValue(route.query.created_from);
  const createdTo = firstQueryValue(route.query.created_to);
  statusFilter.value = isDocumentJobStatus(nextStatus) ? nextStatus : "";
  statusGroupFilter.value = statusFilter.value ? "" : isDocumentJobStatusGroup(nextStatusGroup) ? nextStatusGroup : "";
  qaStatusFilter.value = isTranslationQaStatus(nextQaStatus) ? nextQaStatus : "";
  sortFilter.value = isDocumentJobSort(nextSort) ? nextSort : "created_at_desc";
  searchKeyword.value = nextQuery;
  page.value = Number.isInteger(nextPage) && nextPage > 0 ? nextPage : 1;
  includeArchived.value = firstQueryValue(route.query.include_archived) === "true";
  createdRange.value = createdFrom && createdTo ? [createdFrom, createdTo] as [string, string] : null;
}

function applyQuickFilter(kind: "active" | "failed" | "archived"): void {
  qaStatusFilter.value = "";
  searchKeyword.value = "";
  createdRange.value = null;
  sortFilter.value = "updated_at_desc";
  if (kind === "active") {
    statusFilter.value = "";
    statusGroupFilter.value = "active";
    includeArchived.value = false;
  } else if (kind === "failed") {
    statusGroupFilter.value = "";
    statusFilter.value = "failed";
    includeArchived.value = false;
  } else {
    statusFilter.value = "";
    statusGroupFilter.value = "";
    includeArchived.value = true;
  }
  handleFilter();
}

function resetAdvancedFilters(): void {
  sortFilter.value = "created_at_desc";
  includeArchived.value = false;
  createdRange.value = null;
  handleFilter();
}

function clearAllFilters(): void {
  statusFilter.value = "";
  statusGroupFilter.value = "";
  qaStatusFilter.value = "";
  searchKeyword.value = "";
  sortFilter.value = "created_at_desc";
  includeArchived.value = false;
  createdRange.value = null;
  handleFilter();
}

function jobsRouteQuery(nextPage = page.value): Record<string, string> {
  const query: Record<string, string> = {
    sort: sortFilter.value,
    include_archived: includeArchived.value ? "true" : "false",
    page: String(nextPage),
  };
  if (statusFilter.value) {
    query.status = statusFilter.value;
  } else if (statusGroupFilter.value) {
    query.status_group = statusGroupFilter.value;
  }
  if (qaStatusFilter.value) {
    query.translation_qa_status = qaStatusFilter.value;
  }
  if (searchKeyword.value.trim()) {
    query.q = searchKeyword.value.trim();
  }
  if (createdRange.value) {
    query.created_from = createdRange.value[0];
    query.created_to = createdRange.value[1];
  }
  return query;
}

function isSameJobsRouteQuery(candidate: LocationQuery, expected: Record<string, string>): boolean {
  const keys = [
    "status",
    "status_group",
    "translation_qa_status",
    "sort",
    "include_archived",
    "q",
    "created_from",
    "created_to",
    "page",
  ];
  return keys.every((key) => firstQueryValue(candidate[key]) === (expected[key] ?? ""));
}

async function syncRouteAndLoad(nextPage: number, replace = false): Promise<void> {
  page.value = nextPage;
  const query = jobsRouteQuery(nextPage);
  if (!isSameJobsRouteQuery(route.query, query)) {
    await router[replace ? "replace" : "push"]({ name: "jobs", query });
    return;
  }
  await loadJobs();
}

function removeFilter(key: FilterChipKey): void {
  if (key === "status") {
    statusFilter.value = "";
  } else if (key === "status_group") {
    statusGroupFilter.value = "";
  } else if (key === "translation_qa_status") {
    qaStatusFilter.value = "";
  } else if (key === "q") {
    searchKeyword.value = "";
  } else if (key === "sort") {
    sortFilter.value = "created_at_desc";
  } else if (key === "include_archived") {
    includeArchived.value = false;
  } else if (key === "created_range") {
    createdRange.value = null;
  }
  handleFilter();
}

async function handleDownload(job: DocumentJobResponse): Promise<void> {
  if (isActionBusy(job.id)) {
    return;
  }
  setActionPending(job.id, "download");
  try {
    const response = await documentJobsApi.createDownloadUrl(job.id);
    lastDownloadLink.value = {
      label: `任务 ${job.id} 的下载链接已生成`,
      url: response.download_url,
      expiresAt: response.expires_at,
      fileName: response.file.original_filename,
    };
    const opened = openDownloadLink(response.download_url);
    if (opened) {
      ElMessage.success(`下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
    } else {
      ElMessage.warning("浏览器可能拦截了新窗口，页面已显示下载链接。");
    }
  } catch (caught) {
    await handleActionError(caught);
  } finally {
    clearActionPending(job.id);
  }
}

async function handleActionError(caught: unknown): Promise<void> {
  const normalized = normalizeApiError(caught);
  error.value = normalized;
  if (normalized.status === 403 || normalized.status === 409 || normalized.status === 503) {
    await loadJobs({ preserveError: true });
    error.value = normalized;
  }
}

async function copyLastDownloadLink(): Promise<void> {
  if (!lastDownloadLink.value) {
    return;
  }
  const copied = await copyDownloadLink(lastDownloadLink.value.url);
  if (copied) {
    ElMessage.success("下载链接已复制。");
    return;
  }
  ElMessage.warning("当前浏览器不支持自动复制。");
}

async function handleRetry(job: DocumentJobResponse): Promise<void> {
  await router.push({ path: `/jobs/${job.id}`, query: { retry: "1" } });
}

async function handleClone(job: DocumentJobResponse): Promise<void> {
  if (isActionBusy(job.id)) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "重新发起会基于当前任务的源 PDF 创建一个新任务，不会修改原任务，也不会作为 retry 计数。",
      "重新发起为新任务",
      {
        confirmButtonText: "创建新任务",
        cancelButtonText: "返回",
        type: "info",
      },
    );
    setActionPending(job.id, "clone");
    const response = await documentJobsApi.clone(job.id, { reason: "frontend clone from jobs list" });
    ElMessage.success("已创建新任务。");
    await router.push(`/jobs/${response.job_id}`);
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    await handleActionError(caught);
  } finally {
    clearActionPending(job.id);
  }
}

async function handleCancel(job: DocumentJobResponse): Promise<void> {
  if (isActionBusy(job.id)) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "取消会将任务标记为 canceled 并停止后续处理；如果任务已进入外部服务，系统不承诺强制中断该外部处理。文件和事件记录会保留。",
      "取消任务",
      {
        confirmButtonText: "确认取消",
        cancelButtonText: "返回",
        type: "warning",
      },
    );
    setActionPending(job.id, "cancel");
    await documentJobsApi.cancel(job.id);
    ElMessage.success("任务已取消。");
    await loadJobs();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    await handleActionError(caught);
  } finally {
    clearActionPending(job.id);
  }
}

async function handleArchive(job: DocumentJobResponse): Promise<void> {
  if (isActionBusy(job.id)) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "归档只会把终态任务从默认列表隐藏，不会删除源文件、结果文件或事件记录。开启“含归档”后仍可查看。",
      "归档任务",
      {
        confirmButtonText: "确认归档",
        cancelButtonText: "返回",
        type: "info",
      },
    );
    setActionPending(job.id, "archive");
    await documentJobsApi.archive(job.id);
    ElMessage.success("任务已归档。");
    await loadJobs();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    await handleActionError(caught);
  } finally {
    clearActionPending(job.id);
  }
}

async function handleUnarchive(job: DocumentJobResponse): Promise<void> {
  if (isActionBusy(job.id)) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "取消归档会让任务重新出现在默认列表中，不会修改文件或事件记录。",
      "取消归档",
      {
        confirmButtonText: "确认取消归档",
        cancelButtonText: "返回",
        type: "info",
      },
    );
    setActionPending(job.id, "unarchive");
    await documentJobsApi.unarchive(job.id);
    ElMessage.success("任务已取消归档。");
    await loadJobs();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    await handleActionError(caught);
  } finally {
    clearActionPending(job.id);
  }
}

async function handleDelete(job: DocumentJobResponse): Promise<void> {
  if (isActionBusy(job.id) || !shouldShowDocumentJobAction(job, "delete")) {
    return;
  }
  setActionPending(job.id, "delete");
  try {
    const preview = await documentJobsApi.previewDelete(job.id);
    const deleteCount = preview.totals.delete || 0;
    const keepCount = preview.totals.keep || 0;
    await ElMessageBox.confirm(
      `删除任务会隐藏该任务并清理可安全删除的关联文件。将删除 ${deleteCount} 个文件，保留 ${keepCount} 个文件；任务 metadata、事件和 audit 会保留。`,
      "删除任务",
      {
        confirmButtonText: "确认删除",
        cancelButtonText: "返回",
        type: "warning",
      },
    );
    await documentJobsApi.delete(job.id, {
      preview_hash: preview.preview_hash,
    });
    ElMessage.success("任务已删除。");
    await loadJobs();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    await handleActionError(caught);
  } finally {
    clearActionPending(job.id);
  }
}

// 调用后端批量重试接口，避免前端逐个发起单任务请求。
async function handleBatchRetry(): Promise<void> {
  const targets = selectedRetryableJobs.value;
  if (!targets.length) {
    return;
  }
  batchLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.bulkRetry({
      job_ids: targets.map((job) => job.id),
      reason: "frontend batch retry",
    });
    showBatchResult("批量重试", response);
    await loadJobs();
  } catch (caught) {
    await handleActionError(caught);
  } finally {
    batchLoading.value = false;
  }
}

// 调用后端批量归档接口，并保留现有归档确认语义。
async function handleBatchArchive(): Promise<void> {
  const targets = selectedArchivableJobs.value;
  if (!targets.length) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      `将归档 ${targets.length} 个终态任务。归档不是删除，源文件、结果文件和事件记录会保留。`,
      "批量归档任务",
      {
        confirmButtonText: "确认归档",
        cancelButtonText: "返回",
        type: "info",
      },
    );
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
    return;
  }
  batchLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.bulkArchive({
      job_ids: targets.map((job) => job.id),
    });
    showBatchResult("批量归档", response);
    await loadJobs();
  } catch (caught) {
    await handleActionError(caught);
  } finally {
    batchLoading.value = false;
  }
}

async function handleBatchCancel(): Promise<void> {
  const targets = selectedCancelableJobs.value;
  if (!targets.length) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      `将取消 ${targets.length} 个未终态任务。取消不会删除源文件、结果文件或事件记录。`,
      "批量取消任务",
      {
        confirmButtonText: "确认取消",
        cancelButtonText: "返回",
        type: "warning",
      },
    );
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
    return;
  }
  batchLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.bulkCancel({
      job_ids: targets.map((job) => job.id),
    });
    showBatchResult("批量取消", response);
    await loadJobs();
  } catch (caught) {
    await handleActionError(caught);
  } finally {
    batchLoading.value = false;
  }
}

// 用后端聚合结果展示批量操作的成功、失败数量和失败明细。
function showBatchResult(label: string, result: DocumentJobBulkResponse): void {
  batchResultLabel.value = label;
  batchResult.value = result.failed > 0 ? result : null;
  if (result.failed > 0) {
    ElMessage.warning(`${label}完成：成功 ${result.succeeded} 个，失败 ${result.failed} 个。`);
    return;
  }
  ElMessage.success(`${label}完成：成功 ${result.succeeded} 个。`);
}

function setActionPending(jobId: string, action: DocumentJobActionId): void {
  actionPending.value = { ...actionPending.value, [jobId]: action };
}

function clearActionPending(jobId: string): void {
  const next = { ...actionPending.value };
  delete next[jobId];
  actionPending.value = next;
}

function isActionBusy(jobId: string): boolean {
  return Boolean(actionPending.value[jobId]);
}

watch(
  () => route.query,
  () => {
    applyRouteQueryFilters();
    batchResult.value = null;
    void loadJobs();
  },
  { deep: true },
);

onMounted(() => {
  applyRouteQueryFilters();
  void syncRouteAndLoad(page.value, true);
  startAutoRefresh();
});

onBeforeUnmount(() => {
  if (refreshTimer !== undefined) {
    window.clearInterval(refreshTimer);
  }
});
</script>

<style scoped lang="scss">
.jobs-page {
  position: relative;
  margin: -20px -24px -36px;
  padding: 28px 24px 42px;
  overflow: visible;
  color: var(--app-color-text);
  background: transparent;
  color-scheme: var(--app-color-scheme);
}

.jobs-page::before {
  position: absolute;
  inset: 0 0 auto;
  height: 220px;
  content: "";
  background:
    linear-gradient(100deg, var(--app-color-ambient-primary), transparent 62%),
    linear-gradient(180deg, var(--app-color-glass-muted), transparent);
  pointer-events: none;
}

.jobs-hero,
.metric-grid,
.jobs-list-panel {
  position: relative;
  z-index: 1;
}

.jobs-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px 28px;
  align-items: start;
  min-height: auto;
  border-color: var(--app-color-primary-border);
}

.hero-copy {
  max-width: 820px;
}

.hero-eyebrow,
.table-kicker {
  margin-bottom: 10px;
}

.hero-copy h1 {
  margin: 0 0 8px;
}

.hero-copy p:last-child {
  margin-bottom: 0;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.live-pill {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid var(--app-color-accent-cyan-border);
  border-radius: var(--app-radius-md);
  background: linear-gradient(135deg, var(--app-color-accent-cyan-soft), var(--app-color-surface));
  color: var(--app-color-accent-cyan);
  font-size: 13px;
}

.live-pill small {
  flex-basis: 100%;
  color: var(--app-color-text-muted);
  font-size: 11px;
}

.live-pill span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 4px var(--app-color-success-soft);
}

.live-pill.is-loading span {
  color: var(--app-color-primary);
  animation: app-status-pulse var(--app-motion-slow) ease-out infinite alternate;
}

.hero-refresh {
  min-height: 38px;
  border-color: var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.metric-card {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  min-height: 92px;
  padding: 14px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: linear-gradient(180deg, var(--app-color-surface), var(--app-color-surface-muted));
  box-shadow: var(--app-shadow-panel);
}

.metric-icon {
  display: inline-grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: var(--app-radius-md);
  background: linear-gradient(135deg, var(--app-color-primary), var(--app-color-primary-hover));
  color: #ffffff;
  font-size: 20px;
}

.metric-card span:not(.metric-icon) {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin: 4px 0;
  color: var(--app-color-text);
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
}

.metric-card em {
  color: var(--app-color-text-faint);
  font-size: 12px;
  font-style: normal;
}

.metric-green .metric-icon {
  background: linear-gradient(135deg, var(--app-color-success), var(--app-color-accent-cyan));
  color: #ffffff;
}

.metric-amber .metric-icon {
  background: linear-gradient(135deg, var(--app-color-warning), var(--app-color-accent-amber));
  color: #ffffff;
}

.metric-indigo .metric-icon {
  background: linear-gradient(135deg, var(--app-color-info), var(--app-color-primary));
  color: #ffffff;
}

.jobs-list-panel {
  margin-top: 16px;
}

.table-header {
  align-items: flex-start;
  margin-bottom: 12px;
}

.section-title {
  font-size: 20px;
}

.primary-toolbar {
  justify-content: flex-end;
  max-width: 760px;
}

.search-input {
  width: min(320px, 100%);
}

.filter-select {
  width: 150px;
}

.filter-count {
  display: inline-grid;
  min-width: 18px;
  height: 18px;
  margin-left: 6px;
  place-items: center;
  border-radius: 999px;
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary);
  font-size: 12px;
  font-weight: 700;
}

.advanced-filter-panel {
  display: grid;
  gap: 14px;
}

.advanced-filter-panel label {
  display: grid;
  gap: 6px;
}

.advanced-filter-panel label > span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.advanced-filter-panel :deep(.el-date-editor) {
  width: 100%;
}

.advanced-filter-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
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
  padding: 8px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(90deg, var(--app-color-primary-soft), transparent),
    var(--app-color-surface-muted);
}

.summary-caption {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.selection-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-primary-soft);
  color: var(--app-color-primary-hover);
  font-size: 14px;
}

.selection-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
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

.download-link-notice span,
.batch-failure-list p {
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

.batch-failure-list {
  display: grid;
  gap: 8px;
}

.batch-failure-list ul {
  display: grid;
  gap: 6px;
  max-height: 180px;
  margin: 0;
  padding-left: 18px;
  overflow: auto;
}

.batch-failure-list li {
  display: grid;
  grid-template-columns: minmax(160px, 0.8fr) minmax(90px, 0.4fr) minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.5;
}

.jobs-table-card {
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: none;
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

.jobs-page :deep(.el-button) {
  border-radius: var(--app-radius-md);
}

.jobs-page :deep(.el-button--primary) {
  border: 1px solid var(--app-color-primary);
  background: linear-gradient(135deg, var(--app-color-primary), var(--app-color-primary-hover) 72%, var(--app-color-accent-cyan));
  box-shadow: 0 8px 18px color-mix(in srgb, var(--app-color-primary) 22%, transparent);
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

.jobs-table-card :deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: var(--app-color-surface-muted);
  --el-table-row-hover-bg-color: var(--app-color-primary-soft);
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

@media (prefers-color-scheme: dark) {
  .jobs-page {
    background: var(--app-color-bg);
    color-scheme: var(--app-color-scheme);
  }

  .selection-bar {
    border-color: var(--app-color-primary-border);
    background: var(--app-color-primary-soft);
    color: var(--app-color-primary-hover);
  }

  .advanced-filter-panel label > span {
    color: var(--app-color-text-muted);
  }

  .jobs-page :deep(.el-tag) {
    background: var(--app-color-surface-muted);
  }

  .jobs-table-card :deep(.el-table) {
    --el-table-header-bg-color: var(--app-color-surface-muted);
    --el-table-row-hover-bg-color: var(--app-color-primary-soft);
  }
}

@media (max-width: 1080px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .primary-toolbar {
    justify-content: flex-start;
    width: 100%;
    max-width: none;
  }
}

@media (max-width: 760px) {
  .jobs-page {
    margin: -16px -16px -36px;
    padding: 18px 12px 30px;
  }

  .jobs-hero {
    grid-template-columns: 1fr;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .table-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar,
  .search-input,
  .filter-select {
    width: 100%;
  }

  .selection-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .selection-actions {
    justify-content: flex-start;
  }

  .batch-failure-list li {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .jobs-hero,
  .jobs-list-panel {
    padding: 16px;
  }

  .metric-card {
    min-height: 96px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .jobs-page :deep(.el-button) {
    transition: none;
  }
}
</style>
