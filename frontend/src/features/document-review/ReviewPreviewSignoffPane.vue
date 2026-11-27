<!-- 文件：frontend/src/features/document-review/ReviewPreviewSignoffPane.vue -->
<!-- 用途：统一复核工作台右栏，集成 Word 页级预览 PNG、页级质量指标与吸底统一复核签核（PATCH /review）。 -->
<template>
  <aside class="review-preview-signoff-pane" aria-label="Word 预览与复核签核">
    <div class="preview-panel">
      <div class="preview-tab-bar">
        <el-radio-group v-model="rightTab" size="small">
          <el-radio-button value="preview">Word 预览页</el-radio-button>
          <el-radio-button value="pages">页级指标</el-radio-button>
        </el-radio-group>
        <div v-if="rightTab === 'preview' && hasPreviewPages" class="preview-zoom-bar">
          <el-button size="small" text :disabled="previewZoom <= 60" @click="$emit('update:previewZoom', Math.max(60, previewZoom - 20))">-</el-button>
          <span class="zoom-value">{{ previewZoom }}%</span>
          <el-button size="small" text :disabled="previewZoom >= 200" @click="$emit('update:previewZoom', Math.min(200, previewZoom + 20))">+</el-button>
        </div>
      </div>

      <!-- Word 预览页 Tab -->
      <div v-if="rightTab === 'preview'" class="preview-content">
        <div class="mapping-strip">
          <el-tag size="small" :type="locationBadge.tagType" effect="plain">{{ locationBadge.label }}</el-tag>
          <el-button
            v-if="fallbackPreviewPageIndex !== null && selectedBlock?.location.preview_page_index === null && hasPreviewPages"
            size="small"
            link
            type="primary"
            @click="$emit('set-preview-page', fallbackPreviewPageIndex)"
          >
            定位相近第 {{ fallbackPreviewPageIndex + 1 }} 页
          </el-button>
        </div>

        <template v-if="hasPreviewPages">
          <div class="preview-pager">
            <el-button size="small" :disabled="!canStepPrevPage" @click="$emit('step-preview-page', -1)">上一页</el-button>
            <span class="pager-text">
              第 {{ (currentPreviewPage?.page_index ?? 0) + 1 }} / {{ previewResponse?.page_count ?? previewPages.length }} 页
            </span>
            <el-button size="small" :disabled="!canStepNextPage" @click="$emit('step-preview-page', 1)">下一页</el-button>
          </div>

          <div class="preview-canvas app-scrollbar-transient">
            <div v-if="currentPreviewImageLoading" class="preview-placeholder">正在加载 Word 预览页…</div>
            <div v-else-if="currentPreviewImageError" class="preview-placeholder is-error">
              <p>预览图片加载失败：{{ currentPreviewImageError }}</p>
              <el-button size="small" @click="$emit('download-draft')">下载内部草稿 DOCX</el-button>
            </div>
            <img
              v-else-if="currentPreviewImageUrl"
              :src="currentPreviewImageUrl"
              :alt="`Word 预览第 ${(currentPreviewPage?.page_index ?? 0) + 1} 页`"
              class="preview-image"
              :style="{ width: `${previewZoom}%` }"
            />
            <div v-else class="preview-placeholder">等待加载预览图片…</div>
          </div>
        </template>

        <div v-else class="preview-degraded">
          <el-tag size="small" type="warning" effect="plain">
            {{ previewResponse ? previewStatusText[previewResponse.status] || previewResponse.status : "预览不可用" }}
          </el-tag>
          <p class="degraded-reason">
            {{ previewError ? previewError.message : previewReasonLabel(previewResponse?.reason_code, previewResponse?.status) }}
          </p>
          <div class="degraded-actions">
            <el-button size="small" :loading="openingSourcePdf" @click="$emit('open-source-pdf')">
              打开源 PDF
            </el-button>
            <el-button size="small" type="primary" plain :loading="downloadingDraft" @click="$emit('download-draft')">
              下载内部草稿 DOCX
            </el-button>
          </div>
        </div>
      </div>

      <!-- 页级指标 Tab -->
      <div v-else class="pages-metrics-scroll app-scrollbar-persistent">
        <ApiErrorAlert :error="pagesError" />
        <div v-if="!pagesResponse || pagesResponse.availability !== 'available'" class="preview-degraded">
          <p class="degraded-reason">
            {{ pagesResponse?.reason_code ? `页级质量报告暂不可用（${pagesResponse.reason_code}）` : "当前任务暂无页级质量检查报告。" }}
          </p>
        </div>
        <template v-else>
          <div v-if="pagesResponse.report" class="page-report-summary">
            <div class="report-tags">
              <el-tag size="small" effect="plain">页数：{{ pagesResponse.report.page_count }}</el-tag>
              <el-tag
                size="small"
                :type="pagesResponse.report.evaluation_state === 'complete' ? 'success' : 'warning'"
                effect="plain"
              >
                {{ pagesResponse.report.evaluation_state === "complete" ? "检查完整" : "检查未完整" }}
              </el-tag>
            </div>
            <p v-if="pagesResponse.report.manual_checks.length" class="manual-checks-note">
              需人工核验：{{ pagesResponse.report.manual_checks.join("；") }}
            </p>
          </div>

          <div v-if="activePageMetrics" class="page-metric-card">
            <div class="page-metric-head">
              <strong>当前 Word 第 {{ activePageMetrics.preview_page_index + 1 }} 页检查</strong>
              <span v-if="activePageMetrics.flags.length" class="flag-total">{{ activePageMetrics.flags.length }} 项风险</span>
            </div>
            <ul class="rule-list">
              <li v-for="(rule, ruleKey) in activePageMetrics.rules" :key="ruleKey">
                <span>{{ qualityRuleText[ruleKey] || ruleKey }}</span>
                <el-tag size="small" :type="rule?.checked ? 'success' : 'info'" effect="plain">
                  {{ rule?.checked ? "已检查" : "未检查" }}
                </el-tag>
              </li>
            </ul>
            <div v-if="activePageMetrics.flags.length" class="page-flags">
              <el-tag
                v-for="(flag, index) in activePageMetrics.flags"
                :key="`${flag.code}-${index}`"
                size="small"
                :type="flag.severity === 'warning' ? 'warning' : 'info'"
                effect="plain"
              >
                {{ pageFlagText[flag.code] || flag.code }}
              </el-tag>
            </div>
            <div v-if="activePageMetrics.block_candidates.length" class="candidates-wrap">
              <span class="candidates-label">本页候选块（点击跳转）：</span>
              <div class="candidates-list">
                <el-button
                  v-for="cand in activePageMetrics.block_candidates"
                  :key="cand.block_id"
                  size="small"
                  text
                  type="primary"
                  @click="$emit('select-block', cand.block_id)"
                >
                  {{ cand.block_id }}
                </el-button>
              </div>
            </div>
          </div>
          <p v-else class="degraded-reason">当前预览页暂无对应页级指标明细。</p>
        </template>
      </div>
    </div>

    <!-- 吸底统一复核签核区 -->
    <section class="signoff-panel" aria-label="统一复核签核">
      <div class="signoff-head">
        <h3>统一复核结论</h3>
        <div class="signoff-head-tags">
          <el-tag
            v-if="currentReview"
            size="small"
            :type="jobReviewStatusTagType(currentReview.status)"
            effect="plain"
          >
            当前：{{ jobReviewStatusText[currentReview.status] || currentReview.status }}
          </el-tag>
          <el-button size="small" link type="primary" @click="$emit('open-history')">
            历史记录{{ currentReview?.sequence ? ` (${currentReview.sequence})` : "" }}
          </el-button>
        </div>
      </div>

      <el-alert
        v-if="currentReview?.validity_reason"
        type="warning"
        :closable="false"
        show-icon
        :title="reviewValidityReasonLabel(currentReview.validity_reason)"
      />

      <el-alert
        v-if="reviewConflictActive"
        type="error"
        :closable="false"
        show-icon
        title="提交冲突（409）：任务产物或语义报告已更新"
      >
        <div class="conflict-body">
          <p>你当前填写的复核结论与备注已保留，系统不会自动覆盖。请刷新获取最新来源后再提交。</p>
          <el-button size="small" type="danger" plain @click="$emit('refresh-preserve-draft')">
            刷新并重新核对
          </el-button>
        </div>
      </el-alert>

      <ApiErrorAlert v-else :error="reviewSubmitError" />

      <div class="signoff-form">
        <div class="signoff-row">
          <label class="signoff-field">
            <span>复核状态</span>
            <el-select v-model="reviewForm.status" size="small" aria-label="统一复核状态">
              <el-option
                v-for="statusOption in reviewStatusOptions"
                :key="statusOption"
                :label="jobReviewStatusText[statusOption]"
                :value="statusOption"
              />
            </el-select>
          </label>
          <label class="signoff-field">
            <span>问题归因</span>
            <el-select v-model="reviewForm.issueType" size="small" clearable placeholder="可选" aria-label="复核问题归因">
              <el-option
                v-for="issueOption in reviewIssueTypeOptions"
                :key="issueOption"
                :label="reviewIssueTypeText[issueOption]"
                :value="issueOption"
              />
            </el-select>
          </label>
        </div>

        <el-input
          v-model="reviewForm.note"
          type="textarea"
          :rows="2"
          maxlength="1000"
          show-word-limit
          placeholder="填写人工复核说明（可选，最多 1000 字）"
          aria-label="统一复核备注"
        />

        <div v-if="mustTickTableSemanticsToApprove" class="semantics-ack-box">
          <el-checkbox v-if="tableSemanticsReportSha256" v-model="reviewForm.acknowledgeTableSemantics">
            确认已核对表格语义归属报告（发现 {{ tableSemanticsFindingsCount }} 处，摘要 <span class="mono">{{ shortHash(tableSemanticsReportSha256, 12) }}</span>）
          </el-checkbox>
          <p v-else class="semantics-ack-missing">
            当前存在表格语义归属冲突，但未获取到表格报告摘要（report_sha256），暂不能直接批准，请先刷新核对。
          </p>
        </div>

        <div class="signoff-actions">
          <el-button
            type="primary"
            :loading="submittingReview"
            :disabled="!canSubmitReview"
            @click="$emit('submit-review')"
          >
            提交复核
          </el-button>
          <el-button
            v-if="currentReview?.status === 'approved'"
            type="success"
            plain
            @click="$emit('go-publication')"
          >
            前往发布与交付
          </el-button>
        </div>
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import type {
  DocumentPreviewPageResponse,
  DocumentPreviewResponse,
  DocumentQualityPagesResponse,
  DocumentReviewBlockItemResponse,
  DocumentReviewResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import type { ApiClientError } from "@/utils/errors";
import { jobReviewStatusTagType, jobReviewStatusText } from "@/utils/format";
import {
  formatReviewLocationBadge,
  pageFlagText,
  previewReasonLabel,
  previewStatusText,
  qualityRuleText,
  reviewIssueTypeOptions,
  reviewIssueTypeText,
  reviewStatusOptions,
  reviewValidityReasonLabel,
  shortHash,
} from "./documentReviewFormat";
import type { DocumentReviewSession } from "./useDocumentReviewSession";

const props = defineProps<{
  selectedBlock: DocumentReviewBlockItemResponse | null;
  previewResponse: DocumentPreviewResponse | null;
  previewPages: DocumentPreviewPageResponse[];
  currentPreviewPage: DocumentPreviewPageResponse | null;
  currentPreviewImageUrl: string;
  currentPreviewImageLoading: boolean;
  currentPreviewImageError: string;
  previewError: ApiClientError | null;
  previewZoom: number;
  pagesResponse: DocumentQualityPagesResponse | null;
  pagesError: ApiClientError | null;
  currentReview: DocumentReviewResponse | null;
  reviewForm: DocumentReviewSession["reviewForm"];
  mustTickTableSemanticsToApprove: boolean;
  tableSemanticsReportSha256: string | null;
  tableSemanticsFindingsCount: number;
  canSubmitReview: boolean;
  submittingReview: boolean;
  reviewSubmitError: ApiClientError | null;
  reviewConflictActive: boolean;
  openingSourcePdf: boolean;
  downloadingDraft: boolean;
}>();

defineEmits<{
  "update:previewZoom": [value: number];
  "set-preview-page": [pageIndex: number];
  "step-preview-page": [delta: 1 | -1];
  "select-block": [blockId: string];
  "submit-review": [];
  "open-history": [];
  "refresh-preserve-draft": [];
  "open-source-pdf": [];
  "download-draft": [];
  "go-publication": [];
}>();

const rightTab = ref<"preview" | "pages">("preview");

const locationBadge = computed(() => formatReviewLocationBadge(props.selectedBlock?.location));
const fallbackPreviewPageIndex = computed(() => props.selectedBlock?.location.fallback_page_index ?? null);
const hasPreviewPages = computed(
  () => props.previewResponse?.status === "succeeded" && props.previewPages.length > 0,
);

const currentPreviewPosition = computed(() =>
  props.currentPreviewPage
    ? props.previewPages.findIndex((item) => item.page_index === props.currentPreviewPage!.page_index)
    : -1,
);
const canStepPrevPage = computed(() => currentPreviewPosition.value > 0);
const canStepNextPage = computed(
  () => currentPreviewPosition.value >= 0 && currentPreviewPosition.value < props.previewPages.length - 1,
);

const activePageMetrics = computed(() => {
  const items = props.pagesResponse?.items ?? [];
  if (!items.length) {
    return null;
  }
  const targetIndex = props.currentPreviewPage?.page_index ?? 0;
  return items.find((item) => item.preview_page_index === targetIndex) ?? items[0] ?? null;
});
</script>

<style scoped lang="scss">
.review-preview-signoff-pane {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.preview-panel {
  flex: 1 1 auto;
  min-height: 220px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-lg);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
  overflow: hidden;
}

.preview-tab-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--app-color-border-soft);
  background: var(--app-color-surface-soft);
  flex: 0 0 auto;
}

