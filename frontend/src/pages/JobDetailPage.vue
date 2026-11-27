<!-- 文件：frontend/src/pages/JobDetailPage.vue；用途：展示紧凑双层头、水平阶段进度条、条件警示横幅与分域标签页的任务详情。 -->
<template>
  <div class="job-detail-page app-page">
    <JobDetailHeader
      v-model:lastDownloadLink="lastDownloadLink"
      v-bind="{
        jobId, job, sourceFilename, error, loadAll, jobErrorDiagnosticContext, downloadLoading, retryLoading,
        cloneLoading, cancelLoading, archiveLoading, unarchiveLoading, deleteLoading, openTranslationQa,
        openDocumentReview, handleDownload, copyLastDownloadLink, handleRetry, handleClone, handleCancel,
        handleArchive, handleUnarchive, handleDelete,
      }"
    />
    <el-skeleton v-if="loading && !job" :rows="8" animated />
    <template v-else-if="job">
      <JobPipelineStepper :job="job" />

      <div v-if="topBanner" class="top-condition-banner app-page-shell">
        <el-alert
          class="condition-alert"
          :type="topBanner.type"
          :closable="false"
          show-icon
          :title="topBanner.title"
        >
          <div class="condition-alert-body">
            <span>{{ topBanner.description }}</span>
            <div class="condition-alert-actions">
              <el-button
                v-for="link in topBanner.actions"
                :key="link.key"
                size="small"
                text
                type="primary"
                @click="link.kind === 'review' ? openDocumentReview() : openTab(link.tab!)"
              >
                {{ link.label }}
              </el-button>
            </div>
          </div>
        </el-alert>
      </div>

      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="概览" name="overview">
          <JobOverviewPanel
            v-bind="{
              job, sourceFilename, translationQaReviewText, boundTemplateLabel, boundTermRuleSetLabel,
              boundTranslationTermSetLabel, boundTranslationProfileLabel, runningNotice, runningNoticeType,
              downloadHint,
            }"
          />
        </el-tab-pane>
        <el-tab-pane name="quality">
          <template #label>
            <span class="tab-label-with-badge">
              <span>质量与提示</span>
              <el-tag
                v-if="reviewHintItems.length > 0"
                size="small"
                :type="reviewHintsHaveWarnings ? 'warning' : 'info'"
                effect="plain"
              >
                {{ reviewHintItems.length }}
              </el-tag>
            </span>
          </template>
          <JobReviewHintsPanel
            v-bind="{
              reviewBlocks, reviewBlocksLoading, reviewBlocksError, reviewBlocksConflict, reviewHintsAvailable,
              loadReviewBlocks, jobErrorDiagnosticContext, reviewHintItems, reviewHintsHaveWarnings,
              reviewHintSummary, reviewHintNotice, openDocumentReview,
            }"
          />
        </el-tab-pane>
        <el-tab-pane label="发布与交付" name="publication">
          <JobPublicationPanel
            :job="job"
            :publication="publication"
            :is-admin="isAdmin"
            @open-new-generation="handleOpenNewGeneration"
          />
        </el-tab-pane>
        <el-tab-pane label="诊断" name="diagnostics">
          <JobDiagnosticsPanel
            v-bind="{
              job, events, callbackSummary, translationBatches, loading, eventsLoading, filesLoading,
              callbackSummaryLoading, translationBatchesLoading, eventsError, filesError,
              callbackSummaryError, translationBatchesError, loadEvents, loadFiles, loadCallbackSummary,
              loadTranslationBatches, loadAll, jobErrorDiagnosticContext, openEventsTab,
              translationBatchSummaryItems, translationBatchConclusion, latestErrorEvent, degradedPages,
              sourcePageLine, failureSummary, failureHelpText, callbackSummaryItems, qualityEvidence,
              diagnosticRecommendation, diagnosticSummaryFacts, diagnosticEvidenceItems,
              diagnosticPreviewEvents, diagnosticRecoveryItems,
            }"
          />
        </el-tab-pane>
        <el-tab-pane label="上下文" name="context">
          <JobContextPanel
            v-bind="{
              job, requestSnapshotPreview, termRuleProposalVersionLabel, translationTermProposalVersionLabel,
              openTermRuleProposal, openTranslationTermProposal,
            }"
          />
        </el-tab-pane>
        <el-tab-pane label="文件" name="files">
          <JobFilesPanel
            v-bind="{
              files, filesLoading, filesError, loadFiles, jobErrorDiagnosticContext, downloadingFileId,
              handleFileDownload,
            }"
          />
        </el-tab-pane>
        <el-tab-pane label="事件" name="events">
          <JobEventsPanel
            v-model:eventLevelFilter="eventLevelFilter"
            v-model:eventStageFilter="eventStageFilter"
            v-bind="{
              eventsLoading, eventsError, loadEvents, jobErrorDiagnosticContext, filteredEvents,
            }"
          />
        </el-tab-pane>
      </el-tabs>
      <JobActionDialogs
        v-model:retryDialogVisible="retryDialogVisible"
        v-model:cloneDialogVisible="cloneDialogVisible"
        v-bind="{
          jobErrorDiagnosticContext, retryLoading, cloneLoading, configError, configLoading,
          configSummary, retryDialog, cloneDialog, isAdmin, submitRetryDialog, submitCloneDialog,
        }"
      />
      <NewGenerationDialog
        :job-id="jobId"
        :action="newGenerationAction"
        :latest-expected-source="latestNewGenerationSource"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";
