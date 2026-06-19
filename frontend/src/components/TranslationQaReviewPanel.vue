<!-- File: frontend/src/components/TranslationQaReviewPanel.vue -->
<!-- Purpose: Shared dense Translation QA review panel for queue drawer and future detail-page reuse. -->
<template>
  <section class="translation-qa-review-panel" aria-label="翻译 QA 复核面板">
    <header class="qa-review-header">
      <div class="qa-review-identity">
        <p class="page-kicker">Translation QA Review</p>
        <h2>{{ displayJobId }}</h2>
        <p :title="displayFilename">{{ displayFilename }}</p>
      </div>
      <div class="qa-review-header-actions">
        <el-tag v-if="qa" :type="translationQaStatusTagType(form.status)" effect="plain">
          {{ translationQaStatusText[form.status] }}
        </el-tag>
        <el-tag :type="availabilityTagType" effect="plain">{{ availabilityText }}</el-tag>
        <el-button :icon="Refresh" :loading="loading" text @click="$emit('refresh')">刷新</el-button>
        <el-button v-if="showOpenDetail" :icon="TopRight" text :disabled="!job && !qa" @click="$emit('open-detail')">
          详情页
        </el-button>
        <el-button v-if="showClose" :icon="Close" text aria-label="关闭 QA 抽屉" @click="$emit('close')" />
      </div>
    </header>

    <div class="qa-review-body">
      <ApiErrorAlert :error="error" />

      <div v-if="queueCleared" class="qa-review-empty" aria-live="polite">
        <h3>当前队列已清空</h3>
        <p>当前筛选下没有下一条可处理的翻译 QA 任务。</p>
        <div class="qa-review-empty-actions">
          <el-button :icon="Refresh" @click="$emit('refresh')">刷新队列</el-button>
          <el-button type="primary" @click="$emit('close')">返回列表</el-button>
        </div>
      </div>

      <el-skeleton v-else-if="loading && !qa" :rows="8" animated />

      <template v-else>
        <section class="qa-summary-strip" aria-label="QA 证据摘要">
          <article v-for="metric in summaryMetrics" :key="metric.label" class="qa-summary-chip">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
            <small>{{ metric.helper }}</small>
          </article>
        </section>

        <el-alert
          v-if="qa && !qa.available"
          type="warning"
          :closable="false"
          show-icon
          :title="translationQaAvailabilityReasonText(qa.availability_reason)"
        />
        <el-alert
          v-else-if="qa && !qa.summary.source_comparison_available"
          type="info"
          :closable="false"
          show-icon
          :title="translationQaSourceComparisonReasonText(qa.summary.source_comparison_reason)"
        />

        <section class="segment-review-surface" aria-label="片段对照">
          <div class="segment-review-header">
            <div>
              <h3>片段对照</h3>
              <p>{{ segmentCounterText }}</p>
            </div>
            <div class="segment-nav">
              <el-button :icon="ArrowLeft" size="small" :disabled="!canMovePrevious" @click="moveSegment(-1)">上一段</el-button>
              <el-button :icon="ArrowRight" size="small" :disabled="!canMoveNext" @click="moveSegment(1)">下一段</el-button>
            </div>
          </div>

          <article v-if="activeSegment" class="segment-comparison" :aria-label="`片段 ${activeSegment.id}`">
            <header class="segment-meta">
              <div>
                <strong class="mono">{{ activeSegment.id }}</strong>
                <span>
                  {{ activeSegment.block_type }} · page {{ translationQaPageLabel(activeSegment.page_index) }} · order
                  {{ activeSegment.order }}
                </span>
              </div>
              <div class="segment-tags">
                <el-tag size="small" :type="activeSegment.source_available ? 'success' : 'info'" effect="plain">
                  {{ activeSegment.source_available ? "有源文对照" : "无源文对照" }}
                </el-tag>
                <el-tag size="small" :type="activeSegment.termTraceCount ? 'success' : 'info'" effect="plain">
                  {{ activeSegment.termTraceCount }} 条术语命中
                </el-tag>
              </div>
            </header>
            <div class="segment-columns">
              <section>
                <span>源文</span>
                <p>{{ activeSegment.source_text || sourceUnavailableText }}</p>
              </section>
              <section>
                <span>AI 译文</span>
                <p>{{ activeSegment.ai_translation_text || sourceUnavailableText }}</p>
              </section>
              <section>
                <span>最终文本</span>
                <p>{{ activeSegment.final_text || "-" }}</p>
              </section>
            </div>
            <div v-if="activeSegment.termTraces.length" class="term-trace-strip" aria-label="当前片段术语命中">
              <span v-for="trace in activeSegment.termTraces" :key="`${trace.provider_trace_id || trace.source_term || '-'}-${trace.match_start}`">
                {{ trace.source_term || "-" }} → {{ trace.target_term || "-" }}
                <small>{{ translationQaTermTraceRangeText(trace) }}</small>
              </span>
            </div>
          </article>

          <div v-else class="segment-empty-state">
            <strong>暂无片段证据</strong>
            <p>{{ qa ? translationQaAvailabilityReasonText(qa.availability_reason) : "正在等待 QA 证据。" }}</p>
          </div>
        </section>

        <section class="qa-evidence-summary" aria-label="关键证据">
          <div class="evidence-row">
            <span>DocumentIR</span>
            <strong class="mono">{{ qa?.artifacts.document_ir_file_id || "-" }}</strong>
          </div>
          <div class="evidence-row">
            <span>AI 调用日志</span>
            <strong class="mono">{{ joinIds(qa?.artifacts.ai_call_log_file_ids || []) }}</strong>
          </div>
          <div class="evidence-row">
            <span>Debug 归档</span>
            <strong class="mono">{{ joinIds(qa?.artifacts.ai_debug_archive_file_ids || []) }}</strong>
          </div>
          <div class="evidence-row">
            <span>AI calls</span>
            <strong>{{ aiCallSummaryText }}</strong>
          </div>
          <div class="evidence-row">
            <span>Quality flags</span>
            <div class="flag-list">
              <el-tag v-for="flag in qa?.summary.quality_flags || []" :key="flag" size="small" effect="plain">{{ flag }}</el-tag>
              <strong v-if="!qa?.summary.quality_flags.length">-</strong>
            </div>
          </div>
        </section>
      </template>
    </div>

    <footer class="qa-review-footer">
      <el-form class="review-form" label-position="top" aria-label="QA 复核表单">
        <el-form-item label="状态">
          <el-select v-model="draftStatus" :disabled="!qaEditable" aria-label="QA 状态">
            <el-option
              v-for="option in translationQaStatusOptions"
              :key="option"
              :label="translationQaStatusText[option]"
              :value="option"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="问题归因">
          <el-select v-model="draftIssueType" clearable placeholder="可选" :disabled="!qaEditable" aria-label="QA 问题归因">
            <el-option
              v-for="option in translationQaIssueTypeOptions"
              :key="option"
              :label="translationQaIssueTypeText[option]"
              :value="option"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="draftNote"
            type="textarea"
            :rows="2"
            maxlength="1000"
            show-word-limit
            :disabled="!qaEditable"
            aria-label="QA 备注"
          />
        </el-form-item>
      </el-form>

      <div class="footer-command-row">
        <div v-if="showShortcutHints" class="shortcut-hints" aria-label="快捷键提示">
          <span><kbd>Esc</kbd>关闭</span>
          <span><kbd>⌘/Ctrl</kbd>+<kbd>Enter</kbd>保存并下一条</span>
          <span><kbd>J</kbd>/<kbd>K</kbd>切换片段</span>
        </div>
        <div class="review-actions">
          <el-button v-if="showClose" :disabled="saving" @click="$emit('close')">关闭</el-button>
          <el-button :loading="saving" :disabled="!qaEditable" @click="$emit('submit')">{{ submitLabel }}</el-button>
          <el-button
            v-if="showSubmitNext"
            type="primary"
            :loading="saving"
            :disabled="!qaEditable"
            @click="$emit('submit-next')"
          >
            {{ submitNextLabel }}
          </el-button>
        </div>
      </div>
      <p class="review-meta">
        最近复核：{{ qa?.qa.reviewed_by || "-" }} · {{ formatDateTime(qa?.qa.reviewed_at) }}
      </p>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { ArrowLeft, ArrowRight, Close, Refresh, TopRight } from "@element-plus/icons-vue";

