<!-- frontend/src/pages/JobDetailPage.vue: Detail, events, polling, download, and retry view for one job. -->
<template>
  <div class="job-detail-page">
    <div class="section-header">
      <div>
        <h1 class="section-title">任务详情</h1>
        <p class="section-subtitle mono">{{ jobId }}</p>
      </div>
      <div class="toolbar">
        <el-button :icon="ArrowLeft" @click="$router.push('/jobs')">返回列表</el-button>
        <JobActions
          v-if="job"
          :job="job"
          :download-loading="downloadLoading"
          :retry-loading="retryLoading"
          :cancel-loading="cancelLoading"
          :archive-loading="archiveLoading"
          @refresh="loadAll"
          @download="handleDownload"
          @retry="handleRetry"
          @cancel="handleCancel"
          @archive="handleArchive"
        />
      </div>
    </div>

    <ApiErrorAlert :error="error" />

    <el-skeleton v-if="loading && !job" :rows="8" animated />

    <template v-else-if="job">
      <el-card class="page-section card-flat" shadow="never">
        <div class="detail-overview">
          <JobStatusBadge :status="job.status" />
          <JobProgress :status="job.status" :stage="job.stage" :progress="job.progress" />
        </div>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="模式">{{ jobModeText[job.mode] || job.mode }}</el-descriptions-item>
          <el-descriptions-item label="文档语言">{{ job.document_language }}</el-descriptions-item>
          <el-descriptions-item label="源 PDF">{{ sourceFilename }}</el-descriptions-item>
          <el-descriptions-item label="源文件 ID">{{ job.source_file_id }}</el-descriptions-item>
          <el-descriptions-item label="结果文件 ID">{{ job.result_file_id || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Term Rule Set">{{ boundTermRuleSetLabel }}</el-descriptions-item>
          <el-descriptions-item label="Translation Term Set">{{ boundTranslationTermSetLabel }}</el-descriptions-item>
          <el-descriptions-item label="legacy term_version_id">{{ job.term_version_id || "-" }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(job.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(job.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="重试次数">{{ job.retry_count }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(job.completed_at) }}</el-descriptions-item>
          <el-descriptions-item label="取消时间">{{ formatDateTime(job.canceled_at) }}</el-descriptions-item>
          <el-descriptions-item label="归档时间">{{ formatDateTime(job.archived_at) }}</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="runningNotice"
          class="state-alert"
          :type="runningNoticeType"
          :closable="false"
          show-icon
          :title="runningNotice"
        />
        <el-alert
          v-if="downloadHint"
          class="state-alert"
          type="success"
          :closable="false"
          show-icon
          :title="downloadHint"
        />
      </el-card>

      <el-card v-if="job.status === 'failed'" class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">失败信息</h2>
            <p class="section-subtitle">按后端返回展示，不在前端推断可重试原因。</p>
          </div>
        </div>
        <el-alert class="failure-summary" type="error" :closable="false" show-icon :title="failureSummary">
          <p>{{ failureHelpText }}</p>
          <p v-if="latestErrorEvent">
            最近错误事件：{{ latestErrorEvent.message }}
            <span v-if="latestErrorEvent.trace_id" class="mono">trace_id={{ latestErrorEvent.trace_id }}</span>
          </p>
        </el-alert>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="失败阶段">{{ job.failed_stage || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误码">{{ job.error_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">{{ job.error_message || "-" }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">文件和结果</h2>
            <p class="section-subtitle">任务绑定文件与生成产物。</p>
          </div>
          <el-button :icon="Refresh" :loading="filesLoading" @click="loadFiles">刷新文件</el-button>
        </div>
        <el-table v-loading="filesLoading" :data="files" empty-text="暂无已登记文件" class="job-file-table">
          <el-table-column label="角色" width="128">
            <template #default="{ row }">
              <el-tag size="small" :type="fileTagType(row.file_type)">{{ fileRoleText(row.file_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="文件名" min-width="220">
            <template #default="{ row }">
              <div class="file-name">{{ row.original_filename }}</div>
              <div class="file-meta mono">{{ row.id }}</div>
            </template>
          </el-table-column>
          <el-table-column label="类型" min-width="150">
            <template #default="{ row }">{{ fileTypeText(row.file_type) }}</template>
          </el-table-column>
          <el-table-column label="大小" width="110">
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="116">
            <template #default="{ row }">{{ fileAvailabilityText(row) }}</template>
          </el-table-column>
          <el-table-column label="过期时间" min-width="170">
            <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="108" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                :icon="Download"
                :disabled="!canDownloadFile(row)"
                :loading="downloadingFileId === row.id"
                @click="handleFileDownload(row)"
              >
                下载
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">请求快照</h2>
            <p class="section-subtitle">次级排障信息；主流程通常只需查看状态、失败信息和事件流。</p>
          </div>
        </div>
        <details class="snapshot-details">
          <summary>查看后端记录的非正文任务参数摘要</summary>
          <pre class="snapshot">{{ requestSnapshotPreview }}</pre>
        </details>
      </el-card>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">事件流</h2>
            <p class="section-subtitle">阶段事件和排障 trace 信息。</p>
          </div>
          <el-button :icon="Refresh" :loading="eventsLoading" @click="loadEvents">刷新事件</el-button>
        </div>
        <JobEventTimeline :events="events" />
      </el-card>

      <el-dialog v-model="retryDialogVisible" title="重试任务" width="640px">
        <el-form label-width="150px">
          <el-form-item label="任务 ID">
            <el-input :model-value="retryDialog.job?.id || ''" disabled />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="retryDialog.reason" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="retryDialogVisible = false">取消</el-button>
          <el-button type="warning" :loading="retryLoading" @click="submitRetryDialog">提交重试</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, Download, Refresh } from "@element-plus/icons-vue";
import { useRoute } from "vue-router";

import type {
  DocumentFileResponse,
  DocumentJobResourceSnapshot,
  DocumentJobEventResponse,
  DocumentJobResponse,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobActions from "@/components/JobActions.vue";
import JobEventTimeline from "@/components/JobEventTimeline.vue";
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import { formatBytes, formatDateTime, getJobSourceFilename, isActiveJobStatus, jobModeText } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const route = useRoute();
const jobId = computed(() => String(route.params.jobId || ""));
const job = ref<DocumentJobResponse | null>(null);
const events = ref<DocumentJobEventResponse[]>([]);
const files = ref<DocumentFileResponse[]>([]);
const loading = ref(false);
const eventsLoading = ref(false);
const filesLoading = ref(false);
const downloadLoading = ref(false);
const downloadingFileId = ref<string | null>(null);
const retryLoading = ref(false);
const cancelLoading = ref(false);
const archiveLoading = ref(false);
const retryDialogVisible = ref(false);
const error = ref<ApiClientError | null>(null);
let pollTimer: number | undefined;

const retryDialog = reactive({
  job: null as DocumentJobResponse | null,
  reason: "frontend retry",
});

const requestSnapshotPreview = computed(() => JSON.stringify(job.value?.request_snapshot || {}, null, 2));
const sourceFilename = computed(() => (job.value ? getJobSourceFilename(job.value) : "-"));
const resourceSnapshot = computed(() => readResourceSnapshot(job.value?.request_snapshot.resources));
const boundTermRuleSet = computed(() => resourceSnapshot.value?.term_rule_set || null);
const boundTranslationTermSet = computed(() => resourceSnapshot.value?.translation_term_set || null);
const boundTermRuleSetLabel = computed(() => {
  const bound = boundTermRuleSet.value;
  if (!bound) {
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    return versionLabel(readString(assets?.term_rule_set_id), readString(assets?.term_rule_set_version));
  }
  return `${bound.resource_id}@${bound.version}`;
});
const boundTranslationTermSetLabel = computed(() => {
  const bound = boundTranslationTermSet.value;
  if (!bound) {
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    const setId = readString(assets?.translation_term_set_id);
    const version = readString(assets?.translation_term_version) || job.value?.term_version_id || null;
    return versionLabel(setId, version);
  }
  return `${bound.set_id}@${bound.version}`;
});
const latestErrorEvent = computed(() => [...events.value].reverse().find((event) => event.level === "error") || null);
const failureSummary = computed(() => {
  if (!job.value) {
    return "任务处理失败。";
  }
  const stage = job.value.failed_stage || job.value.stage || "unknown";
  const code = job.value.error_code || "unknown";
  return `任务在 ${stage} 阶段失败，错误码 ${code}。`;
});
const failureHelpText = computed(() => {
  const code = job.value?.error_code || "";
  if (code === "document_job_invalid_input") {
    return "输入文件或任务参数不满足后端校验。请换一个 PDF 或联系管理员确认输入限制。";
  }
  if (job.value?.failed_stage === "parsing") {
    return "PDF 解析阶段失败。可先重试；如果仍失败，请把错误码和 trace_id 交给技术运营排查 MinerU 或文件内容问题。";
  }
  if (job.value?.failed_stage === "uploading") {
    return "结果保存阶段失败。通常与对象存储或文件登记有关，请重试后再联系技术运营。";
  }
  return "可以点击重试；如果后端返回 409，说明当前失败不可重试或次数已达上限，请按返回原因处理。";
});
const runningNotice = computed(() => {
  if (!job.value || !isActiveJobStatus(job.value.status)) {
    return "";
  }
  const timeoutAt = parseDate(job.value.timeout_at);
  if (timeoutAt && timeoutAt.getTime() <= Date.now()) {
    return "任务已超过预计超时时间，仍会继续轮询；请刷新事件流，必要时联系技术运营。";
  }
  const updatedAt = parseDate(job.value.updated_at);
  if (updatedAt && Date.now() - updatedAt.getTime() > 10 * 60 * 1000) {
    return "任务已超过 10 分钟没有状态更新，请查看事件流或稍后刷新。";
  }
  return "任务处理中，页面会自动轮询，终态后停止。";
});
const runningNoticeType = computed<"info" | "warning">(() => {
  if (!job.value || !isActiveJobStatus(job.value.status)) {
    return "info";
  }
  const timeoutAt = parseDate(job.value.timeout_at);
  const updatedAt = parseDate(job.value.updated_at);
  if ((timeoutAt && timeoutAt.getTime() <= Date.now()) || (updatedAt && Date.now() - updatedAt.getTime() > 10 * 60 * 1000)) {
    return "warning";
  }
  return "info";
});
const downloadHint = computed(() => {
  if (job.value?.status !== "succeeded") {
    return "";
  }
  return "结果已生成。点击下载会重新获取临时链接，链接失效后再次点击下载即可。";
});

function readRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readResourceSnapshot(value: unknown): DocumentJobResourceSnapshot | null {
  return readRecord(value) as DocumentJobResourceSnapshot | null;
}

function versionLabel(setId?: string | null, version?: string | null): string {
  const normalizedSetId = setId || "-";
  const normalizedVersion = version || "-";
  return normalizedSetId === "-" && normalizedVersion === "-" ? "-" : `${normalizedSetId}@${normalizedVersion}`;
}

function parseDate(value?: string | null): Date | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

async function loadJob(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    job.value = await documentJobsApi.get(jobId.value);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function loadEvents(): Promise<void> {
  eventsLoading.value = true;
  try {
    const response = await documentJobsApi.listEvents(jobId.value);
    events.value = response.items;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    eventsLoading.value = false;
  }
}

async function loadFiles(): Promise<void> {
  filesLoading.value = true;
  try {
    const response = await documentJobsApi.listFiles(jobId.value);
    files.value = response.files;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    filesLoading.value = false;
  }
}

async function loadAll(): Promise<void> {
  await loadJob();
  if (job.value) {
    await Promise.all([loadEvents(), loadFiles()]);
  } else {
    events.value = [];
    files.value = [];
  }
}

function openRetryDialog(target: DocumentJobResponse): void {
  retryDialog.job = target;
  retryDialog.reason = "frontend retry";
  retryDialogVisible.value = true;
}

function stopPolling(): void {
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

function syncPolling(): void {
  stopPolling();
  if (!job.value || !isActiveJobStatus(job.value.status) || document.hidden) {
    return;
  }
  pollTimer = window.setInterval(() => {
    void loadAll();
  }, 4000);
}

async function handleDownload(target: DocumentJobResponse): Promise<void> {
  downloadLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.createDownloadUrl(target.id);
    window.open(response.download_url, "_blank", "noopener");
    ElMessage.success(`下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    downloadLoading.value = false;
  }
}

async function handleFileDownload(file: DocumentFileResponse): Promise<void> {
  if (!job.value) {
    return;
  }
  downloadingFileId.value = file.id;
  error.value = null;
  try {
    const response = await documentJobsApi.createDownloadUrl(job.value.id, file.id);
    window.open(response.download_url, "_blank", "noopener");
    ElMessage.success(`下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    downloadingFileId.value = null;
  }
}

function handleRetry(target: DocumentJobResponse): void {
  openRetryDialog(target);
}

async function handleCancel(target: DocumentJobResponse): Promise<void> {
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
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
    return;
  }
  cancelLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.cancel(target.id);
    job.value = response.job;
    ElMessage.success("任务已取消。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    cancelLoading.value = false;
  }
}

async function handleArchive(target: DocumentJobResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      "归档只会把终态任务从默认列表隐藏，不会删除源文件、结果文件或事件记录。开启列表的“含归档”后仍可查看。",
      "归档任务",
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
  archiveLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.archive(target.id);
    job.value = response.job;
    ElMessage.success("任务已归档。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    archiveLoading.value = false;
  }
}

async function submitRetryDialog(): Promise<void> {
  if (!retryDialog.job) {
    return;
  }
  await submitRetry(retryDialog.job, { reason: retryDialog.reason || "frontend retry" });
  retryDialogVisible.value = false;
}

async function submitRetry(
  target: DocumentJobResponse,
  payload: Parameters<typeof documentJobsApi.retry>[1],
): Promise<void> {
  retryLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.retry(target.id, payload);
    job.value = response.job;
    ElMessage.success("已提交重试。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    retryLoading.value = false;
  }
}

function handleVisibilityChange(): void {
  syncPolling();
}

// 文件区只做展示映射；文件归属、过期和下载权限以后端校验为准。
function fileRoleText(fileType: string): string {
  if (fileType === "source_pdf") {
    return "源文件";
  }
  if (fileType === "generated_word") {
    return "结果";
  }
  if (fileType === "ai_call_log" || fileType === "ai_debug_archive") {
    return "日志";
  }
  return "中间产物";
}

function fileTypeText(fileType: string): string {
  const labels: Record<string, string> = {
    source_pdf: "源 PDF",
    generated_word: "生成 Word",
    mineru_raw_result: "MinerU 原始结果",
    document_ir: "DocumentIR",
    image_asset: "图片资产",
    ai_call_log: "AI 调用日志",
    ai_debug_archive: "AI debug 归档",
  };
  return labels[fileType] || fileType;
}

function fileTagType(fileType: string): "success" | "warning" | "info" {
  if (fileType === "generated_word") {
    return "success";
  }
  if (fileType === "ai_call_log" || fileType === "ai_debug_archive") {
    return "warning";
  }
  return "info";
}

function isFileExpired(file: DocumentFileResponse): boolean {
  const expiresAt = parseDate(file.expires_at);
  return Boolean(expiresAt && expiresAt.getTime() <= Date.now());
}

function canDownloadFile(file: DocumentFileResponse): boolean {
  return file.status === "uploaded" && !isFileExpired(file);
}

function fileAvailabilityText(file: DocumentFileResponse): string {
  if (file.status !== "uploaded") {
    return file.status;
  }
  if (isFileExpired(file)) {
    return "已过期";
  }
  return "可下载";
}

watch(() => job.value?.status, syncPolling);

onMounted(async () => {
  document.addEventListener("visibilitychange", handleVisibilityChange);
  await loadAll();
  syncPolling();
  if (route.query.retry === "1" && job.value?.status === "failed") {
    openRetryDialog(job.value);
  }
});

onBeforeUnmount(() => {
  stopPolling();
  document.removeEventListener("visibilitychange", handleVisibilityChange);
});
</script>

<style scoped lang="scss">
.detail-overview {
  display: grid;
  grid-template-columns: auto minmax(220px, 420px);
  gap: 18px;
  align-items: center;
  margin-bottom: 18px;
}

.state-alert {
  margin-top: 14px;
}

.failure-summary {
  margin-bottom: 14px;
}

.failure-summary p {
  margin: 4px 0 0;
}

.snapshot-details {
  color: #344054;
}

.snapshot-details summary {
  margin-bottom: 10px;
  cursor: pointer;
  font-weight: 600;
}

.snapshot {
  max-height: 260px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 6px;
  background: #f8fafc;
  color: #344054;
  font-size: 12px;
  line-height: 1.5;
}

.job-file-table {
  width: 100%;
}

.file-name {
  word-break: break-word;
  font-weight: 600;
  color: #1f2937;
}

.file-meta {
  margin-top: 3px;
  color: #667085;
  font-size: 12px;
  word-break: break-all;
}

@media (max-width: 760px) {
  .detail-overview {
    grid-template-columns: 1fr;
  }
}
</style>
