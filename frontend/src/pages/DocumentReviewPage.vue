<!-- 文件：frontend/src/pages/DocumentReviewPage.vue -->
<!-- 用途：独立全宽三栏统一文档复核工作台（/jobs/:jobId/review），同时服务原文直转与四向翻译任务。 -->
<template>
  <main class="document-review-page" aria-labelledby="document-review-title">
    <header class="review-topbar">
      <div class="topbar-left">
        <el-button size="small" :icon="ArrowLeft" @click="goBackToDetail">返回详情</el-button>
        <el-button
          class="tablet-outline-toggle"
          size="small"
          :icon="Menu"
          @click="outlineDrawerOpen = true"
        >
          块大纲 ({{ blocks.length }})
        </el-button>
        <div class="topbar-title-group">
          <div class="topbar-title-row">
            <h1 id="document-review-title" class="review-title" :title="sourceFilename">{{ sourceFilename }}</h1>
            <el-tag v-if="observedSource" size="small" type="info" effect="plain">
              第 {{ observedSource.generation + 1 }} 代
            </el-tag>
            <el-tag v-if="job" size="small" effect="plain">
              {{ jobModeText[job.mode] || job.mode }}
            </el-tag>
          </div>
          <div v-if="states" class="topbar-state-strip" aria-label="任务四态">
            <el-tag size="small" :type="states.execution_status === 'succeeded' ? 'success' : states.execution_status === 'failed' ? 'danger' : 'info'" effect="plain">
              执行：{{ jobStatusText[states.execution_status] || states.execution_status }}
            </el-tag>
            <el-tag size="small" :type="jobQualityStatusTagType(states.quality_status)" effect="plain">
              质量：{{ jobQualityStatusText[states.quality_status] || states.quality_status }}
            </el-tag>
            <el-tag size="small" :type="jobReviewStatusTagType(states.review_status)" effect="plain">
              复核：{{ jobReviewStatusText[states.review_status] || states.review_status }}
            </el-tag>
            <el-tag size="small" :type="jobDeliveryStatusTagType(states.delivery_status)" effect="plain">
              交付：{{ jobDeliveryStatusText[states.delivery_status] || states.delivery_status }}
            </el-tag>
          </div>
        </div>
      </div>

      <div class="topbar-right">
        <el-button size="small" :icon="TopRight" :loading="openingSourcePdf" @click="openSourcePdf">
          打开源 PDF{{ currentSourcePageNumber ? `（第 ${currentSourcePageNumber} 页）` : "" }}
        </el-button>
        <el-button size="small" :icon="Download" :loading="downloadingDraft" @click="downloadInternalDraft">
          下载草稿
        </el-button>
        <el-tooltip
          v-if="isAdmin && !isTranslationJob && tableSemanticsFindingsCount > 0 && effectiveActions?.new_generation"
          :disabled="canRequestNewGeneration || !newGenerationDisabledReason"
          :content="newGenerationDisabledReason"
          placement="bottom"
        >
          <span>
            <el-button
              size="small"
              type="primary"
              plain
              :disabled="!canRequestNewGeneration || !expectedSource"
              @click="openTableValueReviewDrawer"
            >
              表格值列核定模式 ({{ tableSemanticsFindingsCount }})
            </el-button>
          </span>
        </el-tooltip>
        <el-tooltip
          v-if="isAdmin && effectiveActions?.new_generation"
          :disabled="canRequestNewGeneration || !newGenerationDisabledReason"
          :content="newGenerationDisabledReason"
          placement="bottom"
        >
          <span>
            <el-button
              size="small"
              type="warning"
              plain
              :disabled="!canRequestNewGeneration || !expectedSource"
              @click="openNewGenerationDialog"
            >
              开始同任务新代
            </el-button>
          </span>
        </el-tooltip>
        <el-button size="small" :icon="Refresh" :loading="loading" @click="loadAll(false)">刷新</el-button>
      </div>
    </header>

    <ApiErrorAlert :error="pageError" />
    <el-skeleton v-if="loading && !job && !quality" :rows="8" animated />

    <template v-else>
      <div class="mobile-pane-switch" aria-label="切换复核视图">
        <el-segmented
          v-model="mobilePane"
          :options="[
            { label: `块大纲 (${blocks.length})`, value: 'outline' },
            { label: '内容对照', value: 'content' },
            { label: '预览与签核', value: 'preview' },
          ]"
          block
        />
      </div>

      <div class="review-three-pane" :data-mobile-pane="mobilePane">
        <div class="pane-slot pane-outline">
          <ReviewOutlinePane
            :filter="outlineFilter"
            :blocks-response="blocksResponse"
            :blocks="blocks"
            :available-source-pages="availableSourcePages"
            :selected-block-id="selectedBlockId"
            :blocks-loading="blocksLoading"
            :blocks-error="blocksError"
            @select-block="handleSelectBlock"
            @load-more="loadBlocks(true)"
          />
        </div>

        <div class="pane-slot pane-content">
          <ReviewContentPane
            :selected-block="selectedBlock"
            :block-detail="blockDetail"
            :block-detail-loading="blockDetailLoading"
            :block-detail-error="blockDetailError"
            :selected-block-tables="selectedBlockTables"
            :selected-block-references="selectedBlockReferences"
            :table-ref-object-urls="tableRefObjectUrls"
            :table-ref-loading="tableRefLoading"
            :table-ref-errors="tableRefErrors"
            :is-translation-job="isTranslationJob"
            @load-more-detail="loadBlockDetail(selectedBlockId, true)"
            @open-lightbox="openLightbox"
            @propose-term="openTermProposal"
          />
        </div>

        <div class="pane-slot pane-preview">
          <ReviewPreviewSignoffPane
            v-model:preview-zoom="previewZoom"
            :selected-block="selectedBlock"
            :preview-response="previewResponse"
            :preview-pages="previewPages"
            :current-preview-page="currentPreviewPage"
            :current-preview-image-url="currentPreviewImageUrl"
            :current-preview-image-loading="currentPreviewImageLoading"
            :current-preview-image-error="currentPreviewImageError"
            :preview-error="previewError"
            :pages-response="pagesResponse"
            :pages-error="pagesError"
            :current-review="currentReview"
            :review-form="reviewForm"
            :must-tick-table-semantics-to-approve="mustTickTableSemanticsToApprove"
            :table-semantics-report-sha256="tableSemanticsReportSha256"
            :table-semantics-findings-count="tableSemanticsFindingsCount"
            :can-submit-review="canSubmitReview"
            :submitting-review="submittingReview"
            :review-submit-error="reviewSubmitError"
            :review-conflict-active="reviewConflictActive"
            :opening-source-pdf="openingSourcePdf"
            :downloading-draft="downloadingDraft"
            @set-preview-page="setPreviewPageIndex"
            @step-preview-page="stepPreviewPage"
            @select-block="handleSelectBlock"
            @submit-review="submitReview"
            @open-history="openReviewHistory"
            @refresh-preserve-draft="loadAll(true)"
            @open-source-pdf="openSourcePdf"
            @download-draft="downloadInternalDraft"
            @go-publication="goToPublicationTab"
          />
        </div>
      </div>
    </template>

    <!-- 平板端左侧大纲抽屉 -->
    <el-drawer
      v-model="outlineDrawerOpen"
      title="文档块与告警大纲"
      direction="ltr"
      size="min(320px, 88vw)"
      :append-to-body="true"
    >
      <div class="drawer-outline-host">
        <ReviewOutlinePane
          :filter="outlineFilter"
          :blocks-response="blocksResponse"
          :blocks="blocks"
          :available-source-pages="availableSourcePages"
          :selected-block-id="selectedBlockId"
          :blocks-loading="blocksLoading"
          :blocks-error="blocksError"
          @select-block="handleDrawerSelectBlock"
          @load-more="loadBlocks(true)"
        />
      </div>
    </el-drawer>

    <!-- 表格参考图放大灯箱 -->
    <el-dialog
      v-model="lightboxVisible"
      :title="lightboxTitle || '表格参考图预览'"
      width="min(960px, calc(100vw - 32px))"
      top="24px"
      :append-to-body="true"
    >
      <div class="lightbox-toolbar">
        <el-radio-group v-model="lightboxZoom" size="small">
          <el-radio-button :value="100">100%</el-radio-button>
          <el-radio-button :value="150">150%</el-radio-button>
          <el-radio-button :value="200">200%</el-radio-button>
        </el-radio-group>
      </div>
      <div class="lightbox-canvas app-scrollbar-persistent">
        <img
          v-if="lightboxUrl"
          :src="lightboxUrl"
          :alt="lightboxTitle || '表格参考图'"
          class="lightbox-image"
          :style="{ width: `${lightboxZoom}%` }"
        />
      </div>
    </el-dialog>

    <ReviewHistoryDrawer
      v-model="reviewHistoryOpen"
      :history="reviewHistory"
      :loading="reviewHistoryLoading"
      :error="reviewHistoryError"
      @refresh="loadReviewHistory(false)"
      @load-more="loadReviewHistory(true)"
    />

    <InlineTermProposalDrawer
      v-model="termProposalVisible"
      :job="job"
      :observed-term-set-id="observedTranslationTermSetId"
      :observed-term-version="observedTranslationTermVersion"
      :initial-source-term="termProposalDraft.sourceTerm"
      :initial-target-term="termProposalDraft.targetTerm"
      :context-summary="termProposalDraft.contextSummary"
      :source-excerpt="termProposalDraft.excerpt"
    />

    <NewGenerationDialog
      :job-id="jobId"
      :action="newGenerationAction"
      :latest-expected-source="expectedSource"
    />

    <TableValueColumnReviewDrawer
      :controller="tableValueReview"
      :table-references="allTableReferences"
      :table-ref-object-urls="tableRefObjectUrls"
      :latest-expected-source="expectedSource"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ArrowLeft, Download, Menu, Refresh, TopRight } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import InlineTermProposalDrawer from "@/components/InlineTermProposalDrawer.vue";
