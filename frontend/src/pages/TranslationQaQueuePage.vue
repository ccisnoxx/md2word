<!-- File: frontend/src/pages/TranslationQaQueuePage.vue -->
<!-- Purpose: Render the translation QA review queue backed by document_jobs list filtering. -->
<template>
  <main class="translation-qa-queue-page app-page" aria-labelledby="translation-qa-queue-title">
    <section class="page-heading app-page-shell">
      <div>
        <p class="page-kicker">Translation QA</p>
        <h1 id="translation-qa-queue-title" class="page-title">翻译 QA 队列</h1>
        <p class="page-description">按待复核、需修正和阻塞状态处理英文 PDF 翻译任务。</p>
      </div>
      <div class="heading-actions">
        <span class="queue-sync">当前视图：{{ activeFilterLabel }}</span>
        <el-button :icon="Refresh" :loading="loading" @click="loadJobs">刷新</el-button>
      </div>
    </section>

    <section class="qa-inbox-strip app-page-shell" aria-label="翻译 QA 收件箱">
      <button
        v-for="item in qaInboxItems"
        :key="item.status"
        type="button"
        class="qa-inbox-item"
        :class="[`is-${item.tone}`, { 'is-active': item.active }]"
        @click="applyInboxFilter(item.status)"
      >
        <span class="inbox-count">{{ item.count }}</span>
        <span class="inbox-copy">
          <strong>{{ item.label }}</strong>
          <small>{{ item.helper }}</small>
        </span>
      </button>
    </section>

    <section class="qa-workspace app-page-shell" aria-label="翻译 QA 工作区">
      <el-card class="card-flat queue-panel app-panel-card app-table-card" shadow="never">
        <div class="section-header table-header">
          <div>
            <h2 class="section-title">复核收件箱</h2>
            <p class="section-subtitle">列表复用 document-jobs 聚合结果；全文段落复核仍进入单任务 QA 页面。</p>
          </div>
          <div class="toolbar">
            <el-input
              v-model="searchKeyword"
              class="queue-search"
              clearable
              placeholder="搜索任务/文件/错误"
              :prefix-icon="Search"
              @clear="handleFilter"
              @keyup.enter="handleFilter"
            />
            <el-select v-model="qaStatusFilter" clearable placeholder="全部 QA" class="queue-filter" @change="handleFilter">
              <el-option
                v-for="status in qaStatuses"
                :key="status"
                :label="translationQaStatusText[status]"
                :value="status"
              />
            </el-select>
            <el-select v-model="statusFilter" clearable placeholder="任务状态" class="queue-filter" @change="handleFilter">
              <el-option v-for="status in statuses" :key="status" :label="jobStatusText[status]" :value="status" />
            </el-select>
            <el-popover placement="bottom-end" :width="340" trigger="click">
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
                <div class="advanced-filter-footer">
                  <el-switch
                    v-model="includeArchived"
                    active-text="含归档"
                    inactive-text="默认"
                    @change="handleFilter"
                  />
                  <el-button text @click="resetAdvancedFilters">清空高级筛选</el-button>
                </div>
              </div>
            </el-popover>
            <el-button :icon="Search" :loading="loading" @click="handleFilter">搜索</el-button>
          </div>
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

        <ApiErrorAlert :error="error" />

        <div v-if="showEmptyState" class="queue-empty-state" aria-live="polite">
          <h3>{{ emptyStateTitle }}</h3>
          <p>{{ emptyStateDescription }}</p>
          <div class="empty-actions">
            <el-button v-if="hasActiveFilters" :icon="Filter" @click="clearQueueFilters">查看全部 QA</el-button>
            <el-button v-if="qaStatusFilter !== 'approved'" type="primary" @click="applyInboxFilter('approved')">
              查看已通过
            </el-button>
          </div>
        </div>

        <div class="table-scroll">
          <el-table v-loading="loading" :data="jobs" border class="queue-table" :empty-text="emptyText" table-layout="fixed">
            <el-table-column label="任务" min-width="260">
              <template #default="{ row }">
                <div class="job-cell">
                  <button type="button" class="mono job-link job-link-button" @click="openTranslationQa(row)">{{ row.id }}</button>
                  <div class="filename" :title="getJobSourceFilename(row)">{{ getJobSourceFilename(row) }}</div>
                  <div class="job-meta">
                    <el-tag size="small" effect="plain">{{ jobModeText[row.mode] || row.mode }}</el-tag>
                    <el-tag v-if="row.error_code" size="small" type="danger" effect="plain">{{ row.error_code }}</el-tag>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="任务状态" min-width="136">
              <template #default="{ row }">
                <div class="status-cell">
                  <JobStatusBadge :status="row.status" />
                  <span class="muted">{{ stageLabel(row) }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="QA 状态" min-width="132">
              <template #default="{ row }">
                <el-tag :type="qaStatusTagType(row)" effect="plain">
                  {{ qaStatusLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="问题归因" min-width="132">
              <template #default="{ row }">
                {{ issueTypeLabel(row.translation_qa_issue_type) }}
              </template>
            </el-table-column>
            <el-table-column label="证据" min-width="190">
              <template #default="{ row }">
                <div class="evidence-tags">
                  <el-tag size="small" :type="row.document_ir_file_id ? 'success' : 'info'" effect="plain">DocumentIR</el-tag>
                  <el-tag size="small" :type="row.result_file_id ? 'success' : 'info'" effect="plain">DOCX</el-tag>
                  <el-tag size="small" :type="row.debug_full_text_enabled ? 'success' : 'info'" effect="plain">Debug</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="复核人" min-width="148">
              <template #default="{ row }">
                <div>{{ row.translation_qa_reviewed_by || "-" }}</div>
                <div class="muted">{{ formatDateTime(row.translation_qa_reviewed_at) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="更新" min-width="148">
              <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" min-width="168">
              <template #default="{ row }">
                <div class="action-row">
                  <el-button size="small" text type="primary" @click="openTranslationQa(row)">复核</el-button>
                  <el-button size="small" text @click="openTranslationQaDetail(row)">QA 详情</el-button>
                  <el-button size="small" text @click="openJobDetail(row)">任务</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="pagination-row">
          <el-pagination
            background
            layout="prev, pager, next, total"
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            @current-change="handlePageChange"
          />
        </div>
      </el-card>

      <aside class="qa-processing-rail" aria-label="QA 处理面板">
        <strong>处理面板</strong>
        <span>待复核 {{ countQaStatus("unreviewed") }}</span>
        <span>需修正 {{ countQaStatus("needs_fix") }}</span>
        <span>阻塞 {{ countQaStatus("blocked") }}</span>
      </aside>
    </section>

    <el-drawer
      :model-value="qaDrawerVisible"
      class="translation-qa-review-drawer"
      direction="rtl"
      :size="qaDrawerSize"
      :with-header="false"
      :destroy-on-close="false"
      append-to-body
      @update:model-value="handleDrawerModelValue"
    >
      <TranslationQaReviewPanel
        :job="qaDrawerJob"
        :qa="qaDrawerData"
        :form="qaReviewForm"
        :loading="qaDrawerLoading"
        :saving="qaDrawerSaving"
        :error="qaDrawerError"
        :queue-cleared="qaDrawerQueueCleared"
        :active-segment-index="qaDrawerActiveSegmentIndex"
        @update:form="updateQaReviewForm"
        @segment-index-change="setQaDrawerActiveSegment"
        @submit="submitQaReviewOnly"
        @submit-next="submitQaReviewAndNext"
        @refresh="refreshQaDrawer"
        @close="closeQaDrawer"
        @open-detail="openSelectedTranslationQaDetail"
      />
    </el-drawer>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Filter, Refresh, Search } from "@element-plus/icons-vue";
import { useRoute, useRouter, type LocationQuery, type RouteLocationRaw } from "vue-router";

import { documentJobsApi } from "@/api/documentJobs";
import type {
  DocumentJobListSort,
  DocumentJobResponse,
  DocumentJobStatus,
  DocumentJobTranslationQaResponse,
  TranslationQaIssueType,
  TranslationQaStatus,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import TranslationQaReviewPanel from "@/components/TranslationQaReviewPanel.vue";
import {
  formatDateTime,
  getJobSourceFilename,
  jobModeText,
  jobStageText,
  jobStatusText,
  translationQaStatusTagType,
  translationQaStatusText,
} from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  selectNextTranslationQaJob,
  shouldIgnoreTranslationQaShortcut,
  translationQaIssueTypeText,
  translationQaStatusOptions,
  type TranslationQaReviewDraft,
} from "@/utils/translationQa";

const router = useRouter();
const route = useRoute();

const jobs = ref<DocumentJobResponse[]>([]);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const qaStatusFilter = ref<TranslationQaStatus | "">("unreviewed");
const statusFilter = ref<DocumentJobStatus | "">("");
const searchKeyword = ref("");
const sortFilter = ref<DocumentJobListSort>("updated_at_desc");
const includeArchived = ref(false);
const qaDrawerVisible = ref(false);
const qaDrawerLoading = ref(false);
const qaDrawerSaving = ref(false);
const qaDrawerError = ref<ApiClientError | null>(null);
const qaDrawerJob = ref<DocumentJobResponse | null>(null);
const qaDrawerData = ref<DocumentJobTranslationQaResponse | null>(null);
const qaDrawerQueueCleared = ref(false);
const qaDrawerActiveSegmentIndex = ref(0);
const selectedQaJobId = ref("");
const qaReviewForm = reactive<TranslationQaReviewDraft>({
  status: "unreviewed",
  issue_type: null,
  note: "",
});

type QueueFilterChipKey = "translation_qa_status" | "status" | "q" | "sort" | "include_archived";
type QaInboxItem = {
  status: TranslationQaStatus;
  label: string;
  helper: string;
  count: number;
  tone: "info" | "warning" | "danger" | "success";
  active: boolean;
};

const qaDrawerSize = "min(920px, 92vw)";
const qaStatuses: TranslationQaStatus[] = translationQaStatusOptions;
const statuses: DocumentJobStatus[] = ["pending", "queued", "running", "succeeded", "failed", "canceled"];
const sortOptions: Array<{ label: string; value: DocumentJobListSort }> = [
  { label: "更新时间新到旧", value: "updated_at_desc" },
  { label: "更新时间旧到新", value: "updated_at_asc" },
  { label: "创建时间新到旧", value: "created_at_desc" },
  { label: "创建时间旧到新", value: "created_at_asc" },
];
const qaSummary = ref<Record<TranslationQaStatus, number>>({
  unreviewed: 0,
  approved: 0,
  needs_fix: 0,
  blocked: 0,
});
let qaDrawerLoadToken = 0;
let routeSyncInProgress = false;

const activeFilterLabel = computed(() => {
  const qaText = qaStatusFilter.value ? translationQaStatusText[qaStatusFilter.value] : "全部 QA";
  const statusText = statusFilter.value ? jobStatusText[statusFilter.value] : "全部任务状态";
  return `${qaText} · ${statusText}`;
});
const hasActiveFilters = computed(() =>
  Boolean(
    qaStatusFilter.value ||
      statusFilter.value ||
      searchKeyword.value.trim() ||
      includeArchived.value ||
      sortFilter.value !== "updated_at_desc",
  ),
);
const advancedFilterCount = computed(() => {
  let count = 0;
  if (sortFilter.value !== "updated_at_desc") {
    count += 1;
  }
  if (includeArchived.value) {
    count += 1;
  }
  return count;
});
const activeFilterChips = computed<Array<{ key: QueueFilterChipKey; label: string }>>(() => {
  const chips: Array<{ key: QueueFilterChipKey; label: string }> = [];
  if (qaStatusFilter.value) {
    chips.push({ key: "translation_qa_status", label: `QA：${translationQaStatusText[qaStatusFilter.value]}` });
  }
  if (statusFilter.value) {
    chips.push({ key: "status", label: `任务：${jobStatusText[statusFilter.value]}` });
  }
  if (searchKeyword.value.trim()) {
    chips.push({ key: "q", label: `搜索：${searchKeyword.value.trim()}` });
  }
  if (sortFilter.value !== "updated_at_desc") {
    const sortOption = sortOptions.find((option) => option.value === sortFilter.value);
    chips.push({ key: "sort", label: `排序：${sortOption?.label || sortFilter.value}` });
  }
  if (includeArchived.value) {
    chips.push({ key: "include_archived", label: "含归档" });
  }
  return chips;
});
const qaInboxItems = computed<QaInboxItem[]>(() => [
  {
    status: "unreviewed",
    label: "待复核",
    helper: "进入下一批 QA",
    count: countQaStatus("unreviewed"),
    tone: "info",
    active: qaStatusFilter.value === "unreviewed",
  },
  {
    status: "needs_fix",
    label: "需修正",
    helper: "交付前处理",
    count: countQaStatus("needs_fix"),
    tone: "warning",
    active: qaStatusFilter.value === "needs_fix",
  },
  {
    status: "blocked",
    label: "阻塞",
    helper: "证据或判断不足",
    count: countQaStatus("blocked"),
    tone: "danger",
    active: qaStatusFilter.value === "blocked",
  },
  {
    status: "approved",
    label: "已通过",
    helper: "已清理队列",
    count: countQaStatus("approved"),
    tone: "success",
    active: qaStatusFilter.value === "approved",
  },
]);
const emptyText = computed(() => (loading.value ? "加载中" : "当前筛选下暂无翻译 QA 任务"));
const showEmptyState = computed(() => !loading.value && !error.value && jobs.value.length === 0);
const emptyStateTitle = computed(() => (qaStatusFilter.value === "unreviewed" ? "待复核队列已清空" : "当前筛选暂无 QA 任务"));
const emptyStateDescription = computed(() =>
  hasActiveFilters.value
    ? "可以查看全部 QA 状态或切换到已通过队列确认处理结果。"
    : "当前账号暂无可见翻译 QA 任务。",
);

function firstQueryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

function isTranslationQaStatus(value: string): value is TranslationQaStatus {
  return qaStatuses.includes(value as TranslationQaStatus);
}

function isDocumentJobStatus(value: string): value is DocumentJobStatus {
  return statuses.includes(value as DocumentJobStatus);
}

function isDocumentJobSort(value: string): value is DocumentJobListSort {
  return sortOptions.some((option) => option.value === value);
}

function positivePage(value: string): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

function queueRouteQuery(nextPage = page.value, qaJobId: string | null = selectedQaJobId.value): Record<string, string> {
  const query: Record<string, string> = {
    translation_qa_status: qaStatusFilter.value || "all",
    sort: sortFilter.value,
    include_archived: includeArchived.value ? "true" : "false",
    page: String(nextPage),
  };
  if (statusFilter.value) {
    query.status = statusFilter.value;
  }
  if (searchKeyword.value.trim()) {
    query.q = searchKeyword.value.trim();
  }
  if (qaJobId) {
    query.qa_job_id = qaJobId;
  }
  return query;
}

function isSameQueueRouteQuery(candidate: LocationQuery, expected: Record<string, string>): boolean {
  const keys = ["translation_qa_status", "status", "sort", "include_archived", "q", "page", "qa_job_id"];
  return keys.every((key) => firstQueryValue(candidate[key]) === (expected[key] ?? ""));
}

function isSameQueueFilterRouteQuery(left: LocationQuery, right: LocationQuery): boolean {
  const keys = ["translation_qa_status", "status", "sort", "include_archived", "q", "page"];
  return keys.every((key) => firstQueryValue(left[key]) === firstQueryValue(right[key]));
}

function applyRouteQueryFilters(): void {
  const routeQaStatus = firstQueryValue(route.query.translation_qa_status);
  const routeStatus = firstQueryValue(route.query.status);
  const routeSort = firstQueryValue(route.query.sort);
  const routePage = firstQueryValue(route.query.page);
  const routeSearch = firstQueryValue(route.query.q);

  qaStatusFilter.value = routeQaStatus === "all" ? "" : isTranslationQaStatus(routeQaStatus) ? routeQaStatus : "unreviewed";
  statusFilter.value = isDocumentJobStatus(routeStatus) ? routeStatus : "";
  sortFilter.value = isDocumentJobSort(routeSort) ? routeSort : "updated_at_desc";
  includeArchived.value = firstQueryValue(route.query.include_archived) === "true";
  searchKeyword.value = routeSearch;
  page.value = routePage ? positivePage(routePage) : 1;
}

async function loadJobs(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.list({
      page: page.value,
      page_size: pageSize,
      translation_qa_status: qaStatusFilter.value || "all",
      status: statusFilter.value || undefined,
      q: searchKeyword.value.trim() || undefined,
      sort: sortFilter.value,
      include_archived: includeArchived.value,
    });
    jobs.value = response.items;
    total.value = response.total;
    qaSummary.value = {
      unreviewed: response.translation_qa_summary?.unreviewed ?? 0,
      approved: response.translation_qa_summary?.approved ?? 0,
      needs_fix: response.translation_qa_summary?.needs_fix ?? 0,
      blocked: response.translation_qa_summary?.blocked ?? 0,
    };
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

function handleFilter(): void {
  void syncRouteAndLoad(1);
}

function handlePageChange(nextPage: number): void {
  void syncRouteAndLoad(nextPage);
}

function applyInboxFilter(status: TranslationQaStatus): void {
  qaStatusFilter.value = status;
  statusFilter.value = "";
  searchKeyword.value = "";
  sortFilter.value = "updated_at_desc";
  includeArchived.value = false;
  handleFilter();
}

function resetAdvancedFilters(): void {
  sortFilter.value = "updated_at_desc";
  includeArchived.value = false;
  handleFilter();
}

function clearQueueFilters(): void {
  qaStatusFilter.value = "";
  statusFilter.value = "";
  searchKeyword.value = "";
  sortFilter.value = "updated_at_desc";
  includeArchived.value = false;
  handleFilter();
}

function removeFilter(key: QueueFilterChipKey): void {
  if (key === "translation_qa_status") {
    qaStatusFilter.value = "";
  } else if (key === "status") {
    statusFilter.value = "";
  } else if (key === "q") {
    searchKeyword.value = "";
  } else if (key === "sort") {
    sortFilter.value = "updated_at_desc";
  } else if (key === "include_archived") {
    includeArchived.value = false;
  }
  handleFilter();
}

async function syncRouteAndLoad(nextPage: number, replace = false): Promise<void> {
  page.value = nextPage;
  const query = queueRouteQuery(nextPage);
  if (!isSameQueueRouteQuery(route.query, query)) {
    routeSyncInProgress = true;
    try {
      await router[replace ? "replace" : "push"]({ name: "translation-qa", query });
    } finally {
      routeSyncInProgress = false;
    }
  }
  await loadJobs();
}

function queueReturnQuery(): Record<string, string> {
  return {
    from: "translation-qa",
    ...queueRouteQuery(page.value, null),
  };
}

function translationQaRoute(job: DocumentJobResponse): RouteLocationRaw {
  return {
    name: "job-translation-qa",
    params: { jobId: job.id },
    query: queueReturnQuery(),
  };
}

function openTranslationQa(job: DocumentJobResponse): void {
  void openQaDrawer(job);
}

function openTranslationQaDetail(job: DocumentJobResponse): void {
  void router.push(translationQaRoute(job));
}

function openJobDetail(job: DocumentJobResponse): void {
  void router.push({ name: "job-detail", params: { jobId: job.id } });
}

function handleDrawerModelValue(nextValue: boolean): void {
  if (!nextValue) {
    void closeQaDrawer();
  }
}

function updateQaReviewForm(nextForm: TranslationQaReviewDraft): void {
  qaReviewForm.status = nextForm.status;
  qaReviewForm.issue_type = nextForm.issue_type;
  qaReviewForm.note = nextForm.note;
}

function syncQaReviewForm(nextQa: DocumentJobTranslationQaResponse): void {
  qaReviewForm.status = nextQa.qa.status;
  qaReviewForm.issue_type = nextQa.qa.issue_type;
  qaReviewForm.note = nextQa.qa.note || "";
}

function resetQaReviewForm(): void {
  qaReviewForm.status = "unreviewed";
  qaReviewForm.issue_type = null;
  qaReviewForm.note = "";
}

function setQaDrawerActiveSegment(index: number): void {
  const segmentCount = qaDrawerData.value?.segments.length || 0;
  if (!segmentCount) {
    qaDrawerActiveSegmentIndex.value = 0;
    return;
  }
  qaDrawerActiveSegmentIndex.value = Math.min(Math.max(index, 0), segmentCount - 1);
}

async function replaceQaJobQuery(qaJobId: string | null): Promise<void> {
  const query = queueRouteQuery(page.value, qaJobId);
  if (isSameQueueRouteQuery(route.query, query)) {
    return;
  }
  routeSyncInProgress = true;
  try {
    await router.replace({ name: "translation-qa", query });
  } finally {
    routeSyncInProgress = false;
  }
}

async function openQaDrawer(job: DocumentJobResponse): Promise<void> {
  selectedQaJobId.value = job.id;
  qaDrawerVisible.value = true;
  qaDrawerQueueCleared.value = false;
  qaDrawerJob.value = job;
  await replaceQaJobQuery(job.id);
  await loadQaDrawer(job.id, job);
}

function openQaDrawerFromRoute(jobId: string): void {
  selectedQaJobId.value = jobId;
  qaDrawerVisible.value = true;
  qaDrawerQueueCleared.value = false;
  const rowJob = jobs.value.find((job) => job.id === jobId) || null;
  void loadQaDrawer(jobId, rowJob);
}

async function loadQaDrawer(jobId: string, seedJob: DocumentJobResponse | null = null): Promise<void> {
  const loadToken = ++qaDrawerLoadToken;
  qaDrawerVisible.value = true;
  qaDrawerLoading.value = true;
  qaDrawerError.value = null;
  qaDrawerQueueCleared.value = false;
  qaDrawerActiveSegmentIndex.value = 0;
  try {
    const [jobResponse, qaResponse] = await Promise.all([
      seedJob ? Promise.resolve(seedJob) : documentJobsApi.get(jobId),
      documentJobsApi.getTranslationQa(jobId),
    ]);
    if (loadToken !== qaDrawerLoadToken || selectedQaJobId.value !== jobId) {
      return;
    }
    qaDrawerJob.value = jobResponse;
    qaDrawerData.value = qaResponse;
    syncQaReviewForm(qaResponse);
  } catch (caught) {
    if (loadToken === qaDrawerLoadToken && selectedQaJobId.value === jobId) {
      qaDrawerError.value = normalizeApiError(caught);
    }
  } finally {
    if (loadToken === qaDrawerLoadToken && selectedQaJobId.value === jobId) {
      qaDrawerLoading.value = false;
    }
  }
}

async function refreshQaDrawer(): Promise<void> {
  await loadJobs();
  if (qaDrawerQueueCleared.value) {
    return;
  }
  const jobId = selectedQaJobId.value;
  if (!jobId) {
    return;
  }
  const rowJob = jobs.value.find((job) => job.id === jobId) || qaDrawerJob.value;
  await loadQaDrawer(jobId, rowJob);
}

async function closeQaDrawer(): Promise<void> {
  qaDrawerLoadToken += 1;
  selectedQaJobId.value = "";
  qaDrawerVisible.value = false;
  qaDrawerLoading.value = false;
  qaDrawerSaving.value = false;
  qaDrawerError.value = null;
  qaDrawerJob.value = null;
  qaDrawerData.value = null;
  qaDrawerQueueCleared.value = false;
  qaDrawerActiveSegmentIndex.value = 0;
  resetQaReviewForm();
  await replaceQaJobQuery(null);
}

async function submitQaReviewOnly(): Promise<void> {
  await submitQaReview("stay");
}

async function submitQaReviewAndNext(): Promise<void> {
  await submitQaReview("next");
}

async function submitQaReview(mode: "stay" | "next"): Promise<void> {
  const jobId = selectedQaJobId.value;
  if (!jobId || !qaDrawerData.value?.available) {
    ElMessage.warning("当前任务没有可复核的 QA 证据，已保持只读。");
    return;
  }
  qaDrawerSaving.value = true;
  qaDrawerError.value = null;
  try {
    const response = await documentJobsApi.updateTranslationQa(jobId, {
      status: qaReviewForm.status,
      issue_type: qaReviewForm.issue_type,
      note: qaReviewForm.note || null,
    });
    qaDrawerJob.value = response.job;
    if (qaDrawerData.value) {
      qaDrawerData.value = { ...qaDrawerData.value, qa: response.qa };
    }
    ElMessage.success("翻译 QA 复核已保存。");
    await loadJobs();
    if (mode === "next") {
      await openNextQaDrawer(jobId);
    } else {
      await loadQaDrawer(jobId, response.job);
    }
  } catch (caught) {
    qaDrawerError.value = normalizeApiError(caught);
  } finally {
    qaDrawerSaving.value = false;
  }
}

async function openNextQaDrawer(currentJobId: string): Promise<void> {
  let nextJob = selectNextTranslationQaJob(jobs.value, currentJobId);
  if (!nextJob && page.value * pageSize < total.value) {
    await syncRouteAndLoad(page.value + 1, true);
    nextJob = selectNextTranslationQaJob(jobs.value, currentJobId);
  }
  if (nextJob) {
    await openQaDrawer(nextJob);
    return;
  }
  await showQaQueueClearedState();
}

async function showQaQueueClearedState(): Promise<void> {
  qaDrawerLoadToken += 1;
  selectedQaJobId.value = "";
  qaDrawerVisible.value = true;
  qaDrawerLoading.value = false;
  qaDrawerError.value = null;
  qaDrawerJob.value = null;
  qaDrawerData.value = null;
  qaDrawerQueueCleared.value = true;
  qaDrawerActiveSegmentIndex.value = 0;
  resetQaReviewForm();
  await replaceQaJobQuery(null);
}

function openSelectedTranslationQaDetail(): void {
  const jobId = selectedQaJobId.value || qaDrawerData.value?.job_id;
  if (!jobId) {
    return;
  }
  void router.push({
    name: "job-translation-qa",
    params: { jobId },
    query: queueReturnQuery(),
  });
}

function syncQaDrawerFromRoute(): void {
  const routeQaJobId = firstQueryValue(route.query.qa_job_id);
  if (!routeQaJobId) {
    if (selectedQaJobId.value && !qaDrawerQueueCleared.value) {
      void closeQaDrawer();
    }
    return;
  }
  if (routeQaJobId !== selectedQaJobId.value || !qaDrawerVisible.value) {
    openQaDrawerFromRoute(routeQaJobId);
  }
}

function handleQaDrawerKeydown(event: KeyboardEvent): void {
  if (!qaDrawerVisible.value || shouldIgnoreTranslationQaShortcut(event.target)) {
    return;
  }
  if (event.key === "Escape") {
    event.preventDefault();
    void closeQaDrawer();
    return;
  }
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    if (qaDrawerData.value?.available && !qaDrawerLoading.value && !qaDrawerSaving.value && !qaDrawerQueueCleared.value) {
      event.preventDefault();
      void submitQaReviewAndNext();
    }
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === "j") {
    event.preventDefault();
    setQaDrawerActiveSegment(qaDrawerActiveSegmentIndex.value + 1);
  } else if (key === "k") {
    event.preventDefault();
    setQaDrawerActiveSegment(qaDrawerActiveSegmentIndex.value - 1);
  }
}

function countQaStatus(status: TranslationQaStatus): number {
  return qaSummary.value[status] || 0;
}

function qaStatusLabel(job: DocumentJobResponse): string {
  return translationQaStatusText[job.translation_qa_status];
}

function qaStatusTagType(job: DocumentJobResponse): "success" | "warning" | "danger" | "info" {
  return translationQaStatusTagType(job.translation_qa_status);
}

function stageLabel(job: DocumentJobResponse): string {
  return jobStageText[job.stage] || job.stage;
}

function issueTypeLabel(issueType: TranslationQaIssueType | null): string {
  return issueType ? translationQaIssueTypeText[issueType] : "-";
}

watch(
  () => route.query,
  (nextQuery, previousQuery) => {
    applyRouteQueryFilters();
    if (!routeSyncInProgress && !isSameQueueFilterRouteQuery(nextQuery, previousQuery)) {
      void loadJobs();
    }
    if (!routeSyncInProgress) {
      syncQaDrawerFromRoute();
    }
  },
);

onMounted(() => {
  applyRouteQueryFilters();
  syncQaDrawerFromRoute();
  window.addEventListener("keydown", handleQaDrawerKeydown);
  void syncRouteAndLoad(page.value, true);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleQaDrawerKeydown);
});
</script>

<style scoped lang="scss">
.translation-qa-queue-page {
  display: grid;
  align-content: start;
  grid-auto-rows: max-content;
  gap: var(--app-space-3);
  animation: none;
  transform: none;
}

.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--app-space-4);
  padding: 14px var(--app-space-5);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-elevated);
  box-shadow: var(--app-shadow-subtle);
}