import { documentJobsApi } from "@/api/documentJobs";
import type { ReviewExpectedSourceRequest } from "@/api/types";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError } from "@/utils/errors";
import { isDocumentJobActionEnabled } from "@/utils/format";
import { buildExpectedSource } from "@/features/document-review/documentReviewFormat";
import NewGenerationDialog from "@/features/document-review/NewGenerationDialog.vue";
import { useNewGenerationAction } from "@/features/document-review/useNewGenerationAction";
import JobDetailHeader from "@/features/job-detail/JobDetailHeader.vue";
import JobPipelineStepper from "@/features/job-detail/JobPipelineStepper.vue";
import JobPublicationPanel from "@/features/job-detail/JobPublicationPanel.vue";
import JobReviewHintsPanel from "@/features/job-detail/JobReviewHintsPanel.vue";
import JobOverviewPanel from "@/features/job-detail/JobOverviewPanel.vue";
import JobDiagnosticsPanel from "@/features/job-detail/JobDiagnosticsPanel.vue";
import JobContextPanel from "@/features/job-detail/JobContextPanel.vue";
import JobFilesPanel from "@/features/job-detail/JobFilesPanel.vue";
import JobEventsPanel from "@/features/job-detail/JobEventsPanel.vue";
import JobActionDialogs from "@/features/job-detail/JobActionDialogs.vue";
import { useJobDetailData } from "@/features/job-detail/useJobDetailData";
import { useJobDetailResources } from "@/features/job-detail/useJobDetailResources";
import { useJobDetailReviewHints } from "@/features/job-detail/useJobDetailReviewHints";
import { useJobDetailBatches } from "@/features/job-detail/useJobDetailBatches";
import { useJobDetailDiagnostics } from "@/features/job-detail/useJobDetailDiagnostics";
import { useJobDetailActions } from "@/features/job-detail/useJobDetailActions";
import { useJobPublication } from "@/features/job-detail/useJobPublication";