import NewGenerationDialog from "@/features/document-review/NewGenerationDialog.vue";
import ReviewContentPane from "@/features/document-review/ReviewContentPane.vue";
import ReviewHistoryDrawer from "@/features/document-review/ReviewHistoryDrawer.vue";
import ReviewOutlinePane from "@/features/document-review/ReviewOutlinePane.vue";
import ReviewPreviewSignoffPane from "@/features/document-review/ReviewPreviewSignoffPane.vue";
import TableValueColumnReviewDrawer from "@/features/document-review/TableValueColumnReviewDrawer.vue";
import { useDocumentReviewSession } from "@/features/document-review/useDocumentReviewSession";
import { useNewGenerationAction } from "@/features/document-review/useNewGenerationAction";
import { useTableValueColumnReview } from "@/features/document-review/useTableValueColumnReview";
import { readRecord, readResourceSnapshot, readString } from "@/features/job-detail/jobDetailFormat";
import { useAuthStore } from "@/stores/auth";
import {
  jobDeliveryStatusTagType,
  jobDeliveryStatusText,
  jobModeText,
  jobQualityStatusTagType,
  jobQualityStatusText,
  jobReviewStatusTagType,
  jobReviewStatusText,
  jobStatusText,
} from "@/utils/format";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const mobilePane = ref<"outline" | "content" | "preview">("content");
const outlineDrawerOpen = ref(false);
const lightboxVisible = ref(false);
const lightboxUrl = ref("");
const lightboxTitle = ref("");
const lightboxZoom = ref(100);
const termProposalVisible = ref(false);
const termProposalDraft = reactive({
  sourceTerm: "",
  targetTerm: "",
  excerpt: "",
  contextSummary: "",
});

