<!-- File: frontend/src/pages/TranslationResultQaPage.vue -->
<!-- Purpose: 展示任务级翻译 QA 证据、复核状态和段落 trace 关联视图。 -->
<template>
  <main class="translation-result-qa-page app-page" aria-labelledby="translation-qa-title">
    <section class="qa-page-header section-header app-page-header app-page-shell">
      <div>
        <p class="page-kicker">Translation QA</p>
        <h1 id="translation-qa-title" class="page-title">翻译 QA</h1>
        <p class="page-description mono">{{ jobId }}</p>
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

    <ApiErrorAlert class="app-page-shell" :error="error" />
    <el-skeleton v-if="loading && !job && !qa" class="app-page-shell" :rows="8" animated />

    <template v-else-if="job && qa">
      <section class="qa-task-grid page-section app-page-shell">
        <el-card class="card-flat qa-panel app-panel-card" shadow="never">
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
      </section>

      <section class="qa-detail-review-shell page-section app-page-shell">
        <TranslationQaReviewPanel
          :job="job"
          :qa="qa"
          :form="form"
          :loading="loading"
          :saving="saving"
          :error="error"
          :queue-cleared="false"
          :active-segment-index="activeSegmentIndex"
          :show-close="false"
          :show-open-detail="false"
          :show-submit-next="false"
          :show-shortcut-hints="false"
          submit-label="保存复核"
          @update:form="updateForm"
          @segment-index-change="setActiveSegmentIndex"
          @submit="saveQa"
          @refresh="loadAll()"
        />
      </section>

      <section class="qa-grid page-section app-page-shell">
        <el-card class="card-flat qa-panel app-panel-card app-table-card" shadow="never">
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

        <el-card class="card-flat qa-panel app-panel-card app-table-card" shadow="never">
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
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import TranslationQaReviewPanel from "@/components/TranslationQaReviewPanel.vue";
import { formatDateTime, jobModeText } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import type { TranslationQaReviewDraft } from "@/utils/translationQa";

const route = useRoute();
const router = useRouter();
const jobId = computed(() => String(route.params.jobId || ""));
const job = ref<DocumentJobResponse | null>(null);
const qa = ref<DocumentJobTranslationQaResponse | null>(null);
const loading = ref(false);
const saving = ref(false);
const error = ref<ApiClientError | null>(null);
const activeSegmentIndex = ref(0);

const form = reactive<TranslationQaReviewDraft>({
  status: "unreviewed",
  issue_type: null,
  note: "",
});

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
const segmentIds = computed(() => new Set((qa.value?.segments || []).map((segment) => segment.id)));
const unmatchedTermTraces = computed(() =>
  (qa.value?.term_traces || []).filter((trace) => !trace.segment_id || !segmentIds.value.has(trace.segment_id)),
);
const fromTranslationQaQueue = computed(() => route.query.from === "translation-qa");
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
  activeSegmentIndex.value = 0;
}

function updateForm(nextForm: TranslationQaReviewDraft): void {
  form.status = nextForm.status;
  form.issue_type = nextForm.issue_type;
  form.note = nextForm.note;
}

function setActiveSegmentIndex(index: number): void {
  const segmentCount = qa.value?.segments.length || 0;
  if (!segmentCount) {
    activeSegmentIndex.value = 0;
    return;
  }
  activeSegmentIndex.value = Math.min(Math.max(index, 0), segmentCount - 1);
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

function providerLabel(provider: Record<string, unknown>): string {
  const backend = readString(provider.backend) || "-";
  const model = readString(provider.model);
  return model ? `${backend} / ${model}` : backend;
}

function resetPageStateForRouteChange(): void {
  job.value = null;
  qa.value = null;
  error.value = null;
  saving.value = false;
  activeSegmentIndex.value = 0;
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
  gap: var(--app-space-4);
}

.qa-page-header {
  align-items: flex-start;
  border-color: var(--app-color-primary-border);
}

.qa-page-header .toolbar {
  justify-content: flex-end;
}

.qa-grid,
.qa-task-grid {
  display: grid;
  gap: var(--app-space-4);
}

.qa-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.qa-task-grid {
  grid-template-columns: minmax(0, 1fr);
}

.qa-detail-review-shell {
  min-height: 720px;
}

.qa-detail-review-shell :deep(.translation-qa-review-panel) {
  min-height: 720px;
  border: 1px solid var(--app-color-border);
  border-radius: var(--app-radius-md);
  overflow: hidden;
}

.qa-panel {
  min-width: 0;
  border-color: var(--app-color-primary-border);
}

.trace-note {
  margin: 0 0 var(--app-space-2);
  color: var(--app-color-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 980px) {
  .qa-grid {
    grid-template-columns: 1fr;
  }

  .qa-page-header .toolbar {
    justify-content: flex-start;
  }
}
</style>