const data = useJobDetailData(useRoute(), {
  onRetryRequested: (job) => actions.openRetryDialog(job),
  onRouteReset: () => {
    actions.resetForRouteChange();
    publication.reset();
  },
});
const resources = useJobDetailResources(data);
const review = useJobDetailReviewHints(data);
const batches = useJobDetailBatches(data);
const diagnostics = useJobDetailDiagnostics(data, review, resources, batches);
const actions = useJobDetailActions(data, resources, useRouter(), useAuthStore());
const publication = useJobPublication({
  jobId: data.jobId,
  job: data.job,
  activeTab: data.activeTab,
  onPublished: async () => {
    await data.loadAll();
  },
});
const newGenerationAction = useNewGenerationAction({
  jobId: data.jobId,
  onAccepted: async () => {
    await data.loadAll();
    if (data.activeTab.value === "publication") {
      await publication.load();
    }
  },
});
const {
  jobId,
  job,
  events,
  files,
  callbackSummary,
  translationBatches,
  reviewBlocks,
  reviewBlocksLoading,
  reviewBlocksError,
  reviewBlocksConflict,
  loading,
  eventsLoading,
  filesLoading,
  callbackSummaryLoading,
  translationBatchesLoading,
  activeTab,
  eventLevelFilter,
  eventStageFilter,
  error,
  eventsError,
  filesError,
  callbackSummaryError,
  translationBatchesError,
  reviewHintsAvailable,
  loadEvents,
  loadFiles,
  loadCallbackSummary,
  loadReviewBlocks,
  loadTranslationBatches,
  loadAll,
  jobErrorDiagnosticContext,
  openTab,
  openEventsTab,
} = data;
const {
  requestSnapshotPreview,
  sourceFilename,
  translationQaReviewText,
  boundTemplateLabel,
  boundTermRuleSetLabel,
  boundTranslationTermSetLabel,
  boundTranslationProfileLabel,
  termRuleProposalVersionLabel,
  translationTermProposalVersionLabel,
} = resources;
const { reviewHintItems, reviewHintsHaveWarnings, reviewHintSummary, reviewHintNotice } = review;
const { translationBatchSummaryItems, translationBatchConclusion } = batches;
const {
  filteredEvents,
  latestErrorEvent,
  degradedPages,
  sourcePageLine,
  failureSummary,
  failureHelpText,
  runningNotice,
  runningNoticeType,
  downloadHint,
  callbackSummaryItems,
  dispositionAlertType,
  dispositionTitle,
  dispositionDescription,
  qualityEvidence,
  diagnosticRecommendation,
  diagnosticSummaryFacts,
  diagnosticEvidenceItems,
  diagnosticPreviewEvents,
  diagnosticRecoveryItems,
} = diagnostics;
const {
  downloadLoading,
  downloadingFileId,
  retryLoading,
  cloneLoading,
  cancelLoading,
  archiveLoading,
  unarchiveLoading,
  deleteLoading,
  retryDialogVisible,
  cloneDialogVisible,
  configError,
  configLoading,
  configSummary,
  lastDownloadLink,
  retryDialog,
  cloneDialog,
  isAdmin,
  openTermRuleProposal,
  openTranslationTermProposal,
  openTranslationQa,
  openDocumentReview,
  handleDownload,
  handleFileDownload,
  copyLastDownloadLink,
  handleRetry,
  handleClone,
  handleCancel,
  handleArchive,
  handleUnarchive,
  handleDelete,
  submitRetryDialog,
  submitCloneDialog,
} = actions;

const latestNewGenerationSource = computed<ReviewExpectedSourceRequest | null>(() => {
  const pubSource = publication.publications.value?.expected_source;
  if (pubSource) {
    return {
      generation: pubSource.generation,
      result_file_id: pubSource.result_file_id,
      result_sha256: pubSource.result_sha256,
      file_review_source_revision: pubSource.file_review_source_revision,
      receipt_sha256: pubSource.receipt_sha256,
    };
  }
  if (reviewBlocks.value?.source) {
    return buildExpectedSource(reviewBlocks.value.source);
  }
  return null;
});