.page-heading .page-title {
  font-size: 24px;
}

.page-heading .page-description {
  margin-top: 6px;
}

.heading-actions,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--app-space-2);
}

.queue-sync {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.qa-inbox-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-3);
}

.qa-inbox-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--app-space-3);
  align-items: center;
  min-height: 64px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  text-align: left;
  box-shadow: var(--app-shadow-subtle);
  transition:
    border-color var(--app-motion-fast) ease-out,
    background-color var(--app-motion-fast) ease-out,
    box-shadow var(--app-motion-fast) ease-out;
}

.qa-inbox-item:hover,
.qa-inbox-item:focus-visible,
.qa-inbox-item.is-active {
  border-color: var(--app-color-primary-border);
  background: var(--app-color-primary-soft);
  box-shadow: var(--app-shadow-focus);
  outline: none;
}

.inbox-count {
  display: inline-grid;
  min-width: 38px;
  height: 38px;
  place-items: center;
  border-radius: var(--app-radius-md);
  font-size: 18px;
  font-weight: 800;
}

.qa-inbox-item.is-info .inbox-count {
  color: var(--app-color-info);
  background: var(--app-color-info-soft);
}

.qa-inbox-item.is-warning .inbox-count {
  color: var(--app-color-warning);
  background: var(--app-color-warning-soft);
}

