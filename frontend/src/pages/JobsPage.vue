<!-- File: frontend/src/pages/JobsPage.vue -->
<!-- Purpose: Render the document job workbench with upload, filtering, and batch actions. -->
<template>
  <main class="jobs-page" aria-labelledby="jobs-title">
    <section class="jobs-hero">
      <div class="hero-copy">
        <p class="hero-eyebrow">Document Jobs</p>
        <h1 id="jobs-title">转换任务工作台</h1>
        <p>上传 PDF、跟踪队列进度并下载 Word 结果。状态和异常会在这里集中呈现，便于连续处理交付任务。</p>
      </div>
      <div class="hero-actions">
        <div class="live-pill" :class="{ 'is-loading': loading }">
          <span aria-hidden="true"></span>
          <strong>{{ loading ? "同步中" : "已同步" }}</strong>
        </div>
        <el-button class="hero-refresh" :icon="Refresh" :loading="loading" @click="loadJobs">刷新任务</el-button>
      </div>
      <div class="hero-flow" aria-hidden="true">
        <span>PDF</span>
        <i></i>
        <span>队列</span>
        <i></i>
        <span>DOCX</span>
      </div>
    </section>

    <section class="metric-grid" aria-label="任务概览">
      <article v-for="metric in metrics" :key="metric.key" class="metric-card" :class="`metric-${metric.tone}`">
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

    <section class="jobs-workspace" aria-label="任务操作区">
      <PdfUploadPanel class="upload-panel" @created="handleCreated" />

      <section class="jobs-list-panel">
        <div class="section-header table-header">
          <div>
            <p class="table-kicker">当前视图：{{ activeFilterLabel }}</p>
            <h2 class="section-title">任务列表</h2>
            <p class="section-subtitle">查看当前账号可见的 document_jobs。</p>
          </div>
          <div class="toolbar">
            <el-input
              v-model="searchKeyword"
              clearable
              placeholder="搜索任务/文件/错误"
              style="width: 210px"
              @clear="handleFilter"
              @keyup.enter="handleFilter"
            />
            <el-select v-model="statusFilter" clearable placeholder="全部状态" style="width: 156px" @change="handleFilter">
              <el-option v-for="status in statuses" :key="status" :label="jobStatusText[status]" :value="status" />
            </el-select>
            <el-select
              v-model="qaStatusFilter"
              clearable
              placeholder="全部 QA"
              style="width: 156px"
              @change="handleFilter"
            >
              <el-option
                v-for="status in qaStatuses"
                :key="status"
                :label="translationQaStatusText[status]"
                :value="status"
              />
            </el-select>
            <el-select v-model="sortFilter" style="width: 156px" @change="handleFilter">
              <el-option v-for="option in sortOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <el-switch
              v-model="includeArchived"
              active-text="含归档"
              inactive-text="默认"
              @change="handleFilter"
            />
            <el-button :disabled="!selectedRetryableJobs.length" :loading="batchLoading" @click="handleBatchRetry">
              批量重试 {{ selectedRetryableJobs.length }}
            </el-button>
            <el-button :disabled="!selectedArchivableJobs.length" :loading="batchLoading" @click="handleBatchArchive">
              批量归档 {{ selectedArchivableJobs.length }}
            </el-button>
            <el-button :icon="Refresh" :loading="loading" @click="handleFilter">搜索</el-button>
            <el-button :icon="Refresh" :loading="loading" @click="loadJobs">刷新</el-button>
          </div>
        </div>

        <ApiErrorAlert :error="error" />

        <div v-if="summaryEntries.length" class="summary-row" aria-label="状态汇总">
          <el-tag v-for="[status, count] in summaryEntries" :key="status" effect="plain">
            {{ statusLabel(status) }}: {{ count }}
          </el-tag>
        </div>

        <el-card class="jobs-table-card card-flat" shadow="never">
          <JobTable
            :jobs="jobs"
            :loading="loading"
            :page="page"
            :page-size="pageSize"
            :total="total"
            @page-change="handlePageChange"
            @selection-change="handleSelectionChange"
            @download="handleDownload"
            @retry="handleRetry"
            @cancel="handleCancel"
            @archive="handleArchive"
          />
        </el-card>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { CircleCheck, Files, Refresh, Timer, Warning } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import type { DocumentJobListSort, DocumentJobResponse, DocumentJobStatus, TranslationQaStatus } from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobTable from "@/components/JobTable.vue";