const isAdmin = computed(() => auth.user?.role === "admin");

const session = useDocumentReviewSession(route, router, {
  isOverlayOpen: () =>
    outlineDrawerOpen.value
    || lightboxVisible.value
    || termProposalVisible.value
    || newGenerationAction.visible.value
    || tableValueReview.visible.value,
});

const {
  jobId,
  job,
  quality,
  blocksResponse,
  tablesResponse,
  pagesResponse,
  previewResponse,
  tableReferencesResponse,
  blocks,
  selectedBlockId,
  selectedBlock,
  blockDetail,
  selectedBlockTables,
  selectedBlockReferences,
  availableSourcePages,
  currentSourcePageNumber,
  isTranslationJob,
  sourceFilename,
  observedSource,
  expectedSource,
  outlineFilter,
  reviewForm,
  currentReview,
  tableSemanticsReportSha256,
  tableSemanticsFindingsCount,
  mustTickTableSemanticsToApprove,
  canSubmitReview,
  effectiveActions,
  canRequestNewGeneration,
  newGenerationDisabledReason,
  previewPages,
  currentPreviewPage,
  currentPreviewImageUrl,
  currentPreviewImageLoading,
  currentPreviewImageError,
  previewZoom,
  tableRefObjectUrls,
  tableRefLoading,
  tableRefErrors,
  reviewHistory,
  reviewHistoryOpen,
  reviewHistoryLoading,
  reviewHistoryError,
  loading,
  blocksLoading,
  blockDetailLoading,
  submittingReview,
  openingSourcePdf,
  downloadingDraft,
  pageError,
  blocksError,
  blockDetailError,
  previewError,
  pagesError,
  reviewSubmitError,
  reviewConflictActive,
  loadAll,
  loadBlocks,
  loadBlockDetail,
  selectBlock,
  setPreviewPageIndex,
  stepPreviewPage,
  submitReview,
  openReviewHistory,
  loadReviewHistory,
  openSourcePdf,
  downloadInternalDraft,
} = session;