.qa-inbox-item.is-danger .inbox-count {
  color: var(--app-color-danger);
  background: var(--app-color-danger-soft);
}

.qa-inbox-item.is-success .inbox-count {
  color: var(--app-color-success);
  background: var(--app-color-success-soft);
}

.inbox-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.inbox-copy strong,
.inbox-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inbox-copy strong {
  font-size: 14px;
}

.inbox-copy small {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.qa-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 240px;
  gap: var(--app-space-3);
  align-items: start;
}

.queue-panel {
  min-width: 0;
  border-color: var(--app-color-border);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.queue-panel:hover {
  border-color: var(--app-color-border);
  box-shadow: var(--app-shadow-subtle);
  transform: none;
}

.queue-panel :deep(.el-card__body) {
  padding: var(--app-space-4);
}

.table-header {
  align-items: flex-start;
}

.queue-search {
  width: 240px;
}

.queue-filter {
  width: 146px;
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
  gap: var(--app-space-3);
}

.advanced-filter-panel label {
  display: grid;
  gap: 6px;
}

.advanced-filter-panel label > span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.advanced-filter-footer,
.active-filter-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
}

.advanced-filter-footer {
  justify-content: space-between;
}

.active-filter-chips {
  margin-bottom: var(--app-space-3);
}

.queue-empty-state {
  display: grid;
  gap: var(--app-space-2);
  margin-bottom: var(--app-space-3);
  padding: var(--app-space-4);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
}

