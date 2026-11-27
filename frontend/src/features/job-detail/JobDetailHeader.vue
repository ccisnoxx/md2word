<!-- 文件：frontend/src/features/job-detail/JobDetailHeader.vue；用途：展示源 PDF 文件名主标题、四态胶囊、ID 复制与主生命周期操作。 -->
<template>
  <div class="section-header detail-header app-page-header app-page-shell">
    <div class="detail-identity">
      <div class="detail-kicker-row">
        <p class="page-kicker">任务详情</p>
        <el-tag v-if="job" size="small" effect="plain">{{ jobModeText[job.mode] || job.mode }}</el-tag>
        <el-tag v-if="job?.archived_at" size="small" type="info" effect="plain">已归档</el-tag>
      </div>
      <h1 class="section-title page-title detail-filename" :title="displayTitle">{{ displayTitle }}</h1>
      <div class="detail-meta-row">
        <span class="mono detail-job-id" :title="jobId">{{ jobId }}</span>
        <el-button
          class="copy-id-btn"
          link
          size="small"
          :icon="CopyDocument"
          aria-label="复制任务 ID"
          @click="copyJobId"
        >
          复制 ID
        </el-button>
        <span v-if="job && job.retry_count > 0" class="detail-meta-sep">· 第 {{ job.retry_count + 1 }} 代</span>
        <span v-if="job" class="detail-meta-sep">· 更新于 {{ formatDateTime(job.updated_at) }}</span>
      </div>
      <div v-if="job" class="detail-state-strip" aria-label="任务四态摘要">
        <el-tag size="small" :type="executionTagType" effect="plain">
          执行：{{ jobStatusText[job.status] || job.status }}
        </el-tag>
        <el-tag
          v-if="job.quality_status"
          size="small"
          :type="jobQualityStatusTagType(job.quality_status)"
          effect="plain"
        >
          质量：{{ jobQualityStatusText[job.quality_status] || job.quality_status }}
        </el-tag>
        <el-tag
          v-if="job.review_status"
          size="small"
          :type="jobReviewStatusTagType(job.review_status)"
          effect="plain"
        >
          复核：{{ jobReviewStatusText[job.review_status] || job.review_status }}
        </el-tag>
        <el-tag
          v-if="job.delivery_status"
          size="small"
          :type="jobDeliveryStatusTagType(job.delivery_status)"
          effect="plain"
        >
          交付：{{ jobDeliveryStatusText[job.delivery_status] || job.delivery_status }}
        </el-tag>
      </div>
    </div>
    <div class="toolbar">
      <el-button
        v-if="job"
        :type="job.status === 'succeeded' ? 'primary' : 'default'"
        plain
        :icon="DocumentChecked"
        @click="openDocumentReview()"
      >
        进入三栏复核
      </el-button>
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
import { computed } from "vue";
import { ElMessage } from "element-plus";
import { CopyDocument, DataAnalysis, DocumentChecked } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobActions from "@/components/JobActions.vue";
import { copyDownloadLink } from "@/utils/download";
import {
  formatDateTime,
  jobDeliveryStatusTagType,
  jobDeliveryStatusText,
  jobModeText,
  jobQualityStatusTagType,
  jobQualityStatusText,
  jobReviewStatusTagType,
  jobReviewStatusText,
  jobStatusText,
} from "@/utils/format";
import { supportsJobTranslationQa } from "./jobDetailFormat";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailActions } from "./useJobDetailActions";
import type { JobDetailResources } from "./useJobDetailResources";

const lastDownloadLink = defineModel<UnwrapRef<JobDetailActions["lastDownloadLink"]>>("lastDownloadLink", { required: true });
const {
  jobId,
  job,
  sourceFilename,
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
  openDocumentReview,
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
  sourceFilename: UnwrapRef<JobDetailResources["sourceFilename"]>;
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
  openDocumentReview: UnwrapRef<JobDetailActions["openDocumentReview"]>;
  handleDownload: UnwrapRef<JobDetailActions["handleDownload"]>;
  copyLastDownloadLink: UnwrapRef<JobDetailActions["copyLastDownloadLink"]>;
  handleRetry: UnwrapRef<JobDetailActions["handleRetry"]>;
  handleClone: UnwrapRef<JobDetailActions["handleClone"]>;
  handleCancel: UnwrapRef<JobDetailActions["handleCancel"]>;
  handleArchive: UnwrapRef<JobDetailActions["handleArchive"]>;
  handleUnarchive: UnwrapRef<JobDetailActions["handleUnarchive"]>;
  handleDelete: UnwrapRef<JobDetailActions["handleDelete"]>;
}>();

const displayTitle = computed(() => {
  if (sourceFilename && sourceFilename !== "-") {
    return sourceFilename;
  }
  return jobId || "任务详情";
});

const executionTagType = computed<"success" | "warning" | "danger" | "info">(() => {
  if (job?.status === "succeeded") {
    return "success";
  }
  if (job?.status === "failed") {
    return "danger";
  }
  if (job?.status === "canceled") {
    return "warning";
  }
  return "info";
});

async function copyJobId(): Promise<void> {
  if (!jobId) {
    return;
  }
  const copied = await copyDownloadLink(jobId);
  if (copied) {
    ElMessage.success("任务 ID 已复制。");
    return;
  }
  ElMessage.warning("当前浏览器不支持自动复制。");
}
</script>

<style scoped lang="scss">
.detail-header {
  margin-bottom: 0;
  align-items: flex-start;
  gap: 16px;
}

.detail-identity {
  display: grid;
  gap: 6px;
  min-width: 0;
  flex: 1 1 320px;
}

.detail-kicker-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.detail-kicker-row .page-kicker {
  margin: 0;
}

.detail-filename {
  margin: 0;
  overflow-wrap: anywhere;
}

.detail-meta-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.detail-job-id {
  overflow-wrap: anywhere;
}

.copy-id-btn {
  padding: 0 4px;
  height: auto;
  font-size: 12px;
}

.detail-state-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}

.detail-header .toolbar {
  justify-content: flex-end;
  flex: 0 1 auto;
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