const newGenerationAction = useNewGenerationAction({
  jobId,
  onAccepted: async () => {
    await loadAll(false);
  },
});

const sourcePdfFileId = computed(
  () => blocksResponse.value?.content_snapshot.source_pdf_file_id ?? job.value?.source_file_id ?? null,
);
const allTableReferences = computed(() => tableReferencesResponse.value?.items ?? []);

const tableValueReview = useTableValueColumnReview({
  jobId,
  sourcePdfFileId,
  onAccepted: async () => {
    await loadAll(false);
  },
});

const states = computed(() => {
  if (quality.value?.states) {
    return quality.value.states;
  }
  if (!job.value) {
    return null;
  }
  return {
    execution_status: job.value.status,
    quality_status: job.value.quality_status || "pending",
    review_status: job.value.review_status || "unreviewed",
    delivery_status: job.value.delivery_status || "internal_draft",
  };
});

const resourceSnapshot = computed(() => readResourceSnapshot(job.value?.request_snapshot.resources));
const observedTranslationTermSetId = computed(() => {
  const bound = resourceSnapshot.value?.translation_term_set;
  if (bound?.set_id) {
    return bound.set_id;
  }
  const assets = readRecord(job.value?.request_snapshot.term_assets);
  return readString(assets?.translation_term_set_id);
});
const observedTranslationTermVersion = computed(() => {
  const bound = resourceSnapshot.value?.translation_term_set;
  if (bound?.version) {
    return bound.version;
  }
  const assets = readRecord(job.value?.request_snapshot.term_assets);
  return readString(assets?.translation_term_version) || job.value?.term_version_id || null;
});