import PdfUploadPanel from "@/components/PdfUploadPanel.vue";
import {
  canArchiveDocumentJob,
  canRetryDocumentJob,
  formatDateTime,
  jobStatusText,
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
const statusFilter = ref<DocumentJobStatus | "">("");
const qaStatusFilter = ref<TranslationQaStatus | "">("");
const searchKeyword = ref("");
const sortFilter = ref<DocumentJobListSort>("created_at_desc");
const includeArchived = ref(false);
const selectedJobs = ref<DocumentJobResponse[]>([]);
const batchLoading = ref(false);
const summary = ref<Record<string, number>>({});
const statuses: DocumentJobStatus[] = ["pending", "queued", "running", "succeeded", "failed", "canceled"];
const qaStatuses: TranslationQaStatus[] = ["unreviewed", "approved", "needs_fix", "blocked"];
const sortOptions: Array<{ label: string; value: DocumentJobListSort }> = [
  { label: "创建时间新到旧", value: "created_at_desc" },
  { label: "创建时间旧到新", value: "created_at_asc" },
  { label: "更新时间新到旧", value: "updated_at_desc" },
  { label: "更新时间旧到新", value: "updated_at_asc" },
];

const summaryEntries = computed(() => Object.entries(summary.value).filter(([, count]) => count > 0));
const activeFilterLabel = computed(() => {
  const statusText = statusFilter.value ? statusLabel(statusFilter.value) : "全部状态";
  const qaText = qaStatusFilter.value ? `QA ${translationQaStatusText[qaStatusFilter.value]}` : "全部 QA";
  const archiveText = includeArchived.value ? "含归档" : "默认";
  return `${statusText} · ${qaText} · ${archiveText}`;
});
const activeCount = computed(
  () => countByStatus("pending") + countByStatus("queued") + countByStatus("running"),
);
const selectedRetryableJobs = computed(() => selectedJobs.value.filter(canRetryDocumentJob));
const selectedArchivableJobs = computed(() => selectedJobs.value.filter(canArchiveDocumentJob));
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

async function loadJobs(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.list({
      page: page.value,
      page_size: pageSize,
      status: statusFilter.value || undefined,
      translation_qa_status: qaStatusFilter.value || undefined,
      q: searchKeyword.value.trim() || undefined,
      sort: sortFilter.value,
      include_archived: includeArchived.value,
    });
    jobs.value = response.items;
    selectedJobs.value = [];
    total.value = response.total;
    summary.value = response.summary;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

function handlePageChange(nextPage: number): void {
  page.value = nextPage;
  void loadJobs();
}

function handleFilter(): void {
  page.value = 1;
  void loadJobs();
}

function handleSelectionChange(selection: DocumentJobResponse[]): void {
  selectedJobs.value = selection;
}

function statusLabel(status: string): string {
  return jobStatusText[status as DocumentJobStatus] || status;
}

function countByStatus(status: DocumentJobStatus): number {
  return summary.value[status] || 0;
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

// 校验路由中的 QA 状态筛选值，避免把非法 query 传给后端。
function isTranslationQaStatus(value: string): value is TranslationQaStatus {
  return qaStatuses.includes(value as TranslationQaStatus);
}

function applyRouteQueryFilters(): void {
  const nextStatus = firstQueryValue(route.query.status);
  const nextSort = firstQueryValue(route.query.sort);
  const nextQaStatus = firstQueryValue(route.query.translation_qa_status);
  if (isDocumentJobStatus(nextStatus)) {
    statusFilter.value = nextStatus;
  }
  if (isTranslationQaStatus(nextQaStatus)) {
    qaStatusFilter.value = nextQaStatus;
  }
  if (isDocumentJobSort(nextSort)) {
    sortFilter.value = nextSort;
  }
  includeArchived.value = firstQueryValue(route.query.include_archived) === "true";
}

function handleCreated(jobId: string): void {
  void router.push(`/jobs/${jobId}`);
}

async function handleDownload(job: DocumentJobResponse): Promise<void> {
  try {
    const response = await documentJobsApi.createDownloadUrl(job.id);
    window.open(response.download_url, "_blank", "noopener");
    ElMessage.success(`下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function handleRetry(job: DocumentJobResponse): Promise<void> {
  await router.push({ path: `/jobs/${job.id}`, query: { retry: "1" } });
}

async function handleCancel(job: DocumentJobResponse): Promise<void> {
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
    await documentJobsApi.cancel(job.id);
    ElMessage.success("任务已取消。");
    await loadJobs();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
  }
}

async function handleArchive(job: DocumentJobResponse): Promise<void> {
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
    await documentJobsApi.archive(job.id);
    ElMessage.success("任务已归档。");
    await loadJobs();
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
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
    showBatchResult("批量重试", response.succeeded, response.failed);
    await loadJobs();
  } catch (caught) {
    error.value = normalizeApiError(caught);
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
    showBatchResult("批量归档", response.succeeded, response.failed);
    await loadJobs();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    batchLoading.value = false;
  }
}

// 用后端聚合结果展示批量操作的成功和失败数量。
function showBatchResult(label: string, succeeded: number, failed: number): void {
  if (failed > 0) {
    ElMessage.warning(`${label}完成：成功 ${succeeded} 个，失败 ${failed} 个。`);
    return;
  }
  ElMessage.success(`${label}完成：成功 ${succeeded} 个。`);
}

onMounted(() => {
  applyRouteQueryFilters();
  void loadJobs();
});
</script>

<style scoped lang="scss">
.jobs-page {
  --jobs-bg: #eef4ff;
  --jobs-bg-soft: #f8fbff;
  --jobs-surface: rgba(255, 255, 255, 0.78);
  --jobs-surface-solid: #ffffff;
  --jobs-surface-muted: rgba(241, 245, 249, 0.82);
  --jobs-border: rgba(79, 70, 229, 0.14);
  --jobs-border-strong: rgba(15, 23, 42, 0.12);
  --jobs-text: #111827;
  --jobs-muted: #5f6b82;
  --jobs-faint: #8190a8;
  --jobs-primary: #4f46e5;
  --jobs-cyan: #0891b2;
  --jobs-green: #0f9f75;
  --jobs-amber: #b7791f;
  --jobs-danger: #b42318;
  --jobs-shadow: 0 22px 70px rgba(49, 46, 129, 0.14);
  --jobs-shadow-soft: 0 14px 36px rgba(15, 23, 42, 0.08);

  position: relative;
  min-height: calc(100vh - 114px);
  margin: -20px -24px -36px;
  padding: 28px 24px 42px;
  overflow: hidden;
  color: var(--jobs-text);
  background:
    linear-gradient(135deg, rgba(79, 70, 229, 0.11), rgba(8, 145, 178, 0.09) 38%, transparent 72%),
    linear-gradient(160deg, var(--jobs-bg), var(--jobs-bg-soft));
  color-scheme: light;
}

.jobs-page::before,
.jobs-page::after {
  position: absolute;
  z-index: 0;
  content: "";
  pointer-events: none;
}

.jobs-page::before {
  inset: 0;
  background-image:
    linear-gradient(rgba(79, 70, 229, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(8, 145, 178, 0.08) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: linear-gradient(130deg, #000 0%, transparent 76%);
  opacity: 0.52;
}

.jobs-page::after {
  top: -180px;
  right: -140px;
  width: min(56vw, 680px);
  height: min(56vw, 680px);
  background:
    linear-gradient(135deg, rgba(79, 70, 229, 0.18), rgba(15, 159, 117, 0.08)),
    linear-gradient(45deg, transparent 0 44%, rgba(255, 255, 255, 0.36) 44% 48%, transparent 48% 100%);
  clip-path: polygon(16% 0, 100% 8%, 88% 72%, 42% 100%, 0 50%);
  filter: blur(1px);
  opacity: 0.82;
  animation: panel-enter 520ms ease-out both;
}

.jobs-hero,
.metric-grid,
.jobs-workspace {
  position: relative;
  z-index: 1;
  width: min(1220px, 100%);
  margin-right: auto;
  margin-left: auto;
}

.jobs-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px 28px;
  align-items: start;
  min-height: 190px;
  padding: 28px;
  border: 1px solid var(--jobs-border);
  border-radius: 8px;
  background: var(--jobs-surface);
  box-shadow: var(--jobs-shadow);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  animation: fade-up 360ms ease-out both;
}

.hero-copy {
  max-width: 720px;
}

.hero-eyebrow,
.table-kicker {
  margin: 0 0 10px;
  color: var(--jobs-green);
  font-size: 13px;
  font-weight: 760;
}

.hero-copy h1 {
  margin: 0 0 14px;
  color: var(--jobs-text);
  font-size: clamp(34px, 4vw, 54px);
  font-weight: 780;
  line-height: 1.08;
}

.hero-copy p:last-child {
  max-width: 640px;
  margin: 0;
  color: var(--jobs-muted);
  font-size: 16px;
  line-height: 1.75;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.live-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid rgba(15, 159, 117, 0.22);
  border-radius: 8px;
  background: rgba(15, 159, 117, 0.08);
  color: var(--jobs-green);
  font-size: 13px;
}

.live-pill span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 4px rgba(15, 159, 117, 0.12);
}

.live-pill.is-loading span {
  color: var(--jobs-primary);
}

.hero-refresh {
  min-height: 38px;
  border-color: var(--jobs-border);
  border-radius: 8px;
  background: var(--jobs-surface-solid);
  color: var(--jobs-text);
}

.hero-flow {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: auto minmax(50px, 1fr) auto minmax(50px, 1fr) auto;
  gap: 12px;
  align-items: center;
  max-width: 540px;
  margin-top: 16px;
}

.hero-flow span {
  display: inline-grid;
  min-width: 76px;
  height: 40px;
  place-items: center;
  border: 1px solid var(--jobs-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.66);
  color: var(--jobs-text);
  font-size: 13px;
  font-weight: 800;
}

.hero-flow i {
  position: relative;
  height: 2px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.16);
}

.hero-flow i::after {
  position: absolute;
  inset: 0;
  content: "";
  border-radius: inherit;
  background: linear-gradient(90deg, var(--jobs-primary), var(--jobs-green));
  transform: translateX(-100%);
  animation: line-fill 620ms ease-out 180ms both;
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
  min-height: 112px;
  padding: 18px;
  border: 1px solid var(--jobs-border);
  border-radius: 8px;
  background: var(--jobs-surface);
  box-shadow: var(--jobs-shadow-soft);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  animation: fade-up 360ms ease-out both;
}

.metric-card:nth-child(2) {
  animation-delay: 40ms;
}

.metric-card:nth-child(3) {
  animation-delay: 80ms;
}

.metric-card:nth-child(4) {
  animation-delay: 120ms;
}

.metric-icon {
  display: inline-grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 8px;
  background: rgba(79, 70, 229, 0.1);
  color: var(--jobs-primary);
  font-size: 20px;
}

.metric-card span:not(.metric-icon) {
  display: block;
  color: var(--jobs-muted);
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin: 4px 0;
  color: var(--jobs-text);
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
}

.metric-card em {
  color: var(--jobs-faint);
  font-size: 12px;
  font-style: normal;
}

.metric-green .metric-icon {
  background: rgba(15, 159, 117, 0.11);
  color: var(--jobs-green);
}

.metric-amber .metric-icon {
  background: rgba(183, 121, 31, 0.12);
  color: var(--jobs-amber);
}

.metric-indigo .metric-icon {
  background: rgba(8, 145, 178, 0.11);
  color: var(--jobs-cyan);
}

.jobs-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
  margin-top: 16px;
}

.upload-panel,
.jobs-list-panel {
  min-width: 0;
}

.jobs-list-panel {
  padding: 18px;
  border: 1px solid var(--jobs-border);
  border-radius: 8px;
  background: var(--jobs-surface);
  box-shadow: var(--jobs-shadow-soft);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  animation: fade-up 360ms ease-out 80ms both;
}

.table-header {
  align-items: flex-start;
  margin-bottom: 14px;
}

.section-title {
  color: var(--jobs-text);
  font-size: 20px;
}

.section-subtitle {
  color: var(--jobs-muted);
}

.summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.jobs-table-card {
  overflow: hidden;
  border: 1px solid var(--jobs-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.66);
}

.jobs-page :deep(.upload-card) {
  height: 100%;
  border: 1px solid var(--jobs-border);
  border-radius: 8px;
  background: var(--jobs-surface);
  box-shadow: var(--jobs-shadow-soft);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  animation: fade-up 360ms ease-out 40ms both;
}

.jobs-page :deep(.upload-card .el-card__body),
.jobs-table-card :deep(.el-card__body) {
  padding: 20px;
}

.jobs-page :deep(.upload-card .section-title) {
  color: var(--jobs-text);
}

.jobs-page :deep(.upload-card .section-subtitle),
.jobs-page :deep(.upload-footer .muted),
.jobs-page :deep(.mode-label) {
  color: var(--jobs-muted);
}

.jobs-page :deep(.el-upload-dragger) {
  border-color: var(--jobs-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(15, 159, 117, 0.06)),
    var(--jobs-surface-muted);
  transition:
    border-color 180ms ease-out,
    box-shadow 180ms ease-out,
    background-color 180ms ease-out;
}

.jobs-page :deep(.el-upload-dragger:hover) {
  border-color: rgba(79, 70, 229, 0.44);
  box-shadow: 0 12px 28px rgba(79, 70, 229, 0.12);
}

.jobs-page :deep(.el-upload__text),
.jobs-page :deep(.el-upload__tip) {
  color: var(--jobs-muted);
}

.jobs-page :deep(.el-icon--upload) {
  color: var(--jobs-primary);
}

.jobs-page :deep(.el-button) {
  border-radius: 8px;
}

.jobs-page :deep(.el-button--primary) {
  border: 0;
  background: linear-gradient(135deg, var(--jobs-primary), var(--jobs-green));
  box-shadow: 0 14px 28px rgba(15, 159, 117, 0.18);
}

.jobs-page :deep(.el-select__wrapper),
.jobs-page :deep(.el-input__wrapper) {
  border-radius: 8px;
  background: var(--jobs-surface-solid);
  box-shadow: 0 0 0 1px var(--jobs-border) inset;
}

.jobs-page :deep(.el-select__placeholder),
.jobs-page :deep(.el-select__selected-item),
.jobs-page :deep(.el-input__inner) {
  color: var(--jobs-text);
}

.jobs-page :deep(.el-tag) {
  border-color: var(--jobs-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
}

.jobs-table-card :deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(241, 245, 249, 0.74);
  --el-table-row-hover-bg-color: rgba(79, 70, 229, 0.08);
  --el-table-border-color: rgba(79, 70, 229, 0.12);
  --el-table-text-color: var(--jobs-text);
  --el-table-header-text-color: var(--jobs-muted);

  color: var(--jobs-text);
  background: transparent;
}

.jobs-table-card :deep(.el-table__inner-wrapper::before) {
  background: var(--jobs-border);
}

.jobs-table-card :deep(.el-table th.el-table__cell) {
  font-weight: 760;
}

.jobs-table-card :deep(.el-table td.el-table__cell),
.jobs-table-card :deep(.el-table th.el-table__cell) {
  border-bottom-color: var(--jobs-border);
}

.jobs-table-card :deep(.el-table__fixed-right::before),
.jobs-table-card :deep(.el-table__fixed::before) {
  background: var(--jobs-border);
}

.jobs-table-card :deep(.mono) {
  color: var(--jobs-primary);
}

.jobs-table-card :deep(.muted) {
  color: var(--jobs-faint);
}

.jobs-table-card :deep(.error-code) {
  color: var(--jobs-danger);
}

.jobs-table-card :deep(.el-pagination.is-background .btn-prev),
.jobs-table-card :deep(.el-pagination.is-background .btn-next),
.jobs-table-card :deep(.el-pagination.is-background .el-pager li) {
  border-radius: 8px;
  background: var(--jobs-surface-muted);
  color: var(--jobs-text);
}

.jobs-table-card :deep(.el-pagination.is-background .el-pager li.is-active) {
  background: var(--jobs-primary);
  color: #ffffff;
}

@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(14px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes line-fill {
  to {
    transform: translateX(0);
  }
}

@keyframes panel-enter {
  from {
    opacity: 0;
    transform: translate3d(22px, -16px, 0) rotate(2deg);
  }

  to {
    opacity: 0.82;
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
}

@media (prefers-color-scheme: dark) {
  .jobs-page {
    --jobs-bg: #050711;
    --jobs-bg-soft: #0b1020;
    --jobs-surface: rgba(10, 16, 32, 0.74);
    --jobs-surface-solid: rgba(15, 23, 42, 0.92);
    --jobs-surface-muted: rgba(15, 23, 42, 0.66);
    --jobs-border: rgba(148, 163, 184, 0.18);
    --jobs-border-strong: rgba(148, 163, 184, 0.24);
    --jobs-text: #f8fafc;
    --jobs-muted: #aab6ca;
    --jobs-faint: #8391aa;
    --jobs-primary: #818cf8;
    --jobs-cyan: #22d3ee;
    --jobs-green: #34d399;
    --jobs-amber: #f5c451;
    --jobs-danger: #fb7185;
    --jobs-shadow: 0 24px 80px rgba(0, 0, 0, 0.38);
    --jobs-shadow-soft: 0 16px 42px rgba(0, 0, 0, 0.26);

    background:
      linear-gradient(135deg, rgba(129, 140, 248, 0.17), rgba(34, 211, 238, 0.09) 36%, transparent 74%),
      linear-gradient(160deg, var(--jobs-bg), var(--jobs-bg-soft));
    color-scheme: dark;
  }

  .jobs-page::before {
    background-image:
      linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
      linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
    opacity: 0.4;
  }

  .hero-flow span,
  .jobs-table-card {
    background: rgba(15, 23, 42, 0.64);
  }

  .jobs-page :deep(.el-upload-dragger) {
    background:
      linear-gradient(135deg, rgba(129, 140, 248, 0.1), rgba(52, 211, 153, 0.06)),
      rgba(15, 23, 42, 0.58);
  }

  .jobs-page :deep(.el-tag) {
    background: rgba(15, 23, 42, 0.62);
  }

  .jobs-table-card :deep(.el-table) {
    --el-table-header-bg-color: rgba(15, 23, 42, 0.72);
    --el-table-row-hover-bg-color: rgba(129, 140, 248, 0.12);
  }
}

@media (max-width: 1500px) {
  .jobs-workspace {
    grid-template-columns: 1fr;
  }

  .jobs-list-panel {
    grid-column: auto;
  }
}

@media (max-width: 1080px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .jobs-page {
    margin: -16px -16px -36px;
    padding: 18px 12px 30px;
  }

  .jobs-hero {
    grid-template-columns: 1fr;
    padding: 20px;
  }

  .hero-actions {
    flex-wrap: wrap;
  }

  .hero-flow {
    grid-template-columns: 1fr;
    gap: 8px;
    max-width: none;
  }

  .hero-flow i {
    width: 2px;
    height: 22px;
    justify-self: center;
  }

  .hero-flow i::after {
    transform: translateY(-100%);
    animation-name: line-fill-y;
  }

  .metric-grid,
  .jobs-workspace {
    grid-template-columns: 1fr;
  }

  .table-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .toolbar {
    width: 100%;
  }
}

@keyframes line-fill-y {
  to {
    transform: translateY(0);
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

  .jobs-page :deep(.upload-card .el-card__body),
  .jobs-table-card :deep(.el-card__body) {
    padding: 16px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .jobs-page::after,
  .jobs-hero,
  .jobs-list-panel,
  .metric-card,
  .jobs-page :deep(.upload-card),
  .hero-flow i::after {
    animation: none;
  }

  .jobs-page :deep(.el-upload-dragger),
  .jobs-page :deep(.el-button) {
    transition: none;
  }
}
</style>
