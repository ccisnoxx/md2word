<!-- File: frontend/src/pages/TranslationQaQueuePage.vue -->
<!-- Purpose: Render the translation QA review queue backed by document_jobs list filtering. -->
<template>
  <main class="translation-qa-queue-page app-page" aria-labelledby="translation-qa-queue-title">
    <section class="page-heading app-page-header app-page-shell">
      <div>
        <p class="page-kicker">Translation QA</p>
        <h1 id="translation-qa-queue-title" class="page-title">翻译 QA 队列</h1>
        <p class="page-description">集中复核英文 PDF 翻译任务的证据、结论和术语反馈入口。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadJobs">刷新</el-button>
      </div>
    </section>

    <section class="qa-metric-grid app-metric-grid app-page-shell" aria-label="翻译 QA 队列概览">
      <article class="app-metric-card">
        <span>当前筛选</span>
        <strong>{{ total }}</strong>
        <small>{{ activeFilterLabel }}</small>
      </article>
      <article class="app-metric-card">
        <span>本页任务</span>
        <strong>{{ jobs.length }}</strong>
        <small>当前页返回数量</small>
      </article>
      <article class="app-metric-card">
        <span>未复核</span>
        <strong>{{ countQaStatus("unreviewed") }}</strong>
        <small>除 QA 状态外的当前筛选</small>
      </article>
      <article class="app-metric-card">
        <span>需处理</span>
        <strong>{{ countQaStatus("needs_fix") + countQaStatus("blocked") }}</strong>
        <small>除 QA 状态外的当前筛选</small>
      </article>
    </section>

    <el-card class="card-flat queue-panel app-panel-card app-table-card app-page-shell" shadow="never">
      <div class="section-header table-header">
        <div>
          <h2 class="section-title">复核列表</h2>
          <p class="section-subtitle">首版复用 document-jobs 列表接口，不读取全文 prompt / response。</p>
        </div>
        <div class="toolbar">
          <el-input
            v-model="searchKeyword"
            clearable
            placeholder="搜索任务/文件/错误"
            style="width: 220px"
            @clear="handleFilter"
            @keyup.enter="handleFilter"
          />
          <el-select v-model="qaStatusFilter" clearable placeholder="全部 QA" style="width: 150px" @change="handleFilter">
            <el-option
              v-for="status in qaStatuses"
              :key="status"
              :label="translationQaStatusText[status]"
              :value="status"
            />
          </el-select>
          <el-select v-model="statusFilter" clearable placeholder="全部任务状态" style="width: 156px" @change="handleFilter">
            <el-option v-for="status in statuses" :key="status" :label="jobStatusText[status]" :value="status" />
          </el-select>
          <el-select v-model="sortFilter" style="width: 160px" @change="handleFilter">
            <el-option v-for="option in sortOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <el-switch
            v-model="includeArchived"
            active-text="含归档"
            inactive-text="默认"
            @change="handleFilter"
          />
          <el-button :icon="Search" :loading="loading" @click="handleFilter">搜索</el-button>
        </div>
      </div>

      <ApiErrorAlert :error="error" />

      <el-table v-loading="loading" :data="jobs" border class="queue-table" :empty-text="emptyText">
        <el-table-column label="任务" min-width="190">
          <template #default="{ row }">
            <router-link class="mono job-link" :to="translationQaRoute(row)">{{ row.id }}</router-link>
            <div class="filename" :title="getJobSourceFilename(row)">{{ getJobSourceFilename(row) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="任务状态" min-width="150">
          <template #default="{ row }">
            <JobStatusBadge :status="row.status" />
            <div class="muted">{{ row.stage }}</div>
          </template>
        </el-table-column>
        <el-table-column label="QA 状态" min-width="132">
          <template #default="{ row }">
            <el-tag :type="qaStatusTagType(row)" effect="plain">
              {{ qaStatusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="问题归因" min-width="126">
          <template #default="{ row }">
            {{ issueTypeLabel(row.translation_qa_issue_type) }}
          </template>
        </el-table-column>
        <el-table-column label="证据提示" min-width="210">
          <template #default="{ row }">
            <div class="evidence-tags">
              <el-tag size="small" :type="row.document_ir_file_id ? 'success' : 'info'" effect="plain">DocumentIR</el-tag>
              <el-tag size="small" :type="row.result_file_id ? 'success' : 'info'" effect="plain">DOCX</el-tag>
              <el-tag size="small" :type="row.debug_full_text_enabled ? 'success' : 'info'" effect="plain">Debug</el-tag>
              <el-tag v-if="row.error_code" size="small" type="danger" effect="plain">{{ row.error_code }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="复核人" min-width="155">
          <template #default="{ row }">
            <div>{{ row.translation_qa_reviewed_by || "-" }}</div>
            <div class="muted">{{ formatDateTime(row.translation_qa_reviewed_at) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="155">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="132" fixed="right">
          <template #default="{ row }">
            <div class="action-row">
              <el-button size="small" text type="primary" @click="openTranslationQa(row)">复核</el-button>
              <el-button size="small" text @click="openJobDetail(row)">任务详情</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

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
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { Refresh, Search } from "@element-plus/icons-vue";
import { useRoute, useRouter, type LocationQuery, type RouteLocationRaw } from "vue-router";

import { documentJobsApi } from "@/api/documentJobs";
import type {
  DocumentJobListSort,
  DocumentJobResponse,
  DocumentJobStatus,
  TranslationQaIssueType,
  TranslationQaStatus,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import {
  formatDateTime,
  getJobSourceFilename,
  jobStatusText,
  translationQaStatusTagType,
  translationQaStatusText,
} from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

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

const qaStatuses: TranslationQaStatus[] = ["unreviewed", "approved", "needs_fix", "blocked"];
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
const qaIssueTypeText: Record<TranslationQaIssueType, string> = {
  translation: "翻译问题",
  terminology: "术语问题",
  layout: "版式问题",
  source_quality: "源文件质量",
  artifact_missing: "证据缺失",
  other: "其他",
};

const activeFilterLabel = computed(() => {
  const qaText = qaStatusFilter.value ? translationQaStatusText[qaStatusFilter.value] : "全部 QA";
  const statusText = statusFilter.value ? jobStatusText[statusFilter.value] : "全部任务状态";
  return `${qaText} · ${statusText}`;
});
const emptyText = computed(() => (loading.value ? "加载中" : "当前筛选下暂无翻译 QA 任务"));

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

function queueRouteQuery(nextPage = page.value): Record<string, string> {
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
  return query;
}

function isSameQueueRouteQuery(candidate: LocationQuery, expected: Record<string, string>): boolean {
  const keys = ["translation_qa_status", "status", "sort", "include_archived", "q", "page"];
  return keys.every((key) => firstQueryValue(candidate[key]) === (expected[key] ?? ""));
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

async function syncRouteAndLoad(nextPage: number, replace = false): Promise<void> {
  page.value = nextPage;
  const query = queueRouteQuery(nextPage);
  if (!isSameQueueRouteQuery(route.query, query)) {
    await router[replace ? "replace" : "push"]({ name: "translation-qa", query });
    return;
  }
  await loadJobs();
}

function queueReturnQuery(): Record<string, string> {
  return {
    from: "translation-qa",
    ...queueRouteQuery(page.value),
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
  void router.push(translationQaRoute(job));
}

function openJobDetail(job: DocumentJobResponse): void {
  void router.push({ name: "job-detail", params: { jobId: job.id } });
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

function issueTypeLabel(issueType: TranslationQaIssueType | null): string {
  return issueType ? qaIssueTypeText[issueType] : "-";
}

watch(
  () => route.query,
  () => {
    applyRouteQueryFilters();
    void loadJobs();
  },
);

onMounted(() => {
  applyRouteQueryFilters();
  void syncRouteAndLoad(page.value, true);
});
</script>

<style scoped lang="scss">
.translation-qa-queue-page {
  display: grid;
  gap: var(--app-space-4);
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--app-space-4);
}

.heading-actions,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
}

.qa-metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.queue-panel {
  min-width: 0;
}

.table-header {
  align-items: flex-start;
}

.queue-table {
  width: 100%;
}

.job-link {
  color: var(--app-color-primary);
  font-weight: 650;
}

.filename {
  max-width: 100%;
  margin-top: 4px;
  overflow: hidden;
  color: var(--app-color-text-muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.evidence-tags,
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-row :deep(.el-button + .el-button) {
  margin-left: 0;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

@media (max-width: 980px) {
  .qa-metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .heading-actions,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .qa-metric-grid {
    grid-template-columns: 1fr;
  }

  .toolbar :deep(.el-input),
  .toolbar :deep(.el-select) {
    width: 100% !important;
  }
}
</style>