.queue-empty-state h3,
.queue-empty-state p {
  margin: 0;
}

.queue-empty-state h3 {
  color: var(--app-color-text);
  font-size: 16px;
}

.queue-empty-state p {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.table-scroll {
  overflow-x: auto;
  max-width: 100%;
}

.queue-table {
  min-width: 1060px;
  width: 100%;
}

.job-cell {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.job-link {
  color: var(--app-color-primary);
  font-weight: 700;
}

.job-link-button {
  display: inline;
  width: fit-content;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.job-link-button:hover,
.job-link-button:focus-visible {
  text-decoration: underline;
}

.filename {
  max-width: 100%;
  overflow: hidden;
  color: var(--app-color-text-muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.job-meta,
.status-cell,
.evidence-tags,
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.status-cell {
  align-items: flex-start;
  flex-direction: column;
}

.evidence-tags :deep(.el-tag) {
  border-color: var(--app-color-accent-cyan-border);
  background: var(--app-color-accent-cyan-soft);
}

.action-row :deep(.el-button + .el-button) {
  margin-left: 0;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--app-space-3);
}

.qa-processing-rail {
  position: sticky;
  top: 104px;
  display: grid;
  gap: var(--app-space-2);
  padding: var(--app-space-4);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-elevated);
  box-shadow: var(--app-shadow-subtle);
}

.qa-processing-rail strong {
  color: var(--app-color-text);
  font-size: 15px;
}

.qa-processing-rail span {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

:global(.translation-qa-review-drawer.el-drawer) {
  max-width: 100vw;
  background: var(--app-color-surface);
}

:global(.translation-qa-review-drawer .el-drawer__body) {
  height: 100%;
  padding: 0;
  overflow: hidden;
}

@media (max-width: 1180px) {
  .qa-workspace {
    grid-template-columns: 1fr;
  }

  .qa-processing-rail {
    position: static;
    grid-template-columns: repeat(4, auto);
    align-items: center;
  }
}

@media (max-width: 980px) {
  .qa-inbox-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .heading-actions,
  .toolbar {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  :global(.translation-qa-review-drawer.el-drawer) {
    width: 100vw !important;
  }

  .page-heading,
  .heading-actions,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .qa-inbox-strip {
    grid-template-columns: 1fr;
  }

  .toolbar,
  .queue-search,
  .queue-filter {
    width: 100%;
  }

  .queue-panel :deep(.el-card__body) {
    padding: var(--app-space-3);
  }

  .qa-processing-rail {
    grid-template-columns: 1fr;
  }
}
</style>