import type {
  DocumentJobResponse,
  DocumentJobTranslationQaResponse,
  TranslationQaIssueType,
  TranslationQaStatus,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { formatDateTime, getJobSourceFilename, translationQaStatusTagType, translationQaStatusText } from "@/utils/format";
import type { ApiClientError } from "@/utils/errors";
import {
  buildTranslationQaSegmentRows,
  translationQaAvailabilityReasonText,
  translationQaDebugArchiveHelper,
  translationQaDebugArchiveState,
  translationQaDebugArchiveStateText,
  translationQaIssueTypeOptions,
  translationQaIssueTypeText,
  translationQaPageLabel,
  translationQaSourceComparisonReasonText,
  translationQaStatusCountText,
  translationQaStatusOptions,
  translationQaTermTraceRangeText,
  type TranslationQaReviewDraft,
} from "@/utils/translationQa";

const props = withDefaults(defineProps<{
  job: DocumentJobResponse | null;
  qa: DocumentJobTranslationQaResponse | null;
  form: TranslationQaReviewDraft;
  loading: boolean;
  saving: boolean;
  error: ApiClientError | null;
  queueCleared: boolean;
  activeSegmentIndex: number;
  showClose?: boolean;
  showOpenDetail?: boolean;
  showSubmitNext?: boolean;
  showShortcutHints?: boolean;
  submitLabel?: string;
  submitNextLabel?: string;
}>(), {
  showClose: true,
  showOpenDetail: true,
  showSubmitNext: true,
  showShortcutHints: true,
  submitLabel: "仅保存",
  submitNextLabel: "保存并下一条",
});

const emit = defineEmits<{
  "update:form": [value: TranslationQaReviewDraft];
  "segment-index-change": [value: number];
  submit: [];
  "submit-next": [];
  refresh: [];
  close: [];
  "open-detail": [];
}>();

const displayJobId = computed(() => props.job?.id || props.qa?.job_id || "无选中任务");
const displayFilename = computed(() => props.job ? getJobSourceFilename(props.job) : "当前筛选暂无下一条");
const qaEditable = computed(() => Boolean(props.qa?.available && !props.loading && !props.saving && !props.queueCleared));
const segmentRows = computed(() => buildTranslationQaSegmentRows(props.qa));
const activeSegment = computed(() => segmentRows.value[normalizedActiveSegmentIndex.value] || null);
const normalizedActiveSegmentIndex = computed(() => {
  if (!segmentRows.value.length) {
    return 0;
  }
  return Math.min(Math.max(props.activeSegmentIndex, 0), segmentRows.value.length - 1);
});
const canMovePrevious = computed(() => segmentRows.value.length > 0 && normalizedActiveSegmentIndex.value > 0);
const canMoveNext = computed(() => segmentRows.value.length > 0 && normalizedActiveSegmentIndex.value < segmentRows.value.length - 1);
const segmentCounterText = computed(() => {
  if (!segmentRows.value.length) {
    return "0 / 0";
  }
  return `${normalizedActiveSegmentIndex.value + 1} / ${segmentRows.value.length}`;
});
const sourceUnavailableText = computed(() => translationQaSourceComparisonReasonText(props.qa?.summary.source_comparison_reason || null));
const debugArchiveState = computed(() => translationQaDebugArchiveState(props.qa));
const availabilityText = computed(() => {
  if (props.queueCleared) {
    return "队列清空";
  }
  if (!props.qa) {
    return props.loading ? "加载中" : "未加载";
  }
  return props.qa.available ? "可复核" : "只读诊断";
});
const availabilityTagType = computed<"success" | "warning" | "info">(() => {
  if (props.qa?.available) {
    return "success";
  }
  if (props.qa && !props.qa.available) {
    return "warning";
  }
  return "info";
});
const aiCallSummaryText = computed(() => translationQaStatusCountText(props.qa?.summary.ai_call_statuses || {}));
const summaryMetrics = computed(() => [
  {
    label: "片段",
    value: props.qa ? `${props.qa.summary.returned_segment_count}/${props.qa.summary.final_segment_count}` : "-",
    helper: "returned/final",
  },
  {
    label: "术语命中",
    value: props.qa?.summary.term_trace_count ?? "-",
    helper: props.qa?.summary.term_trace_count ? "trace available" : "none",
  },
  {
    label: "AI calls",
    value: props.qa?.summary.ai_call_count ?? "-",
    helper: aiCallSummaryText.value,
  },
  {
    label: "Debug archive",
    value: translationQaDebugArchiveStateText(debugArchiveState.value),
    helper: translationQaDebugArchiveHelper(props.qa),
  },
]);

const draftStatus = computed<TranslationQaStatus>({
  get: () => props.form.status,
  set: (status) => emit("update:form", { ...props.form, status }),
});
const draftIssueType = computed<TranslationQaIssueType | null>({
  get: () => props.form.issue_type,
  set: (issue_type) => emit("update:form", { ...props.form, issue_type }),
});
const draftNote = computed<string>({
  get: () => props.form.note,
  set: (note) => emit("update:form", { ...props.form, note }),
});

function moveSegment(delta: number): void {
  if (!segmentRows.value.length) {
    return;
  }
  const nextIndex = Math.min(Math.max(normalizedActiveSegmentIndex.value + delta, 0), segmentRows.value.length - 1);
  emit("segment-index-change", nextIndex);
}

function joinIds(ids: string[]): string {
  return ids.length ? ids.join(", ") : "-";
}
</script>

<style scoped lang="scss">
.translation-qa-review-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  height: 100%;
  min-height: 0;
  color: var(--app-color-text);
  background: var(--app-color-surface);
}