function goBackToDetail(): void {
  void router.push({ name: "job-detail", params: { jobId: jobId.value } });
}

function goToPublicationTab(): void {
  void router.push({
    name: "job-detail",
    params: { jobId: jobId.value },
    query: { tab: "publication" },
  });
}

function handleSelectBlock(blockId: string): void {
  void selectBlock(blockId);
  if (mobilePane.value === "outline") {
    mobilePane.value = "content";
  }
}

function handleDrawerSelectBlock(blockId: string): void {
  outlineDrawerOpen.value = false;
  void selectBlock(blockId);
}

function openLightbox(payload: { url: string; title: string }): void {
  lightboxUrl.value = payload.url;
  lightboxTitle.value = payload.title;
  lightboxZoom.value = 100;
  lightboxVisible.value = true;
}

function openTermProposal(payload: {
  sourceTerm: string;
  targetTerm: string;
  excerpt: string;
  contextSummary: string;
}): void {
  termProposalDraft.sourceTerm = payload.sourceTerm;
  termProposalDraft.targetTerm = payload.targetTerm;
  termProposalDraft.excerpt = payload.excerpt;
  termProposalDraft.contextSummary = payload.contextSummary;
  termProposalVisible.value = true;
}

function openNewGenerationDialog(): void {
  if (!expectedSource.value) {
    return;
  }
  newGenerationAction.open(expectedSource.value);
}

function openTableValueReviewDrawer(): void {
  if (!expectedSource.value) {
    return;
  }
  tableValueReview.open(tablesResponse.value?.items ?? [], expectedSource.value);
}
</script>

<style scoped lang="scss">
.document-review-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.review-topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-lg);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.topbar-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1 1 360px;
}

.topbar-title-group {
  display: grid;
  gap: 6px;
  min-width: 0;
  flex: 1 1 240px;
}

.topbar-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.review-title {
  margin: 0;
  font-size: 18px;
  line-height: 1.25;
  color: var(--app-color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: min(460px, 72vw);
}

.topbar-state-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topbar-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.tablet-outline-toggle,
.mobile-pane-switch {
  display: none;
}

.review-three-pane {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 400px;
  gap: 12px;
  height: calc(100vh - 180px);
  min-height: 540px;
  min-width: 0;
}

.pane-slot {
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.drawer-outline-host {
  height: calc(100vh - 96px);
}

.lightbox-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 10px;
}

.lightbox-canvas {
  max-height: 70vh;
  overflow: auto;
  padding: 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
  text-align: center;
}

.lightbox-image {
  display: inline-block;
  max-width: none;
  height: auto;
  background: #ffffff;
}

@media (max-width: 1279px) {
  .tablet-outline-toggle {
    display: inline-flex;
  }

  .review-three-pane {
    grid-template-columns: minmax(0, 1fr) 360px;
  }

  .pane-outline {
    display: none;
  }
}

@media (max-width: 767px) {
  .tablet-outline-toggle {
    display: none;
  }

  .mobile-pane-switch {
    display: block;
  }

  .review-three-pane {
    grid-template-columns: minmax(0, 1fr);
    height: auto;
    min-height: 0;
  }

  .pane-slot {
    height: auto;
  }

  .review-three-pane[data-mobile-pane="outline"] .pane-outline,
  .review-three-pane[data-mobile-pane="content"] .pane-content,
  .review-three-pane[data-mobile-pane="preview"] .pane-preview {
    display: block;
  }

  .review-three-pane[data-mobile-pane="outline"] .pane-content,
  .review-three-pane[data-mobile-pane="outline"] .pane-preview,
  .review-three-pane[data-mobile-pane="content"] .pane-outline,
  .review-three-pane[data-mobile-pane="content"] .pane-preview,
  .review-three-pane[data-mobile-pane="preview"] .pane-outline,
  .review-three-pane[data-mobile-pane="preview"] .pane-content {
    display: none;
  }
}
</style>
