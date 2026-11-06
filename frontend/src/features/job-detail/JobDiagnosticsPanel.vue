<template>
  <el-card class="page-section diagnostic-overview-card card-flat" shadow="never" aria-live="polite">
    <div class="section-header">
      <div>
        <h2 class="section-title">诊断摘要</h2>
        <p class="section-subtitle">用现有任务、事件、文件和回调数据说明当前结果、关键证据和下一步。</p>
      </div>
      <el-button
        :icon="Refresh"
        :loading="loading || eventsLoading || filesLoading || callbackSummaryLoading || translationBatchesLoading"
        @click="loadAll"
      >
        刷新诊断
      </el-button>
    </div>
    <EvidenceSurfaceSection
      title="下一步建议"
      description="只根据当前任务状态和后端动作可用性给出建议，不自动执行修复或重试。"
      aria-label="下一步建议"
      root-class="diagnostic-section-block"
    >
      <el-alert
        v-if="diagnosticRecommendation"
        class="diagnostic-recommendation"
        :type="diagnosticRecommendation.type"
        :closable="false"
        show-icon
        :title="diagnosticRecommendation.title"
      >
        <p>{{ diagnosticRecommendation.description }}</p>
        <strong>{{ diagnosticRecommendation.actionLabel }}</strong>
      </el-alert>
    </EvidenceSurfaceSection>
    <div class="diagnostic-summary-grid" aria-label="当前诊断摘要">
      <div v-for="item in diagnosticSummaryFacts" :key="item.label" class="diagnostic-summary-item">
        <span>{{ item.label }}</span>
        <strong :class="{ mono: item.mono }">{{ item.value }}</strong>
      </div>
    </div>
    <EvidenceSurfaceSection
      title="关键证据"
      description="区分源文件、结果、DocumentIR、回调和最近错误事件；原始 ID/错误码保持可复制。"
      aria-label="关键证据"
      root-class="diagnostic-section-block"
    >
      <div class="diagnostic-evidence-grid">
        <article v-for="item in diagnosticEvidenceItems" :key="item.label" class="diagnostic-evidence-card">
          <span>{{ item.label }}</span>
          <strong :class="{ mono: item.mono }">{{ item.value }}</strong>
          <small>{{ item.helper }}</small>
        </article>
      </div>
    </EvidenceSurfaceSection>
    <EvidenceSurfaceSection
      v-if="usesTranslationResources(job)"
      title="翻译批次"
      description="翻译 Provider 批次摘要；AI 调用日志仅显示文件 ID，正文内容不进入此视图。"
      aria-label="翻译批次"
      root-class="diagnostic-section-block"
    >
      <template #actions>
        <el-button text type="primary" :loading="translationBatchesLoading" @click="loadTranslationBatches()">
          刷新批次
        </el-button>
      </template>
      <ApiErrorAlert
        :error="translationBatchesError"
        :diagnostic-context="jobErrorDiagnosticContext('document_jobs.translation_batches')"
      />
      <el-alert
        v-if="translationBatchConclusion"
        class="translation-batch-conclusion"
        :type="translationBatchConclusion.type"
        :closable="false"
        show-icon
        :title="translationBatchConclusion.title"
      >
        <p>{{ translationBatchConclusion.description }}</p>
        <p v-if="translationBatchConclusion.reason" class="translation-batch-conclusion-reason mono">
          {{ translationBatchConclusion.reason }}
        </p>
      </el-alert>
      <div v-if="translationBatches.length" class="translation-batch-summary-grid">
        <div v-for="item in translationBatchSummaryItems" :key="item.label" class="translation-batch-summary-item">
          <span>{{ item.label }}</span>
          <strong class="mono">{{ item.value }}</strong>
        </div>
      </div>
      <el-table
        v-if="translationBatches.length"
        v-loading="translationBatchesLoading"
        class="translation-batch-table"
        :data="translationBatches"
        table-layout="fixed"
        :row-class-name="translationBatchTableRowClassName"
      >
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <div class="translation-batch-status">
              <el-tag size="small" :type="translationBatchStatusTagType(row)" effect="plain">
                {{ translationBatchStatusText(row.status) }}
              </el-tag>
              <div v-if="translationBatchFlagTexts(row).length" class="translation-batch-flags">
                <el-tag
                  v-for="flag in translationBatchFlagTexts(row)"
                  :key="flag"
                  size="small"
                  type="warning"
                  effect="plain"
                >
                  {{ flag }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="批次" min-width="210" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="translation-batch-id mono">{{ row.batch_id }}</div>
            <div class="translation-batch-meta mono">
              root=
              {{ row.root_batch_id }}
              · parent=
              {{ row.parent_batch_id || "-" }}
              · level=
              {{ row.split_level }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="页范围" width="110">
          <template #default="{ row }">{{ translationBatchPageRangeText(row) }}</template>
        </el-table-column>
        <el-table-column label="规模" width="150">
          <template #default="{ row }">{{ translationBatchScaleText(row) }}</template>
        </el-table-column>
        <el-table-column label="尝试" width="90">
          <template #default="{ row }">{{ translationBatchAttemptText(row) }}</template>
        </el-table-column>
        <el-table-column label="finish_reason" width="135" show-overflow-tooltip>
          <template #default="{ row }"><span class="mono">{{ row.finish_reason || "-" }}</span></template>
        </el-table-column>
        <el-table-column label="错误摘要" min-width="220" show-overflow-tooltip>
          <template #default="{ row }"><span class="mono">{{ translationBatchErrorSummaryText(row) }}</span></template>
        </el-table-column>
        <el-table-column label="AI 调用日志" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div>{{ translationBatchAiCallLogSummaryText(row) }}</div>
            <div class="translation-batch-meta mono">{{ translationBatchFileIdsText(row.ai_call_log_file_ids) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-else
        v-loading="translationBatchesLoading"
        class="compact-empty"
        description="暂无翻译 Provider 批次记录"
      />
    </EvidenceSurfaceSection>
    <EvidenceSurfaceSection
      title="事件预览"
      description="优先查看最近错误/警告（error/warning）；完整事件流仍在“事件”页签。"
      aria-label="事件预览"
      root-class="diagnostic-section-block"
    >
      <template #actions>
        <el-button text type="primary" @click="openEventsTab">查看完整事件流</el-button>
      </template>
      <ApiErrorAlert :error="eventsError" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.diagnostic_event_preview')" />
      <div v-if="eventsLoading && !events.length" class="diagnostic-loading">事件加载中...</div>
      <ol v-else-if="diagnosticPreviewEvents.length" class="diagnostic-event-preview">
        <li
          v-for="event in diagnosticPreviewEvents"
          :key="event.id"
          :class="`is-${event.level}`"
        >
          <span>{{ formatDateTime(event.created_at) }} · {{ event.level }} · {{ jobStageText[event.stage] || event.stage }}</span>
          <strong class="mono">{{ event.event_type }}</strong>
          <p>{{ event.message }}</p>
          <small v-if="event.trace_id" class="mono">trace_id={{ event.trace_id }}</small>
        </li>
      </ol>
      <el-empty v-else class="compact-empty" description="暂无事件证据；可刷新诊断或稍后查看事件流" />
    </EvidenceSurfaceSection>
    <EvidenceSurfaceSection
      v-if="diagnosticRecoveryItems.length"
      title="恢复路径"
      description="部分诊断数据加载失败时，可单独刷新对应证据。"
      aria-label="错误恢复路径"
      root-class="diagnostic-section-block"
    >
      <div class="diagnostic-recovery-actions">
        <el-button v-if="filesError" :loading="filesLoading" @click="loadFiles()">刷新文件证据</el-button>
        <el-button v-if="callbackSummaryError" :loading="callbackSummaryLoading" @click="loadCallbackSummary()">
          刷新回调
        </el-button>
        <el-button v-if="eventsError" :loading="eventsLoading" @click="loadEvents()">刷新事件</el-button>
        <el-button v-if="translationBatchesError" :loading="translationBatchesLoading" @click="loadTranslationBatches()">
          刷新 Provider 批次
        </el-button>
      </div>
    </EvidenceSurfaceSection>
  </el-card>
  <el-card class="page-section card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">Word 质量证据</h2>
        <p class="section-subtitle">来自 generated_word 结果、DocumentIR 文件元数据和后端质量标记。</p>
      </div>
      <el-button :icon="Refresh" :loading="filesLoading" @click="loadFiles()">刷新质量证据</el-button>
    </div>
    <ApiErrorAlert :error="filesError" :diagnostic-context="jobErrorDiagnosticContext('document_jobs.quality_evidence')" />
    <template v-if="qualityEvidence">
      <el-alert
        class="quality-evidence-alert"
        :type="qualityEvidence.tagType === 'danger' ? 'error' : qualityEvidence.tagType"
        :closable="false"
        show-icon
        :title="qualityEvidence.title"
      >
        <p>{{ qualityEvidence.description }}</p>
      </el-alert>
      <div v-if="qualityEvidence.evidenceItems.length" class="quality-evidence-grid">
        <div v-for="item in qualityEvidence.evidenceItems" :key="item.label" class="quality-evidence-item">
          <span>{{ item.label }}</span>
          <strong :class="{ mono: item.mono }">{{ item.value }}</strong>
        </div>
      </div>
      <div v-if="qualityEvidence.flags.length" class="quality-flag-list">
        <div v-for="flag in qualityEvidence.flags" :key="flag" class="quality-flag-item">
          <el-tag size="small" type="warning" effect="plain">{{ documentJobQualityFlagText(flag) }}</el-tag>
        </div>
      </div>
      <el-empty v-else class="compact-empty" description="暂无自动质量标记" />
    </template>
  </el-card>
  <el-card class="page-section card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">回调消息</h2>
        <p class="section-subtitle">MinerU 回调（callback）的入库、重放和失败摘要；不展示回调原始 payload。</p>
      </div>
      <el-button :icon="Refresh" :loading="callbackSummaryLoading" @click="loadCallbackSummary()">刷新回调</el-button>
    </div>
    <ApiErrorAlert
      :error="callbackSummaryError"
      :diagnostic-context="jobErrorDiagnosticContext('document_jobs.callback_summary')"
    />
    <el-descriptions :column="2" border>
      <el-descriptions-item v-for="item in callbackSummaryItems" :key="item.label" :label="item.label">
        <span class="mono">{{ item.value }}</span>
      </el-descriptions-item>
    </el-descriptions>
    <el-table
      v-if="callbackSummary?.recent_problem_messages.length"
      class="page-section"
      :data="callbackSummary.recent_problem_messages"
      table-layout="fixed"
    >
      <el-table-column prop="message_id" label="消息 ID" min-width="180">
        <template #default="{ row }"><span class="mono">{{ row.message_id }}</span></template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110" />
      <el-table-column prop="attempts" label="尝试次数" width="100" />
      <el-table-column prop="error_code" label="错误码" min-width="180" />
      <el-table-column prop="error_message" label="错误信息" min-width="280" show-overflow-tooltip />
      <el-table-column label="更新时间" min-width="170">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
    </el-table>
  </el-card>
  <el-card v-if="degradedPages.length" class="page-section card-flat" shadow="never">
    <el-alert type="warning" :closable="false" show-icon
      title="部分页面无法转换，已按原 PDF 页面图像保留（不可编辑），结果仅可内部下载，不能批准或发布。">
      <p v-if="sourcePageLine">{{ sourcePageLine }}</p>
      <p v-for="line in degradedPageLines(degradedPages)" :key="line">{{ line }}</p>
    </el-alert>
  </el-card>
  <el-card v-else-if="sourcePageLine" class="page-section card-flat" shadow="never">
    <el-alert type="success" :closable="false" show-icon :title="sourcePageLine" />
  </el-card>
  <el-card v-if="job.status === 'failed'" class="page-section card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">失败信息</h2>
        <p class="section-subtitle">按后端返回展示，不在前端推断可重试原因。</p>
      </div>
    </div>
    <el-alert class="failure-summary" type="error" :closable="false" show-icon :title="failureSummary">
      <p>{{ failureHelpText }}</p>
      <p v-for="line in jobFailureSummaryLines(job, job.failure_diagnostic, true)" :key="line">{{ line }}</p>
      <p v-if="latestErrorEvent">
        最近错误事件：
        {{ latestErrorEvent.message }}
        <span v-if="latestErrorEvent.trace_id" class="mono">trace_id={{ latestErrorEvent.trace_id }}</span>
      </p>
    </el-alert>
    <el-descriptions :column="1" border>
      <el-descriptions-item label="失败阶段">{{ job.failed_stage ? jobStageText[job.failed_stage] || job.failed_stage : "-" }}</el-descriptions-item>
      <el-descriptions-item label="错误码">{{ job.error_code || "-" }}</el-descriptions-item>
      <el-descriptions-item label="错误信息">{{ job.error_message || "-" }}</el-descriptions-item>
    </el-descriptions>
  </el-card>
  <el-empty v-else class="page-section" description="当前任务没有失败诊断；请查看上方诊断摘要、质量证据和事件预览" />
</template>

<script setup lang="ts">
import { Refresh } from "@element-plus/icons-vue";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import EvidenceSurfaceSection from "@/components/EvidenceSurfaceSection.vue";
import { formatDateTime, documentJobQualityFlagText, jobStageText } from "@/utils/format";
import { jobFailureSummaryLines } from "@/utils/failureDiagnostic";
import { degradedPageLines } from "@/utils/degradedPages";
import {
  translationBatchAiCallLogSummaryText,
  translationBatchAttemptText,
  translationBatchErrorSummaryText,
  translationBatchFileIdsText,
  translationBatchFlagTexts,
  translationBatchPageRangeText,
  translationBatchScaleText,
  translationBatchStatusTagType,
  translationBatchStatusText,
} from "@/utils/translationBatches";
import { usesTranslationResources, translationBatchTableRowClassName } from "./jobDetailFormat";
import type { UnwrapRef } from "vue";
import type { JobDetailData } from "./useJobDetailData";
import type { JobDetailBatches } from "./useJobDetailBatches";
import type { JobDetailDiagnostics } from "./useJobDetailDiagnostics";
import type { DocumentJobResponse } from "@/api/types";
const {
  job,
  events,
  callbackSummary,
  translationBatches,
  loading,
  eventsLoading,
  filesLoading,
  callbackSummaryLoading,
  translationBatchesLoading,
  eventsError,
  filesError,
  callbackSummaryError,
  translationBatchesError,
  loadEvents,
  loadFiles,
  loadCallbackSummary,
  loadTranslationBatches,
  loadAll,
  jobErrorDiagnosticContext,
  openEventsTab,
  translationBatchSummaryItems,
  translationBatchConclusion,
  latestErrorEvent,
  degradedPages,
  sourcePageLine,
  failureSummary,
  failureHelpText,
  callbackSummaryItems,
  qualityEvidence,
  diagnosticRecommendation,
  diagnosticSummaryFacts,
  diagnosticEvidenceItems,
  diagnosticPreviewEvents,
  diagnosticRecoveryItems,
} = defineProps<{
  job: DocumentJobResponse;
  events: UnwrapRef<JobDetailData["events"]>;
  callbackSummary: UnwrapRef<JobDetailData["callbackSummary"]>;
  translationBatches: UnwrapRef<JobDetailData["translationBatches"]>;
  loading: UnwrapRef<JobDetailData["loading"]>;
  eventsLoading: UnwrapRef<JobDetailData["eventsLoading"]>;
  filesLoading: UnwrapRef<JobDetailData["filesLoading"]>;
  callbackSummaryLoading: UnwrapRef<JobDetailData["callbackSummaryLoading"]>;
  translationBatchesLoading: UnwrapRef<JobDetailData["translationBatchesLoading"]>;
  eventsError: UnwrapRef<JobDetailData["eventsError"]>;
  filesError: UnwrapRef<JobDetailData["filesError"]>;
  callbackSummaryError: UnwrapRef<JobDetailData["callbackSummaryError"]>;
  translationBatchesError: UnwrapRef<JobDetailData["translationBatchesError"]>;
  loadEvents: UnwrapRef<JobDetailData["loadEvents"]>;
  loadFiles: UnwrapRef<JobDetailData["loadFiles"]>;
  loadCallbackSummary: UnwrapRef<JobDetailData["loadCallbackSummary"]>;
  loadTranslationBatches: UnwrapRef<JobDetailData["loadTranslationBatches"]>;
  loadAll: UnwrapRef<JobDetailData["loadAll"]>;
  jobErrorDiagnosticContext: UnwrapRef<JobDetailData["jobErrorDiagnosticContext"]>;
  openEventsTab: UnwrapRef<JobDetailData["openEventsTab"]>;
  translationBatchSummaryItems: UnwrapRef<JobDetailBatches["translationBatchSummaryItems"]>;
  translationBatchConclusion: UnwrapRef<JobDetailBatches["translationBatchConclusion"]>;
  latestErrorEvent: UnwrapRef<JobDetailDiagnostics["latestErrorEvent"]>;
  degradedPages: UnwrapRef<JobDetailDiagnostics["degradedPages"]>;
  sourcePageLine: UnwrapRef<JobDetailDiagnostics["sourcePageLine"]>;
  failureSummary: UnwrapRef<JobDetailDiagnostics["failureSummary"]>;
  failureHelpText: UnwrapRef<JobDetailDiagnostics["failureHelpText"]>;
  callbackSummaryItems: UnwrapRef<JobDetailDiagnostics["callbackSummaryItems"]>;
  qualityEvidence: UnwrapRef<JobDetailDiagnostics["qualityEvidence"]>;
  diagnosticRecommendation: UnwrapRef<JobDetailDiagnostics["diagnosticRecommendation"]>;
  diagnosticSummaryFacts: UnwrapRef<JobDetailDiagnostics["diagnosticSummaryFacts"]>;
  diagnosticEvidenceItems: UnwrapRef<JobDetailDiagnostics["diagnosticEvidenceItems"]>;
  diagnosticPreviewEvents: UnwrapRef<JobDetailDiagnostics["diagnosticPreviewEvents"]>;
  diagnosticRecoveryItems: UnwrapRef<JobDetailDiagnostics["diagnosticRecoveryItems"]>;
}>();
</script>

<style scoped lang="scss">
.diagnostic-overview-card {
  display: grid;
  gap: var(--app-space-3);
}

.diagnostic-overview-card :deep(.el-card__body) {
  display: grid;
  gap: var(--app-space-3);
}

.diagnostic-recommendation p,
.diagnostic-recommendation strong {
  display: block;
  margin: 4px 0 0;
}

.diagnostic-summary-grid,
.diagnostic-evidence-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.diagnostic-summary-item,
.diagnostic-evidence-card {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-muted);
}

.diagnostic-summary-item span,
.diagnostic-evidence-card span,
.diagnostic-evidence-card small,
.diagnostic-loading {
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.diagnostic-summary-item strong,
.diagnostic-evidence-card strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diagnostic-evidence-card small {
  display: block;
  margin-top: 6px;
  overflow-wrap: anywhere;
}

.translation-batch-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.translation-batch-summary-item {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-muted);
}

.translation-batch-summary-item span {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.translation-batch-summary-item strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.translation-batch-table {
  width: 100%;
}

.translation-batch-status {
  display: grid;
  gap: 6px;
  align-items: start;
}

.translation-batch-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.translation-batch-id,
.translation-batch-meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.translation-batch-meta {
  margin-top: 3px;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.translation-batch-table :deep(.is-translation-batch-failed > td) {
  background: var(--el-color-danger-light-9);
}

.translation-batch-table :deep(.is-translation-batch-warning > td) {
  background: var(--el-color-warning-light-9);
}

.translation-batch-table :deep(.is-translation-batch-active > td) {
  background: var(--el-color-primary-light-9);
}

.translation-batch-table :deep(.is-translation-batch-stopped > td) {
  background: var(--el-color-warning-light-9);
}

.translation-batch-table :deep(.is-translation-batch-retrying > td) {
  background: var(--el-color-warning-light-9);
}

.translation-batch-table :deep(.is-translation-batch-superseded > td) {
  background: var(--app-color-surface-muted);
}

.translation-batch-conclusion {
  margin-bottom: var(--app-space-2);
}

.translation-batch-conclusion p {
  margin: 0;
}

.translation-batch-conclusion-reason {
  margin-top: 6px !important;
  overflow-wrap: anywhere;
}

.diagnostic-section-block {
  display: grid;
  gap: var(--app-space-2);
}

.diagnostic-event-preview {
  display: grid;
  gap: 8px;
  padding: 0;
  margin: 0;
  list-style: none;
}

.diagnostic-event-preview li {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-color-border-soft);
  border-left: 3px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface);
}

.diagnostic-event-preview li.is-error {
  border-left-color: var(--el-color-danger);
}

.diagnostic-event-preview li.is-warning {
  border-left-color: var(--el-color-warning);
}

.diagnostic-event-preview span,
.diagnostic-event-preview small {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.diagnostic-event-preview strong,
.diagnostic-event-preview p {
  margin: 4px 0 0;
  overflow-wrap: anywhere;
}

.diagnostic-recovery-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.failure-summary {
  margin-bottom: 14px;
}

.failure-summary p {
  margin: 4px 0 0;
}

.quality-evidence-alert {
  margin-bottom: 14px;
}

.quality-evidence-alert p {
  margin: 4px 0 0;
}

.quality-evidence-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.quality-evidence-item {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-surface-muted);
}

.quality-evidence-item span {
  display: block;
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.quality-evidence-item strong {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  color: var(--app-color-text);
  font-size: 13px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quality-flag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.quality-flag-item {
  min-width: 0;
}

.quality-flag-item :deep(.el-tag__content) {
  overflow: hidden;
  max-width: min(100%, 420px);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-empty {
  padding: 16px 0 4px;
}

@media (max-width: 760px) {

  .diagnostic-summary-grid,
.diagnostic-evidence-grid,
.translation-batch-summary-grid,
.quality-evidence-grid {
    grid-template-columns: 1fr;
  }
}
</style>