.preview-zoom-bar {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.zoom-value {
  font-size: 12px;
  color: var(--app-color-text-muted);
  min-width: 38px;
  text-align: center;
}

.preview-content {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  gap: 8px;
}

.mapping-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.preview-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.pager-text {
  font-size: 12px;
  color: var(--app-color-text-muted);
}

.preview-canvas {
  flex: 1 1 auto;
  min-height: 160px;
  overflow: auto;
  padding: 8px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
  text-align: center;
}

.preview-image {
  display: inline-block;
  max-width: none;
  height: auto;
  border: 1px solid var(--app-color-border-soft);
  background: #ffffff;
}

.preview-placeholder {
  padding: 28px 12px;
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.preview-placeholder.is-error {
  color: var(--app-color-danger, #dc2626);
}

.preview-degraded {
  display: grid;
  gap: 10px;
  align-content: start;
  padding: 14px 4px;
}

.degraded-reason {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.degraded-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pages-metrics-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 12px;
  display: grid;
  gap: 10px;
  align-content: start;
}

.page-report-summary,
.page-metric-card {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-soft);
}

.report-tags,
.page-flags,
.candidates-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.manual-checks-note {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.page-metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.flag-total {
  color: var(--app-color-warning, #b45309);
  font-weight: 600;
  font-size: 12px;
}

.rule-list {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
}

.rule-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.candidates-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--app-color-text-muted);
}

.signoff-panel {
  flex: 0 0 auto;
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-lg);
  background: var(--app-color-surface);
  box-shadow: var(--app-shadow-subtle);
}

.signoff-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.signoff-head h3 {
  margin: 0;
  font-size: 14px;
  color: var(--app-color-text);
}

.signoff-head-tags {
  display: flex;
  align-items: center;
  gap: 8px;
}

.conflict-body {
  display: grid;
  gap: 6px;
  font-size: 12px;
}

.conflict-body p {
  margin: 0;
}

.signoff-form {
  display: grid;
  gap: 8px;
}

.signoff-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.signoff-field {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: var(--app-color-text-muted);
}

.semantics-ack-box {
  padding: 8px 10px;
  border: 1px solid var(--app-color-warning, #d97706);
  border-radius: var(--app-radius-md);
  background: rgba(217, 119, 6, 0.08);
}

.semantics-ack-box :deep(.el-checkbox__label) {
  white-space: normal;
  line-height: 1.4;
  font-size: 12px;
}

.semantics-ack-missing {
  margin: 0;
  color: var(--app-color-danger, #dc2626);
  font-size: 12px;
  line-height: 1.4;
}

.signoff-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