.qa-review-header {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-3);
  align-items: flex-start;
  justify-content: space-between;
  padding: var(--app-space-4);
  border-bottom: 1px solid var(--app-color-border);
  background: var(--app-color-surface-elevated);
}

.qa-review-identity {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.qa-review-identity h2,
.qa-review-identity p {
  margin: 0;
}

.qa-review-identity h2 {
  overflow: hidden;
  font-size: 18px;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qa-review-identity p:last-child {
  overflow: hidden;
  color: var(--app-color-text-muted);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qa-review-header-actions,
.segment-nav,
.qa-review-empty-actions,
.review-actions,
.shortcut-hints,
.segment-tags,
.flag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  align-items: center;
}

.qa-review-body {
  display: grid;
  align-content: start;
  gap: var(--app-space-3);
  min-height: 0;
  overflow: auto;
  padding: var(--app-space-4);
}

.qa-summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--app-space-2);
}

.qa-summary-chip {
  display: grid;
  gap: 3px;
  min-width: 0;
  padding: var(--app-space-2) var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
}

.qa-summary-chip span,
.qa-summary-chip small {
  overflow: hidden;
  color: var(--app-color-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qa-summary-chip strong {
  overflow: hidden;
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.segment-review-surface,
.qa-evidence-summary,
.qa-review-empty {
  display: grid;
  gap: var(--app-space-3);
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.segment-review-header {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  align-items: flex-start;
  justify-content: space-between;
}

.segment-review-header h3,
.segment-review-header p,
.qa-review-empty h3,
.qa-review-empty p {
  margin: 0;
}

.segment-review-header h3,
.qa-review-empty h3 {
  font-size: 15px;
}

.segment-review-header p,
.qa-review-empty p {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.segment-comparison {
  display: grid;
  gap: var(--app-space-3);
  min-width: 0;
}

.segment-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  align-items: flex-start;
  justify-content: space-between;
}

.segment-meta > div:first-child {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.segment-meta span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.segment-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-2);
}

.segment-columns section {
  display: grid;
  align-content: start;
  gap: var(--app-space-2);
  min-height: 168px;
  min-width: 0;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
}

.segment-columns span {
  color: var(--app-color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.segment-columns p {
  margin: 0;
  color: var(--app-color-text);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.term-trace-strip {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.term-trace-strip span {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  max-width: 100%;
  padding: 4px 8px;
  border: 1px solid var(--app-color-accent-cyan-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-accent-cyan-soft);
  font-size: 12px;
}

.term-trace-strip small {
  color: var(--app-color-text-muted);
}

.segment-empty-state {
  display: grid;
  gap: 4px;
  min-height: 160px;
  place-content: center;
  color: var(--app-color-text-muted);
  text-align: center;
}

.segment-empty-state p {
  margin: 0;
  font-size: 13px;
}

.qa-evidence-summary {
  gap: 0;
  padding: 0;
  overflow: hidden;
}

.evidence-row {
  display: grid;
  grid-template-columns: 132px minmax(0, 1fr);
  gap: var(--app-space-3);
  align-items: start;
  padding: 10px var(--app-space-3);
  border-bottom: 1px solid var(--app-color-border-soft);
}

.evidence-row:last-child {
  border-bottom: 0;
}

.evidence-row > span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.evidence-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 13px;
}

.qa-review-footer {
  display: grid;
  gap: var(--app-space-2);
  padding: var(--app-space-3) var(--app-space-4);
  border-top: 1px solid var(--app-color-border);
  background: var(--app-color-surface-elevated);
}

.review-form {
  display: grid;
  grid-template-columns: 150px 170px minmax(220px, 1fr);
  gap: var(--app-space-3);
  align-items: start;
}

.review-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.review-form :deep(.el-select) {
  width: 100%;
}

.footer-command-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-3);
  align-items: center;
  justify-content: space-between;
}

.shortcut-hints {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

kbd {
  display: inline-grid;
  min-width: 22px;
  height: 20px;
  place-items: center;
  padding: 0 5px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
  color: var(--app-color-text);
  font-family: inherit;
  font-size: 11px;
}

.review-meta {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

@media (max-width: 760px) {
  .qa-review-header,
  .qa-review-body,
  .qa-review-footer {
    padding: var(--app-space-3);
  }

  .qa-summary-strip,
  .segment-columns,
  .review-form {
    grid-template-columns: 1fr;
  }

  .segment-columns section {
    min-height: 120px;
  }

  .evidence-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .footer-command-row,
  .review-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .review-actions :deep(.el-button + .el-button) {
    margin-left: 0;
  }
}
</style>