async function handleOpenNewGeneration(): Promise<void> {
  if (latestNewGenerationSource.value) {
    newGenerationAction.open(latestNewGenerationSource.value);
    return;
  }
  try {
    const qualityResp = await documentJobsApi.getQuality(jobId.value);
    newGenerationAction.open(buildExpectedSource(qualityResp.source));
  } catch (caught) {
    ElMessage.error(normalizeApiError(caught).message);
  }
}

type TopBannerAction =
  | { key: string; label: string; kind: "tab"; tab: string }
  | { key: string; label: string; kind: "review" };

type TopBannerConfig = {
  type: "error" | "warning" | "info" | "success";
  title: string;
  description: string;
  actions: TopBannerAction[];
};

const topBanner = computed<TopBannerConfig | null>(() => {
  const current = job.value;
  if (!current) {
    return null;
  }
  if (current.status === "failed") {
    return {
      type: "error",
      title: dispositionTitle.value,
      description: failureHelpText.value,
      actions: [
        { key: "diagnostics", label: "查看诊断", kind: "tab", tab: "diagnostics" },
        { key: "events", label: "查看事件", kind: "tab", tab: "events" },
      ],
    };
  }
  if (current.quality_status === "blocked") {
    return {
      type: "error",
      title: "质量检查存在阻断项，当前不可作为最终交付件发布",
      description: reviewHintNotice.value,
      actions: [
        { key: "review", label: "进入三栏复核", kind: "review" },
        { key: "quality", label: "查看质量与提示", kind: "tab", tab: "quality" },
        { key: "publication", label: "查看发布与交付", kind: "tab", tab: "publication" },
      ],
    };
  }
  if (reviewHintsHaveWarnings.value || reviewBlocksConflict.value) {
    return {
      type: "warning",
      title: dispositionTitle.value,
      description: reviewHintNotice.value,
      actions: [
        { key: "review", label: "进入三栏复核", kind: "review" },
        { key: "quality", label: "查看质量与提示", kind: "tab", tab: "quality" },
        { key: "publication", label: "查看发布与交付", kind: "tab", tab: "publication" },
      ],
    };
  }
  if (current.status === "canceled" || dispositionAlertType.value === "warning") {
    return {
      type: "warning",
      title: dispositionTitle.value,
      description: dispositionDescription.value,
      actions: [{ key: "diagnostics", label: "查看诊断", kind: "tab", tab: "diagnostics" }],
    };
  }
  if (current.status === "succeeded" && isDocumentJobActionEnabled(current, "publish")) {
    return {
      type: "info",
      title: "当前任务已满足后端发布条件",
      description: "请前往「发布与交付」查看发布前检查并提交正式发布。",
      actions: [{ key: "publication", label: "前往发布与交付", kind: "tab", tab: "publication" }],
    };
  }
  return null;
});
</script>

<style scoped lang="scss">
.job-detail-page {
  display: grid;
  gap: 14px;
}

.top-condition-banner {
  min-width: 0;
}

.condition-alert-body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 14px;
  margin-top: 2px;
}

.condition-alert-actions {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tab-label-with-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.detail-tabs {
  width: 100%;
  max-width: var(--app-content-width);
  margin: 0 auto;
  min-width: 0;
}

.detail-tabs :deep(.el-tabs__content) {
  overflow: visible;
}

.job-detail-page :deep(.el-card) {
  border-color: var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.job-detail-page :deep(.el-tabs__nav-wrap::after) {
  background-color: var(--app-color-border-soft);
}

.job-detail-page :deep(.el-tabs__active-bar) {
  background-color: var(--app-color-primary);
}

.job-detail-page :deep(.el-tabs__item.is-active) {
  color: var(--app-color-primary-hover);
  font-weight: 600;
}

.job-detail-page :deep(.el-descriptions__label) {
  background: var(--app-color-surface-muted);
  color: var(--app-color-text-muted);
}

.job-detail-page :deep(.el-descriptions__content) {
  overflow-wrap: anywhere;
}
</style>
