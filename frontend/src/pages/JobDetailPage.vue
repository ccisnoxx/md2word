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
          @refresh="loadAll"
          @download="handleDownload"
          @retry="handleRetry"
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
          <el-descriptions-item label="源文件 ID">{{ job.source_file_id }}</el-descriptions-item>
          <el-descriptions-item label="结果文件 ID">{{ job.result_file_id || "-" }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(job.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(job.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="重试次数">{{ job.retry_count }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(job.completed_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card v-if="job.status === 'failed'" class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">失败信息</h2>
            <p class="section-subtitle">按后端返回展示，不在前端推断可重试原因。</p>
          </div>
        </div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="失败阶段">{{ job.failed_stage || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误码">{{ job.error_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">{{ job.error_message || "-" }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">请求快照</h2>
            <p class="section-subtitle">后端记录的非正文任务参数摘要。</p>
          </div>
        </div>
        <pre class="snapshot">{{ requestSnapshotPreview }}</pre>
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { ArrowLeft, Refresh } from "@element-plus/icons-vue";
import { useRoute } from "vue-router";

import type { DocumentJobEventResponse, DocumentJobResponse } from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobActions from "@/components/JobActions.vue";
import JobEventTimeline from "@/components/JobEventTimeline.vue";
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import { formatDateTime, isActiveJobStatus, jobModeText } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const route = useRoute();
const jobId = computed(() => String(route.params.jobId || ""));
const job = ref<DocumentJobResponse | null>(null);
const events = ref<DocumentJobEventResponse[]>([]);
const loading = ref(false);
const eventsLoading = ref(false);
const downloadLoading = ref(false);
const retryLoading = ref(false);
const error = ref<ApiClientError | null>(null);
let pollTimer: number | undefined;

const requestSnapshotPreview = computed(() => JSON.stringify(job.value?.request_snapshot || {}, null, 2));

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

async function loadAll(): Promise<void> {
  await loadJob();
  if (job.value) {
    await loadEvents();
  }
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
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    downloadLoading.value = false;
  }
}

async function handleRetry(target: DocumentJobResponse): Promise<void> {
  retryLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.retry(target.id, "frontend retry");
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

watch(() => job.value?.status, syncPolling);

onMounted(async () => {
  document.addEventListener("visibilitychange", handleVisibilityChange);
  await loadAll();
  syncPolling();
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

@media (max-width: 760px) {
  .detail-overview {
    grid-template-columns: 1fr;
  }
}
</style>
