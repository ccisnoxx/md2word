<!-- 文件：frontend/src/components/TranslationQaReviewPanel.vue -->
<!-- 用途：为队列抽屉和详情页复用提供紧凑的翻译 QA 复核面板。 -->
<template>
  <WorkbenchDrawerSurface
    label="翻译 QA 复核面板"
    kicker="翻译 QA 复核"
    :title="displayJobId"
    :subtitle="displayFilename"
    root-class="translation-qa-review-panel app-scrollbar-persistent"
    header-class="qa-review-header"
    body-class="qa-review-body app-scrollbar-persistent"
    footer-class="qa-review-footer"
  >
    <template #actions>
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
    </template>
    <div>
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
        <EvidenceSurfaceSection
          title="当前状态"
          description="先看可复核性、对照证据、AI 调用与质量摘要，再决定是否进入片段级复核。"
          aria-label="QA 当前状态"
          root-class="qa-current-state-section"
        >
          <section class="qa-summary-strip" aria-label="QA 证据摘要">
            <article v-for="metric in summaryMetrics" :key="metric.label" class="qa-summary-chip">
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
              <small>{{ metric.helper }}</small>
            </article>
          </section>
          <section class="qa-evidence-overview" aria-label="QA 状态和证据概览">
            <article v-for="group in qaEvidenceGroups" :key="group.title" class="qa-evidence-group">
              <h3>{{ group.title }}</h3>
              <dl>
                <div v-for="item in group.items" :key="item.label">
                  <dt>{{ item.label }}</dt>
                  <dd :class="{ mono: item.mono }">{{ item.value }}</dd>
                </div>
              </dl>
            </article>
          </section>
        </EvidenceSurfaceSection>

        <EvidenceSurfaceSection
          title="下一步建议"
          description="只根据当前可复核性、问题归因和证据完整度给出建议，不替代人工判断。"
          aria-label="QA 下一步建议"
        >
          <el-alert
            class="qa-guidance-alert"
            :type="qaEvidenceGuidance.type"
            :closable="false"
            show-icon
            :title="qaEvidenceGuidance.title"
          >
            <p>{{ qaEvidenceGuidance.description }}</p>
          </el-alert>
          <el-alert
            v-if="qa && qa.available && !qa.summary.source_comparison_available"
            type="info"
            :closable="false"
            show-icon
            :title="translationQaSourceComparisonReasonText(qa.summary.source_comparison_reason)"
          />
        </EvidenceSurfaceSection>

        <EvidenceSurfaceSection
          title="片段对照"
          :description="`当前片段：${segmentCounterText}`"
          aria-label="片段对照"
          root-class="segment-review-surface"
        >
          <template #actions>
            <div class="segment-nav">
              <el-button :icon="ArrowLeft" size="small" :disabled="!canMovePrevious" @click="moveSegment(-1)">上一段</el-button>
              <el-button :icon="ArrowRight" size="small" :disabled="!canMoveNext" @click="moveSegment(1)">下一段</el-button>
            </div>
          </template>

          <article v-if="activeSegment" class="segment-comparison" :aria-label="`片段 ${activeSegment.id}`">
            <header class="segment-meta">
              <div>
                <strong class="mono">{{ activeSegment.id }}</strong>
                <span>
                  {{ activeSegment.block_type }} · 页 {{ translationQaPageLabel(activeSegment.page_index) }} · 顺序
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
        </EvidenceSurfaceSection>

        <EvidenceSurfaceSection
          title="关键证据"
          description="保留 DocumentIR、AI 调用日志和调试归档的原始文件 ID，便于排障复制。"
          aria-label="关键证据"
          root-class="qa-evidence-summary"
        >
          <EvidenceKeyValueList class="evidence-row-list" :items="qaTechnicalEvidenceItems" />
          <div class="evidence-row evidence-row-flags">
            <span>质量标记</span>
            <div class="flag-list">
              <el-tag v-for="flag in qa?.summary.quality_flags || []" :key="flag" size="small" effect="plain">{{ flag }}</el-tag>
              <strong v-if="!qa?.summary.quality_flags.length">-</strong>
            </div>
          </div>
        </EvidenceSurfaceSection>
      </template>
    </div>
    <template #footer>
      <div>
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
        <ShortcutHintList v-if="showShortcutHints" :items="qaReviewShortcutHints" />
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
      </div>
    </template>
  </WorkbenchDrawerSurface>
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
import EvidenceKeyValueList from "@/components/EvidenceKeyValueList.vue";
import EvidenceSurfaceSection from "@/components/EvidenceSurfaceSection.vue";
import ShortcutHintList from "@/components/ShortcutHintList.vue";
import WorkbenchDrawerSurface from "@/components/WorkbenchDrawerSurface.vue";
import type { ShortcutHint } from "@/utils/keyboardShortcuts";
import { formatDateTime, getJobSourceFilename, translationQaStatusTagType, translationQaStatusText } from "@/utils/format";
import type { ApiClientError } from "@/utils/errors";
import {
  buildTranslationQaEvidenceGuidance,
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
import type { EvidenceKeyValueItem } from "@/components/EvidenceKeyValueList.vue";

const qaReviewShortcutHints: ShortcutHint[] = [
  { keys: ["Esc"], label: "关闭" },
  { keys: ["Cmd/Ctrl", "Enter"], label: "保存并下一条" },
  { keys: ["J/K"], label: "切换片段" },
];

type QaEvidenceOverviewGroup = {
  title: string;
  items: Array<{
    label: string;
    value: string;
    mono?: boolean;
  }>;
};

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
const qaEvidenceGuidance = computed(() =>
  buildTranslationQaEvidenceGuidance(props.qa, props.form.status, props.form.issue_type),
);
const sourceComparisonStatusText = computed(() => {
  if (!props.qa) {
    return "未加载";
  }
  if (props.qa.summary.source_comparison_available) {
    return "可用";
  }
  return translationQaSourceComparisonReasonText(props.qa.summary.source_comparison_reason);
});
const qaEvidenceGroups = computed<QaEvidenceOverviewGroup[]>(() => [
  {
    title: "复核状态",
    items: [
      { label: "可用性", value: availabilityText.value },
      { label: "当前状态", value: translationQaStatusText[props.form.status] },
      { label: "问题归因", value: props.form.issue_type ? translationQaIssueTypeText[props.form.issue_type] : "未选择" },
    ],
  },
  {
    title: "对照证据",
    items: [
      { label: "源文对照", value: sourceComparisonStatusText.value },
      { label: "片段数量", value: props.qa ? `${props.qa.summary.returned_segment_count}/${props.qa.summary.final_segment_count}` : "-" },
      { label: "术语命中", value: String(props.qa?.summary.term_trace_count ?? "-") },
    ],
  },
  {
    title: "调用与质量",
    items: [
      { label: "AI 调用状态", value: aiCallSummaryText.value },
      { label: "AI 调用数", value: String(props.qa?.summary.ai_call_count ?? "-") },
      { label: "质量标记", value: props.qa?.summary.quality_flags.length ? `${props.qa.summary.quality_flags.length} 项` : "-" },
    ],
  },
]);
const summaryMetrics = computed(() => [
  {
    label: "片段",
    value: props.qa ? `${props.qa.summary.returned_segment_count}/${props.qa.summary.final_segment_count}` : "-",
    helper: "返回/总数",
  },
  {
    label: "术语命中",
    value: props.qa?.summary.term_trace_count ?? "-",
    helper: props.qa?.summary.term_trace_count ? "有命中" : "无命中",
  },
  {
    label: "AI 调用",
    value: props.qa?.summary.ai_call_count ?? "-",
    helper: aiCallSummaryText.value,
  },
  {
    label: "调试归档",
    value: translationQaDebugArchiveStateText(debugArchiveState.value),
    helper: translationQaDebugArchiveHelper(props.qa),
  },
]);
const qaTechnicalEvidenceItems = computed<EvidenceKeyValueItem[]>(() => [
  { label: "DocumentIR", value: props.qa?.artifacts.document_ir_file_id || "-", mono: true },
  { label: "AI 调用日志", value: joinIds(props.qa?.artifacts.ai_call_log_file_ids || []), mono: true },
  { label: "调试归档", value: joinIds(props.qa?.artifacts.ai_debug_archive_file_ids || []), mono: true },
  { label: "AI 调用", value: aiCallSummaryText.value },
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

:deep(.qa-review-header) {
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
.segment-tags,
.flag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  align-items: center;
}

:deep(.qa-review-body) {
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

.qa-guidance-alert p {
  margin: 4px 0 0;
}

.qa-evidence-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--app-space-2);
}

.qa-evidence-group {
  display: grid;
  gap: var(--app-space-2);
  min-width: 0;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface);
}

.qa-evidence-group h3 {
  margin: 0;
  font-size: 14px;
}

.qa-evidence-group dl {
  display: grid;
  gap: 8px;
  margin: 0;
}

.qa-evidence-group dl div {
  display: grid;
  gap: 2px;
}

.qa-evidence-group dt {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.qa-evidence-group dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
  font-size: 13px;
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

.qa-evidence-heading {
  display: grid;
  gap: 4px;
  padding: var(--app-space-3);
  border-bottom: 1px solid var(--app-color-border-soft);
}

.qa-evidence-heading h3,
.qa-evidence-heading p {
  margin: 0;
}

.qa-evidence-heading h3 {
  font-size: 14px;
}

.qa-evidence-heading p {
  color: var(--app-color-text-muted);
  font-size: 12px;
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

:deep(.qa-review-footer) {
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

.review-meta {
  margin: 0;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

@media (max-width: 760px) {
  .translation-qa-review-panel {
    display: block;
    height: 100%;
    max-height: 100dvh;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 0;
  }

  :deep(.qa-review-header),
  :deep(.qa-review-body),
  :deep(.qa-review-footer) {
    padding: var(--app-space-3);
  }

  :deep(.qa-review-body) {
    min-height: auto;
    overflow: visible;
  }

  :deep(.qa-review-footer) {
    display: block;
    padding-bottom: calc(var(--app-space-3) + env(safe-area-inset-bottom));
  }

  .qa-summary-strip,
  .qa-evidence-overview,
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

  .footer-command-row {
    position: sticky;
    z-index: 1;
    bottom: calc(-1 * var(--app-space-3) - env(safe-area-inset-bottom));
    display: block;
    margin: var(--app-space-3) calc(-1 * var(--app-space-3)) 0;
    padding: var(--app-space-2) var(--app-space-3) calc(var(--app-space-2) + env(safe-area-inset-bottom));
    border-top: 1px solid var(--app-color-border);
    background: var(--app-color-surface-elevated);
  }

  .footer-command-row :deep(.shortcut-hint-list) {
    display: none;
  }

  .review-actions {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 6px;
    width: 100%;
  }

  .review-actions :deep(.el-button) {
    min-width: 0;
    padding-inline: 6px;
  }

  .review-actions :deep(.el-button + .el-button) {
    margin-left: 0;
  }
}
</style>
