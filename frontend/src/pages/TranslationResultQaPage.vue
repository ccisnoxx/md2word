<!-- File: frontend/src/pages/TranslationResultQaPage.vue -->
<!-- Purpose: 展示任务级翻译 QA 证据、复核状态和段落 trace 关联视图。 -->
<template>
  <main class="translation-result-qa-page" aria-labelledby="translation-qa-title">
    <section class="section-header">
      <div>
        <h1 id="translation-qa-title" class="section-title">翻译 QA</h1>
        <p class="section-subtitle mono">{{ jobId }}</p>
      </div>
      <div class="toolbar">
        <el-button v-if="fromTranslationQaQueue" @click="openQaQueue">返回 QA 队列</el-button>
        <el-button @click="openJobDetail">任务详情</el-button>
        <el-button :disabled="!job || job.mode !== 'en2zh_pdf_to_word'" @click="openTranslationTermProposal">
          提交翻译术语建议
        </el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll()">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />
    <el-skeleton v-if="loading && !job && !qa" :rows="8" animated />

    <template v-else-if="job && qa">
      <el-alert
        v-if="!qa.available"
        class="page-section"
        type="warning"
        :closable="false"
        show-icon
        :title="availabilityReasonText(qa.availability_reason)"
      />
      <el-alert
        v-else-if="!qa.summary.source_comparison_available"
        class="page-section"
        type="info"
        :closable="false"
        show-icon
        :title="sourceComparisonReasonText(qa.summary.source_comparison_reason)"
      />

      <section class="qa-grid page-section">
        <el-card class="card-flat qa-panel" shadow="never">
          <div class="section-header">
            <div>
              <h2 class="section-title">任务</h2>
              <p class="section-subtitle">{{ jobModeText[job.mode] || job.mode }}</p>
            </div>
            <JobStatusBadge :status="job.status" />
          </div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="创建时间">{{ formatDateTime(job.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatDateTime(job.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="Template">{{ boundTemplateLabel }}</el-descriptions-item>
            <el-descriptions-item label="Term Rule Set">{{ boundTermRuleSetLabel }}</el-descriptions-item>
            <el-descriptions-item label="Translation Term Set">{{ boundTranslationTermSetLabel }}</el-descriptions-item>
            <el-descriptions-item label="Translation Profile">{{ boundTranslationProfileLabel }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card class="card-flat qa-panel" shadow="never">
          <div class="section-header">
            <div>
              <h2 class="section-title">复核结论</h2>
              <p class="section-subtitle">任务级状态，不修改译文或术语库。</p>
            </div>
            <el-tag :type="qaStatusTagType(form.status)" effect="plain">{{ qaStatusText[form.status] }}</el-tag>
          </div>
          <el-form label-width="96px">
            <el-form-item label="状态">
              <el-select v-model="form.status" :disabled="!qaEditable">
                <el-option v-for="option in qaStatusOptions" :key="option" :label="qaStatusText[option]" :value="option" />
              </el-select>
            </el-form-item>
            <el-form-item label="问题归因">
              <el-select v-model="form.issue_type" clearable placeholder="可选" :disabled="!qaEditable">
                <el-option
                  v-for="option in qaIssueTypeOptions"
                  :key="option"
                  :label="qaIssueTypeText[option]"
                  :value="option"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.note" type="textarea" :rows="3" maxlength="1000" show-word-limit :disabled="!qaEditable" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" :disabled="!qaEditable" @click="saveQa">保存复核</el-button>
            </el-form-item>
          </el-form>
          <p class="review-meta">
            最近复核：{{ qa.qa.reviewed_by || "-" }} · {{ formatDateTime(qa.qa.reviewed_at) }}
          </p>
        </el-card>
      </section>

      <section class="metric-grid page-section" aria-label="QA 证据摘要">
        <article v-for="metric in metrics" :key="metric.label" class="metric-card">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.helper }}</small>
        </article>
      </section>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">证据文件</h2>
            <p class="section-subtitle">只展示现有任务产物，不生成新文件。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="DocumentIR">
            <span class="mono">{{ qa.artifacts.document_ir_file_id || "-" }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="AI 调用日志">
            <span class="mono">{{ joinIds(qa.artifacts.ai_call_log_file_ids) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="AI debug 归档">
            <span class="mono">{{ joinIds(qa.artifacts.ai_debug_archive_file_ids) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="Quality flags">
            <div class="flag-list">
              <el-tag v-for="flag in qa.summary.quality_flags" :key="flag" size="small" effect="plain">{{ flag }}</el-tag>
              <span v-if="!qa.summary.quality_flags.length">-</span>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">片段对照</h2>
            <p class="section-subtitle">
              返回 {{ qa.summary.returned_segment_count }} / {{ qa.summary.final_segment_count }} 个最终文本片段。
            </p>
          </div>
        </div>
        <el-table :data="segmentTraceRows" empty-text="暂无片段证据">
          <el-table-column type="expand" width="48">
            <template #default="{ row }">
              <div class="segment-trace-detail">
                <section class="trace-card">
                  <div class="trace-card-header">
                    <h3>该片段术语命中</h3>
                    <el-tag size="small" effect="plain">{{ termTraceCountText(row) }}</el-tag>
                  </div>
                  <el-table :data="row.termTraces" size="small" empty-text="该片段暂无术语命中">
                    <el-table-column label="Source" min-width="140" prop="source_term" />
                    <el-table-column label="Target" min-width="160" prop="target_term" />
                    <el-table-column label="Version" min-width="180">
                      <template #default="{ row: trace }">
                        <span class="mono">{{ versionLabel(trace.translation_term_set_id, trace.translation_term_version) }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="Range" width="110">
                      <template #default="{ row: trace }">{{ termTraceRangeText(trace) }}</template>
                    </el-table-column>
                    <el-table-column label="Provider trace" min-width="160">
                      <template #default="{ row: trace }">
                        <span class="mono">{{ trace.provider_trace_id || "-" }}</span>
                      </template>
                    </el-table-column>
                  </el-table>
                </section>

                <section class="trace-card">
                  <div class="trace-card-header">
                    <h3>AI call evidence</h3>
                    <el-tag size="small" type="info" effect="plain">call-level only</el-tag>
                  </div>
                  <p class="trace-note">
                    当前证据没有稳定的 segment-to-call 关联键；这里展示任务级 AI 调用 metadata，不推断单片段归属。
                  </p>
                  <el-table :data="qa.ai_calls" size="small" empty-text="暂无 AI 调用日志">
                    <el-table-column label="Call" min-width="150">
                      <template #default="{ row: call }">
                        <span class="mono">{{ call.call_id || call.file_id }}</span>
                      </template>
                    </el-table-column>
                    <el-table-column label="状态" width="96" prop="status" />
                    <el-table-column label="Provider" min-width="170">
                      <template #default="{ row: call }">{{ providerLabel(call.provider) }}</template>
                    </el-table-column>
                    <el-table-column label="Items" width="88" prop="item_count" />
                    <el-table-column label="Chars" width="88" prop="char_count" />
                  </el-table>
                </section>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="片段" min-width="180">
            <template #default="{ row }">
              <div class="mono">{{ row.id }}</div>
              <div class="muted">{{ row.block_type }} · page {{ pageLabel(row.page_index) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="证据状态" min-width="170">
            <template #default="{ row }">
              <div class="evidence-tags">
                <el-tag size="small" :type="sourceEvidenceTagType(row)" effect="plain">
                  {{ sourceEvidenceLabel(row) }}
                </el-tag>
                <el-tag size="small" :type="row.termTraceCount ? 'success' : 'info'" effect="plain">
                  {{ termTraceCountText(row) }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="源文" min-width="260">
            <template #default="{ row }">
              <span v-if="row.source_text">{{ row.source_text }}</span>
              <span v-else class="muted">{{ sourceComparisonReasonText(qa.summary.source_comparison_reason) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="AI 译文" min-width="260">
            <template #default="{ row }">
              <span v-if="row.ai_translation_text">{{ row.ai_translation_text }}</span>
              <span v-else class="muted">{{ sourceComparisonReasonText(qa.summary.source_comparison_reason) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最终文本" min-width="260" prop="final_text" />
        </el-table>
      </el-card>

      <section class="qa-grid page-section">
        <el-card class="card-flat qa-panel" shadow="never">
          <div class="section-header">
            <div>
              <h2 class="section-title">术语命中</h2>
              <p class="section-subtitle">来自 AI 调用日志的脱敏 trace。</p>
            </div>
          </div>
          <el-table :data="qa.term_traces" empty-text="暂无术语命中">
            <el-table-column label="Segment" min-width="150" prop="segment_id" />
            <el-table-column label="Source" min-width="130" prop="source_term" />
            <el-table-column label="Target" min-width="150" prop="target_term" />
            <el-table-column label="Version" min-width="170">
              <template #default="{ row }">
                <span class="mono">{{ versionLabel(row.translation_term_set_id, row.translation_term_version) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <p v-if="unmatchedTermTraces.length" class="trace-note">
            另有 {{ unmatchedTermTraces.length }} 条术语 trace 没有 segment_id，已保留在全局列表中。
          </p>
        </el-card>

        <el-card class="card-flat qa-panel" shadow="never">
          <div class="section-header">
            <div>
              <h2 class="section-title">AI 调用摘要</h2>
              <p class="section-subtitle">metadata-only，不含完整 prompt 或 response。</p>
            </div>
          </div>
          <el-table :data="qa.ai_calls" empty-text="暂无 AI 调用日志">
            <el-table-column label="状态" width="96" prop="status" />
            <el-table-column label="Provider" min-width="170">
              <template #default="{ row }">{{ providerLabel(row.provider) }}</template>
            </el-table-column>
            <el-table-column label="Items" width="88" prop="item_count" />
            <el-table-column label="Chars" width="88" prop="char_count" />
            <el-table-column label="耗时" width="96">
              <template #default="{ row }">{{ row.duration_ms ?? "-" }} ms</template>
            </el-table-column>
          </el-table>
        </el-card>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import type {
  DocumentJobResourceSnapshot,
  DocumentJobResponse,
  DocumentJobTranslationQaResponse,
  DocumentJobTranslationQaSegmentResponse,
  DocumentJobTranslationQaTermTraceResponse,
  TranslationQaIssueType,
  TranslationQaStatus,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import { formatDateTime, jobModeText } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const route = useRoute();
const router = useRouter();
const jobId = computed(() => String(route.params.jobId || ""));
const job = ref<DocumentJobResponse | null>(null);
const qa = ref<DocumentJobTranslationQaResponse | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref<ApiClientError | null>(null);

const qaStatusOptions: TranslationQaStatus[] = ["unreviewed", "approved", "needs_fix", "blocked"];
const qaIssueTypeOptions: TranslationQaIssueType[] = [
  "translation",
  "terminology",
  "layout",
  "source_quality",
  "artifact_missing",
  "other",
];

const qaStatusText: Record<TranslationQaStatus, string> = {
  unreviewed: "未复核",
  approved: "通过",
  needs_fix: "需修正",
  blocked: "阻塞/无法判断",
};

const qaIssueTypeText: Record<TranslationQaIssueType, string> = {
  translation: "翻译问题",
  terminology: "术语问题",
  layout: "版式问题",
  source_quality: "源文件质量",
  artifact_missing: "证据缺失",
  other: "其他",
};

const form = reactive({
  status: "unreviewed" as TranslationQaStatus,
  issue_type: null as TranslationQaIssueType | null,
  note: "",
});

type SegmentTraceRow = DocumentJobTranslationQaSegmentResponse & {
  termTraces: DocumentJobTranslationQaTermTraceResponse[];
  termTraceCount: number;
};

const resourceSnapshot = computed(() => readResourceSnapshot(job.value?.request_snapshot.resources));
const boundTemplateLabel = computed(() => {
  const bound = resourceSnapshot.value?.template;
  return bound ? `${bound.resource_id}@${bound.version}` : job.value?.template_version_id || "-";
});
const boundTermRuleSetLabel = computed(() => {
  const bound = resourceSnapshot.value?.term_rule_set;
  return bound ? `${bound.resource_id}@${bound.version}` : snapshotTermAssetLabel("term_rule_set_id", "term_rule_set_version");
});
const boundTranslationTermSetLabel = computed(() => {
  const bound = resourceSnapshot.value?.translation_term_set;
  return bound ? `${bound.set_id}@${bound.version}` : snapshotTermAssetLabel("translation_term_set_id", "translation_term_version");
});
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
const boundTranslationProfileLabel = computed(() => {
  const bound = resourceSnapshot.value?.translation_profile;
  if (bound) {
    return `${bound.resource_id}@${bound.version}`;
  }
  const profile = readRecord(job.value?.request_snapshot.translation_profile);
  return versionLabel(readString(profile?.translation_profile_id), readString(profile?.translation_profile_version));
});
const metrics = computed(() => {
  if (!qa.value) {
    return [];
  }
  return [
    {
      label: "最终片段",
      value: qa.value.summary.final_segment_count,
      helper: `${qa.value.summary.returned_segment_count} shown`,
    },
    {
      label: "AI calls",
      value: qa.value.summary.ai_call_count,
      helper: statusCountText(qa.value.summary.ai_call_statuses),
    },
    {
      label: "术语命中",
      value: qa.value.summary.term_trace_count,
      helper: qa.value.summary.source_comparison_available ? "source comparison available" : "metadata trace",
    },
    {
      label: "Quality flags",
      value: qa.value.summary.quality_flags.length,
      helper: qa.value.summary.quality_flags[0] || "none",
    },
  ];
});
const termTracesBySegment = computed(() => {
  const grouped = new Map<string, DocumentJobTranslationQaTermTraceResponse[]>();
  for (const trace of qa.value?.term_traces || []) {
    if (!trace.segment_id) {
      continue;
    }
    const items = grouped.get(trace.segment_id) || [];
    items.push(trace);
    grouped.set(trace.segment_id, items);
  }
  return grouped;
});
const segmentIds = computed(() => new Set((qa.value?.segments || []).map((segment) => segment.id)));
const segmentTraceRows = computed<SegmentTraceRow[]>(() =>
  (qa.value?.segments || []).map((segment) => {
    const termTraces = termTracesBySegment.value.get(segment.id) || [];
    return {
      ...segment,
      termTraces,
      termTraceCount: termTraces.length,
    };
  }),
);
const unmatchedTermTraces = computed(() =>
  (qa.value?.term_traces || []).filter((trace) => !trace.segment_id || !segmentIds.value.has(trace.segment_id)),
);
const fromTranslationQaQueue = computed(() => route.query.from === "translation-qa");
const qaEditable = computed(() => Boolean(qa.value?.available && !saving.value));
const qaQueueReturnQuery = computed(() => {
  const query: Record<string, string> = {};
  for (const key of ["translation_qa_status", "status", "sort", "include_archived", "q", "page"]) {
    const value = route.query[key];
    if (typeof value === "string" && value.trim()) {
      query[key] = value;
    }
  }
  return query;
});

function readRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? value as Record<string, unknown> : null;
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readResourceSnapshot(value: unknown): DocumentJobResourceSnapshot | null {
  return readRecord(value) as DocumentJobResourceSnapshot | null;
}

function versionLabel(setId?: string | null, version?: string | null): string {
  const normalizedSetId = setId || "-";
  const normalizedVersion = version || "-";
  return normalizedSetId === "-" && normalizedVersion === "-" ? "-" : `${normalizedSetId}@${normalizedVersion}`;
}

function snapshotTermAssetLabel(setKey: string, versionKey: string): string {
  const assets = readRecord(job.value?.request_snapshot.term_assets);
  return versionLabel(readString(assets?.[setKey]), readString(assets?.[versionKey]));
}

function syncForm(nextQa: DocumentJobTranslationQaResponse): void {
  form.status = nextQa.qa.status;
  form.issue_type = nextQa.qa.issue_type;
  form.note = nextQa.qa.note || "";
}

function appendQueryValue(query: Record<string, string>, key: string, value?: string | null): void {
  if (value) {
    query[key] = value;
  }
}

function openQaQueue(): void {
  void router.push({ name: "translation-qa", query: qaQueueReturnQuery.value });
}

function openJobDetail(): void {
  void router.push({ name: "job-detail", params: { jobId: jobId.value } });
}

function openTranslationTermProposal(): void {
  if (!job.value || job.value.mode !== "en2zh_pdf_to_word") {
    return;
  }
  const query: Record<string, string> = {
    tab: "translation-new",
    source_job_id: job.value.id,
    source_file_id: job.value.source_file_id,
  };
  appendQueryValue(query, "observed_translation_term_set_id", observedTranslationTermSetId.value);
  appendQueryValue(query, "observed_translation_term_version", observedTranslationTermVersion.value);
  void router.push({ name: "term-proposals", query });
}

async function loadAll(targetJobId = jobId.value): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [jobResponse, qaResponse] = await Promise.all([
      documentJobsApi.get(targetJobId),
      documentJobsApi.getTranslationQa(targetJobId),
    ]);
    if (targetJobId === jobId.value) {
      job.value = jobResponse;
      qa.value = qaResponse;
      syncForm(qaResponse);
    }
  } catch (caught) {
    if (targetJobId === jobId.value) {
      error.value = normalizeApiError(caught);
    }
  } finally {
    if (targetJobId === jobId.value) {
      loading.value = false;
    }
  }
}

async function saveQa(): Promise<void> {
  if (!qa.value?.available) {
    ElMessage.warning("当前任务没有可复核的 QA 证据，已保持只读。");
    return;
  }
  saving.value = true;
  error.value = null;
  try {
    await documentJobsApi.updateTranslationQa(jobId.value, {
      status: form.status,
      issue_type: form.issue_type,
      note: form.note || null,
    });
    ElMessage.success("翻译 QA 复核已保存。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    saving.value = false;
  }
}

function qaStatusTagType(status: TranslationQaStatus): "success" | "warning" | "danger" | "info" {
  if (status === "approved") {
    return "success";
  }
  if (status === "needs_fix") {
    return "warning";
  }
  if (status === "blocked") {
    return "danger";
  }
  return "info";
}

function joinIds(ids: string[]): string {
  return ids.length ? ids.join(", ") : "-";
}

function pageLabel(value: number | null): string {
  return value === null ? "-" : String(value + 1);
}

function providerLabel(provider: Record<string, unknown>): string {
  const backend = readString(provider.backend) || "-";
  const model = readString(provider.model);
  return model ? `${backend} / ${model}` : backend;
}

function statusCountText(value: Record<string, number>): string {
  const entries = Object.entries(value);
  return entries.length ? entries.map(([status, count]) => `${status}: ${count}`).join(", ") : "-";
}

// 根据单个片段是否带源文/AI 译文，显示可追踪证据状态。
function sourceEvidenceLabel(row: SegmentTraceRow): string {
  if (row.source_available) {
    return "有源文对照";
  }
  return "无源文对照";
}

// 将片段源文对照状态映射成标签颜色，避免把 debug archive 缺失误报为错误。
function sourceEvidenceTagType(row: SegmentTraceRow): "success" | "info" {
  return row.source_available ? "success" : "info";
}

// 格式化单片段术语命中数量，用于表格和展开面板。
function termTraceCountText(row: SegmentTraceRow): string {
  return `${row.termTraceCount} 条术语命中`;
}

// 展示术语命中在文本中的原始 offset；缺失时保持明确占位。
function termTraceRangeText(trace: DocumentJobTranslationQaTermTraceResponse): string {
  if (trace.match_start === null || trace.match_end === null) {
    return "-";
  }
  return `${trace.match_start}-${trace.match_end}`;
}

function availabilityReasonText(reason: string | null): string {
  const labels: Record<string, string> = {
    unsupported_mode: "当前任务不是 en2zh_pdf_to_word，翻译 QA 不适用。",
    document_ir_missing: "任务缺少 DocumentIR 证据文件，无法展示最终文本片段。",
    document_ir_unreadable: "DocumentIR 证据文件不可读取。",
  };
  return labels[reason || ""] || "翻译 QA 证据不可用。";
}

function sourceComparisonReasonText(reason: string | null): string {
  const labels: Record<string, string> = {
    ai_debug_archive_missing: "未保存 AI debug 归档，源文/AI 译文对照不可用。",
    ai_debug_archive_expired: "AI debug 归档已过期，源文/AI 译文对照不可用。",
    ai_debug_archive_no_text: "AI debug 归档不含可展示文本，源文/AI 译文对照不可用。",
  };
  return labels[reason || ""] || "源文/AI 译文对照不可用。";
}

function resetPageStateForRouteChange(): void {
  job.value = null;
  qa.value = null;
  error.value = null;
  saving.value = false;
  form.status = "unreviewed";
  form.issue_type = null;
  form.note = "";
}

watch(jobId, async (nextJobId, previousJobId) => {
  if (!nextJobId || nextJobId === previousJobId) {
    return;
  }
  resetPageStateForRouteChange();
  await loadAll(nextJobId);
});

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.translation-result-qa-page {
  display: grid;
  gap: 16px;
}

.qa-grid,
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.qa-panel {
  min-width: 0;
}

.metric-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  min-height: 98px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #ffffff;
}

.metric-card span,
.metric-card small,
.review-meta {
  color: #667085;
  font-size: 13px;
}

.metric-card strong {
  display: block;
  margin: 6px 0;
  color: #111827;
  font-size: 24px;
  line-height: 1;
}

.flag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.evidence-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.segment-trace-detail {
  display: grid;
  gap: 14px;
  padding: 12px 8px;
}

.trace-card {
  min-width: 0;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #f8fafc;
}

.trace-card-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.trace-card-header h3 {
  margin: 0;
  color: #111827;
  font-size: 14px;
}

.trace-note {
  margin: 0 0 10px;
  color: #667085;
  font-size: 13px;
  line-height: 1.6;
}

.review-meta {
  margin: 0;
}

@media (max-width: 980px) {
  .qa-grid,
  .metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
