<!-- frontend/src/pages/JobsPage.vue: Main document job workbench with upload and job list. -->
<template>
  <div class="jobs-page">
    <PdfUploadPanel class="page-section" @created="handleCreated" />

    <section class="page-section">
      <div class="section-header">
        <div>
          <h1 class="section-title">任务列表</h1>
          <p class="section-subtitle">查看当前账号可见的 document_jobs。</p>
        </div>
        <div class="toolbar">
          <el-select v-model="statusFilter" clearable placeholder="全部状态" style="width: 150px" @change="handleFilter">
            <el-option v-for="status in statuses" :key="status" :label="jobStatusText[status]" :value="status" />
          </el-select>
          <el-button :icon="Refresh" :loading="loading" @click="loadJobs">刷新</el-button>
        </div>
      </div>

      <ApiErrorAlert :error="error" />

      <div v-if="summaryEntries.length" class="summary-row">
        <el-tag v-for="[status, count] in summaryEntries" :key="status" effect="plain">
          {{ statusLabel(status) }}: {{ count }}
        </el-tag>
      </div>

      <el-card class="card-flat" shadow="never">
        <JobTable
          :jobs="jobs"
          :loading="loading"
          :page="page"
          :page-size="pageSize"
          :total="total"
          @page-change="handlePageChange"
          @download="handleDownload"
          @retry="handleRetry"
        />
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import type { DocumentJobResponse, DocumentJobStatus } from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobTable from "@/components/JobTable.vue";
import PdfUploadPanel from "@/components/PdfUploadPanel.vue";
import { jobStatusText } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const router = useRouter();
const jobs = ref<DocumentJobResponse[]>([]);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const statusFilter = ref<DocumentJobStatus | "">("");
const summary = ref<Record<string, number>>({});
const statuses: DocumentJobStatus[] = ["pending", "queued", "running", "succeeded", "failed", "canceled"];

const summaryEntries = computed(() => Object.entries(summary.value).filter(([, count]) => count > 0));

async function loadJobs(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.list({
      page: page.value,
      page_size: pageSize,
      status: statusFilter.value || undefined,
    });
    jobs.value = response.items;
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

function statusLabel(status: string): string {
  return jobStatusText[status as DocumentJobStatus] || status;
}

function handleCreated(jobId: string): void {
  void router.push(`/jobs/${jobId}`);
}

async function handleDownload(job: DocumentJobResponse): Promise<void> {
  try {
    const response = await documentJobsApi.createDownloadUrl(job.id);
    window.open(response.download_url, "_blank", "noopener");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function handleRetry(job: DocumentJobResponse): Promise<void> {
  try {
    await documentJobsApi.retry(job.id, "frontend retry");
    ElMessage.success("已提交重试。");
    await loadJobs();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

onMounted(() => {
  void loadJobs();
});
</script>

<style scoped lang="scss">
.summary-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
</style>
