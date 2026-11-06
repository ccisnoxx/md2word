<template>
  <div class="job-detail-page app-page">
    <JobDetailHeader
      v-model:lastDownloadLink="lastDownloadLink"
      v-bind="{
        jobId, job, error, loadAll, jobErrorDiagnosticContext, downloadLoading, retryLoading, cloneLoading,
        cancelLoading, archiveLoading, unarchiveLoading, deleteLoading, openTranslationQa, handleDownload,
        copyLastDownloadLink, handleRetry, handleClone, handleCancel, handleArchive, handleUnarchive,
        handleDelete,
      }"
    />
    <el-skeleton v-if="loading && !job" :rows="8" animated />
    <template v-else-if="job">
      <JobDispositionPanel
        v-bind="{
          loading, eventsLoading, filesLoading, callbackSummaryLoading, translationBatchesLoading, loadAll,
          dispositionAlertType, dispositionTitle, dispositionDescription, dispositionFacts, actionSummaries,
        }"
      />
      <JobPublicationPanel :job="job" />
      <JobReviewHintsPanel
        v-bind="{
          reviewBlocks, reviewBlocksLoading, reviewBlocksError, reviewBlocksConflict, reviewHintsAvailable,
          loadReviewBlocks, jobErrorDiagnosticContext, reviewHintItems, reviewHintsHaveWarnings,
          reviewHintSummary, reviewHintNotice,
        }"
      />
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
    </template>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import JobDetailHeader from "@/features/job-detail/JobDetailHeader.vue";
import JobDispositionPanel from "@/features/job-detail/JobDispositionPanel.vue";
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

const data = useJobDetailData(useRoute(), {
  onRetryRequested: (job) => actions.openRetryDialog(job),
  onRouteReset: () => actions.resetForRouteChange(),
});
const resources = useJobDetailResources(data);
const review = useJobDetailReviewHints(data);
const batches = useJobDetailBatches(data);
const diagnostics = useJobDetailDiagnostics(data, review, resources, batches);
const actions = useJobDetailActions(data, resources, useRouter(), useAuthStore());
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
  dispositionFacts,
  actionSummaries,
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
</script>

<style scoped lang="scss">
.job-detail-page {
  display: grid;
  gap: var(--app-space-4);
}

.job-detail-page :deep(.el-card.card-flat) {
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-panel);
}

.job-detail-page :deep(.el-card__body) {
  padding: var(--app-space-5);
}

.job-detail-page :deep(.el-button),
.job-detail-page :deep(.el-select__wrapper),
.job-detail-page :deep(.el-input__wrapper),
.job-detail-page :deep(.el-textarea__inner) {
  border-radius: var(--app-radius-md);
}

.detail-tabs {
  min-width: 0;
}

.detail-tabs :deep(.el-tabs__nav-wrap::after) {
  background-color: var(--app-color-border-soft);
}

.detail-tabs :deep(.el-tabs__item) {
  color: var(--app-color-text-muted);
  font-weight: 650;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: var(--app-color-primary);
}
</style>
