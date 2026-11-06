<template>
  <div class="section-header detail-header app-page-header app-page-shell">
    <div>
      <p class="page-kicker">转换任务</p>
      <h1 class="section-title page-title">任务详情</h1>
      <p class="section-subtitle mono">{{ jobId }}</p>
    </div>
    <div class="toolbar">
      <el-button v-if="supportsJobTranslationQa(job)" :icon="DataAnalysis" @click="openTranslationQa">
        翻译 QA
      </el-button>
      <JobActions
        v-if="job"
        :job="job"
        :download-loading="downloadLoading"
        :retry-loading="retryLoading"
        :clone-loading="cloneLoading"
        :cancel-loading="cancelLoading"
        :archive-loading="archiveLoading"
        :unarchive-loading="unarchiveLoading"
        :delete-loading="deleteLoading"
        @refresh="loadAll"
        @download="handleDownload"
        @retry="handleRetry"
        @clone="handleClone"
        @cancel="handleCancel"
        @archive="handleArchive"
        @unarchive="handleUnarchive"
        @delete="handleDelete"
      />
    </div>
  </div>
  <ApiErrorAlert :error="error" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.detail')" />
  <el-alert
    v-if="lastDownloadLink"
    class="page-section download-link-alert"
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
</template>

<script setup lang="ts">
import { DataAnalysis } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobActions from "@/components/JobActions.vue";
import { formatDateTime } from "@/utils/format";
import { supportsJobTranslationQa } from "./jobDetailFormat";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailActions } from "./useJobDetailActions";
const lastDownloadLink = defineModel<UnwrapRef<JobDetailActions["lastDownloadLink"]>>("lastDownloadLink", { required: true });
const {
  jobId,
  job,
  error,
  loadAll,
  jobErrorDiagnosticContext,
  downloadLoading,
  retryLoading,
  cloneLoading,
  cancelLoading,
  archiveLoading,
  unarchiveLoading,
  deleteLoading,
  openTranslationQa,
  handleDownload,
  copyLastDownloadLink,
  handleRetry,
  handleClone,
  handleCancel,
  handleArchive,
  handleUnarchive,
  handleDelete,
} = defineProps<{
  jobId: UnwrapRef<JobDetailData["jobId"]>;
  job: UnwrapRef<JobDetailData["job"]>;
  error: UnwrapRef<JobDetailData["error"]>;
  loadAll: UnwrapRef<JobDetailData["loadAll"]>;
  jobErrorDiagnosticContext: UnwrapRef<JobDetailData["jobErrorDiagnosticContext"]>;
  downloadLoading: UnwrapRef<JobDetailActions["downloadLoading"]>;
  retryLoading: UnwrapRef<JobDetailActions["retryLoading"]>;
  cloneLoading: UnwrapRef<JobDetailActions["cloneLoading"]>;
  cancelLoading: UnwrapRef<JobDetailActions["cancelLoading"]>;
  archiveLoading: UnwrapRef<JobDetailActions["archiveLoading"]>;
  unarchiveLoading: UnwrapRef<JobDetailActions["unarchiveLoading"]>;
  deleteLoading: UnwrapRef<JobDetailActions["deleteLoading"]>;
  openTranslationQa: UnwrapRef<JobDetailActions["openTranslationQa"]>;
  handleDownload: UnwrapRef<JobDetailActions["handleDownload"]>;
  copyLastDownloadLink: UnwrapRef<JobDetailActions["copyLastDownloadLink"]>;
  handleRetry: UnwrapRef<JobDetailActions["handleRetry"]>;
  handleClone: UnwrapRef<JobDetailActions["handleClone"]>;
  handleCancel: UnwrapRef<JobDetailActions["handleCancel"]>;
  handleArchive: UnwrapRef<JobDetailActions["handleArchive"]>;
  handleUnarchive: UnwrapRef<JobDetailActions["handleUnarchive"]>;
  handleDelete: UnwrapRef<JobDetailActions["handleDelete"]>;
}>();
</script>

<style scoped lang="scss">
.detail-header {
  margin-bottom: 0;
}

.detail-header .toolbar {
  justify-content: flex-end;
}

.download-link-alert {
  margin-top: 0;
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
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.download-link-notice a {
  color: var(--app-color-primary);
  font-weight: 700;
  text-decoration: none;
}
</style>
