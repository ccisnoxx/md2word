<!-- frontend/src/pages/JobDetailPage.vue: Detail, events, polling, download, and retry view for one job. -->
<template>
  <div class="job-detail-page">
    <div class="section-header">
      <div>
        <h1 class="section-title">任务详情</h1>
        <p class="section-subtitle mono">{{ jobId }}</p>
      </div>
      <div class="toolbar">
        <el-button :icon="ArrowLeft" @click="$router.push('/jobs')">返回列表</el-button>
        <el-button v-if="job" :icon="EditPen" @click="openTermRuleProposalDialog">新增术语规则建议</el-button>
        <el-button v-if="job" :icon="EditPen" @click="openTranslationTermProposalDialog">
          新增翻译术语建议
        </el-button>
        <JobActions
          v-if="job"
          :job="job"
          :download-loading="downloadLoading"
          :retry-loading="retryLoading"
          :cancel-loading="cancelLoading"
          :archive-loading="archiveLoading"
          @refresh="loadAll"
          @download="handleDownload"
          @retry="handleRetry"
          @cancel="handleCancel"
          @archive="handleArchive"
        />
      </div>
    </div>

    <ApiErrorAlert :error="error" />

    <el-skeleton v-if="loading && !job" :rows="8" animated />

    <template v-else-if="job">
      <el-card class="page-section card-flat" shadow="never">
        <div class="detail-overview">
          <JobStatusBadge :status="job.status" />
          <JobProgress :status="job.status" :stage="job.stage" :progress="job.progress" />
        </div>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="模式">{{ jobModeText[job.mode] || job.mode }}</el-descriptions-item>
          <el-descriptions-item label="文档语言">{{ job.document_language }}</el-descriptions-item>
          <el-descriptions-item label="源 PDF">{{ sourceFilename }}</el-descriptions-item>
          <el-descriptions-item label="源文件 ID">{{ job.source_file_id }}</el-descriptions-item>
          <el-descriptions-item label="结果文件 ID">{{ job.result_file_id || "-" }}</el-descriptions-item>
          <el-descriptions-item label="Term Rule Set">{{ boundTermRuleSetLabel }}</el-descriptions-item>
          <el-descriptions-item label="Translation Term Set">{{ boundTranslationTermSetLabel }}</el-descriptions-item>
          <el-descriptions-item label="legacy term_version_id">{{ job.term_version_id || "-" }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(job.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDateTime(job.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="重试次数">{{ job.retry_count }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(job.completed_at) }}</el-descriptions-item>
          <el-descriptions-item label="取消时间">{{ formatDateTime(job.canceled_at) }}</el-descriptions-item>
          <el-descriptions-item label="归档时间">{{ formatDateTime(job.archived_at) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card v-if="job.status === 'failed'" class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">失败信息</h2>
            <p class="section-subtitle">按后端返回展示，不在前端推断可重试原因。</p>
          </div>
        </div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="失败阶段">{{ job.failed_stage || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误码">{{ job.error_code || "-" }}</el-descriptions-item>
          <el-descriptions-item label="错误信息">{{ job.error_message || "-" }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">请求快照</h2>
            <p class="section-subtitle">后端记录的非正文任务参数摘要。</p>
          </div>
        </div>
        <pre class="snapshot">{{ requestSnapshotPreview }}</pre>
      </el-card>

      <el-card class="page-section card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">事件流</h2>
            <p class="section-subtitle">阶段事件和排障 trace 信息。</p>
          </div>
          <el-button :icon="Refresh" :loading="eventsLoading" @click="loadEvents">刷新事件</el-button>
        </div>
        <JobEventTimeline :events="events" />
      </el-card>

      <el-dialog v-model="proposalDialogVisible" title="新增术语规则建议" width="720px">
        <el-form label-width="110px">
          <el-form-item label="来源任务">
            <el-input :model-value="job.id" disabled />
          </el-form-item>
          <el-form-item label="绑定规则版本">
            <el-input :model-value="boundTermRuleSetLabel" disabled />
          </el-form-item>
          <el-form-item label="原文术语" required>
            <el-input v-model="proposalForm.source_term" placeholder="例如 VIN" />
          </el-form-item>
          <el-form-item label="分类" required>
            <el-select v-model="proposalForm.category_id" filterable placeholder="选择分类">
              <el-option
                v-for="category in termRuleCategories"
                :key="category.id"
                :label="category.name"
                :value="category.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="展示分段" required>
            <TermSegmentEditor v-model="proposalForm.segments" />
          </el-form-item>
          <el-form-item label="原因说明" required>
            <el-input v-model="proposalForm.reason" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="页码">
            <el-input-number v-model="proposalForm.page_number" :min="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="前置上下文">
            <el-input v-model="proposalForm.context_before" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="后置上下文">
            <el-input v-model="proposalForm.context_after" type="textarea" :rows="2" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="proposalDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="proposalSubmitting" @click="submitTermRuleProposal">提交建议</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="translationProposalDialogVisible" title="新增翻译术语建议" width="680px">
        <el-form label-width="120px">
          <el-form-item label="来源任务">
            <el-input :model-value="job.id" disabled />
          </el-form-item>
          <el-form-item label="绑定术语版本">
            <el-input :model-value="boundTranslationTermSetLabel" disabled />
          </el-form-item>
          <el-form-item label="动作">
            <el-radio-group v-model="translationProposalForm.action">
              <el-radio-button label="add">新增</el-radio-button>
              <el-radio-button label="update">编辑</el-radio-button>
              <el-radio-button label="delete">删除</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="原文术语" required>
            <el-input v-model="translationProposalForm.source_term" placeholder="例如 FPGA" />
          </el-form-item>
          <el-form-item v-if="translationProposalForm.action !== 'delete'" label="目标译文" required>
            <el-input v-model="translationProposalForm.target_term" placeholder="例如 现场可编程门阵列" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="translationProposalForm.priority" :min="0" controls-position="right" />
          </el-form-item>
          <el-form-item label="领域">
            <el-input v-model="translationProposalForm.domain" placeholder="可选" />
          </el-form-item>
          <el-form-item label="分类">
            <el-input v-model="translationProposalForm.category" placeholder="可选" />
          </el-form-item>
          <el-form-item label="说明">
            <el-input v-model="translationProposalForm.note" type="textarea" :rows="3" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="translationProposalDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="translationProposalSubmitting" @click="submitTranslationTermProposal">
            提交建议
          </el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="retryDialogVisible" title="重试任务" width="640px">
        <el-form label-width="150px">
          <el-form-item label="任务 ID">
            <el-input :model-value="retryDialog.job?.id || ''" disabled />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="retryDialog.reason" type="textarea" :rows="2" />
          </el-form-item>
          <template v-if="isAdmin">
            <el-form-item label="使用最新术语资产">
              <el-switch v-model="retryDialog.use_latest_term_assets" />
            </el-form-item>
            <el-form-item label="Term Rule Set">
              <el-select
                v-model="retryDialog.term_rule_set_id"
                clearable
                filterable
                placeholder="默认规则集"
                @change="handleRetryTermRuleSetChange"
              >
                <el-option v-for="set in termRuleSets" :key="set.id" :label="set.id" :value="set.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="Term Rule Version">
              <el-select
                v-model="retryDialog.term_rule_set_version"
                clearable
                filterable
                :disabled="retryDialog.use_latest_term_assets"
                placeholder="默认版本或选择 published 历史版本"
              >
                <el-option
                  v-for="version in selectedRetryTermRuleVersions"
                  :key="version.version"
                  :label="`${version.version}${version.is_default ? '（默认）' : ''}`"
                  :value="version.version"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="Translation Term Set">
              <el-input
                v-model="retryDialog.translation_term_set_id"
                :disabled="retryDialog.use_latest_term_assets"
                placeholder="默认 translation-terms-en2zh"
              />
            </el-form-item>
            <el-form-item label="Translation Version">
              <el-input
                v-model="retryDialog.translation_term_version"
                :disabled="retryDialog.use_latest_term_assets"
                placeholder="例如 v1；为空使用默认"
              />
            </el-form-item>
          </template>
        </el-form>
        <template #footer>
          <el-button @click="retryDialogVisible = false">取消</el-button>
          <el-button type="warning" :loading="retryLoading" @click="submitRetryDialog">提交重试</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, EditPen, Refresh } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import type {
  DocumentJobResourceSnapshot,
  DocumentJobEventResponse,
  DocumentJobResponse,
  TermRuleCategoryListItemResponse,
  TermRuleSetDetailResponse,
  TermRuleSetListItemResponse,
  TermRuleSegmentWriteRequest,
  TranslationTermProposalAction,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { termProposalsApi, translationTermProposalsApi } from "@/api/termProposals";
import { termRulesApi } from "@/api/termRules";
import { termRuleSetsApi } from "@/api/termRuleSets";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobActions from "@/components/JobActions.vue";
import JobEventTimeline from "@/components/JobEventTimeline.vue";
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import TermSegmentEditor from "@/components/TermSegmentEditor.vue";
import { useAuthStore } from "@/stores/auth";
import { formatDateTime, getJobSourceFilename, isActiveJobStatus, jobModeText } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const jobId = computed(() => String(route.params.jobId || ""));
const job = ref<DocumentJobResponse | null>(null);
const events = ref<DocumentJobEventResponse[]>([]);
const loading = ref(false);
const eventsLoading = ref(false);
const downloadLoading = ref(false);
const retryLoading = ref(false);
const cancelLoading = ref(false);
const archiveLoading = ref(false);
const proposalDialogVisible = ref(false);
const proposalSubmitting = ref(false);
const translationProposalDialogVisible = ref(false);
const translationProposalSubmitting = ref(false);
const retryDialogVisible = ref(false);
const termRuleCategories = ref<TermRuleCategoryListItemResponse[]>([]);
const termRuleSets = ref<TermRuleSetListItemResponse[]>([]);
const termRuleSetDetails = ref<Record<string, TermRuleSetDetailResponse>>({});
const error = ref<ApiClientError | null>(null);
let pollTimer: number | undefined;

const proposalForm = reactive({
  source_term: "",
  category_id: "",
  segments: [
    { segment_text: "V", render_type: "plain" },
    { segment_text: "IN", render_type: "subscript" },
  ] as TermRuleSegmentWriteRequest[],
  reason: "",
  page_number: null as number | null,
  context_before: "",
  context_after: "",
});

const translationProposalForm = reactive({
  action: "add" as TranslationTermProposalAction,
  source_term: "",
  target_term: "",
  priority: 0,
  domain: "",
  category: "",
  note: "",
});

const retryDialog = reactive({
  job: null as DocumentJobResponse | null,
  reason: "frontend retry",
  use_latest_term_assets: false,
  term_rule_set_id: "",
  term_rule_set_version: "",
  translation_term_set_id: "",
  translation_term_version: "",
});

const requestSnapshotPreview = computed(() => JSON.stringify(job.value?.request_snapshot || {}, null, 2));
const sourceFilename = computed(() => (job.value ? getJobSourceFilename(job.value) : "-"));
const isAdmin = computed(() => auth.user?.role === "admin");
const resourceSnapshot = computed(() => readResourceSnapshot(job.value?.request_snapshot.resources));
const boundTermRuleSet = computed(() => resourceSnapshot.value?.term_rule_set || null);
const boundTranslationTermSet = computed(() => resourceSnapshot.value?.translation_term_set || null);
const boundTermRuleSetLabel = computed(() => {
  const bound = boundTermRuleSet.value;
  if (!bound) {
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    return versionLabel(readString(assets?.term_rule_set_id), readString(assets?.term_rule_set_version));
  }
  return `${bound.resource_id}@${bound.version}`;
});
const boundTranslationTermSetLabel = computed(() => {
  const bound = boundTranslationTermSet.value;
  if (!bound) {
    const assets = readRecord(job.value?.request_snapshot.term_assets);
    const setId = readString(assets?.translation_term_set_id);
    const version = readString(assets?.translation_term_version) || job.value?.term_version_id || null;
    return versionLabel(setId, version);
  }
  return `${bound.set_id}@${bound.version}`;
});
const selectedRetryTermRuleVersions = computed(() => {
  const selected = retryDialog.term_rule_set_id || termRuleSets.value[0]?.id || "";
  return termRuleSetDetails.value[selected]?.versions || [];
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

async function loadJob(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    job.value = await documentJobsApi.get(jobId.value);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

async function loadEvents(): Promise<void> {
  eventsLoading.value = true;
  try {
    const response = await documentJobsApi.listEvents(jobId.value);
    events.value = response.items;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    eventsLoading.value = false;
  }
}

async function loadAll(): Promise<void> {
  await loadJob();
  if (job.value) {
    await loadEvents();
  }
}

async function loadTermRuleCategories(): Promise<void> {
  const response = await termRulesApi.listCategories();
  termRuleCategories.value = response.items.filter((category) => category.enabled);
}

async function loadTermRuleSets(): Promise<void> {
  const response = await termRuleSetsApi.list();
  termRuleSets.value = response.items;
  await Promise.all(response.items.map((item) => loadTermRuleSetDetail(item.id)));
}

async function loadTermRuleSetDetail(setId: string): Promise<void> {
  if (!setId || termRuleSetDetails.value[setId]) {
    return;
  }
  termRuleSetDetails.value[setId] = await termRuleSetsApi.get(setId);
}

async function openTermRuleProposalDialog(): Promise<void> {
  if (!job.value) {
    return;
  }
  resetProposalForm();
  proposalDialogVisible.value = true;
  error.value = null;
  try {
    if (!termRuleCategories.value.length) {
      await loadTermRuleCategories();
    }
    if (!proposalForm.category_id && termRuleCategories.value.length) {
      proposalForm.category_id = termRuleCategories.value[0].id;
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function openRetryDialog(target: DocumentJobResponse): Promise<void> {
  retryDialog.job = target;
  retryDialog.reason = "frontend retry";
  retryDialog.use_latest_term_assets = false;
  retryDialog.term_rule_set_id = boundTermRuleSet.value?.resource_id || "";
  retryDialog.term_rule_set_version = boundTermRuleSet.value?.version || "";
  retryDialog.translation_term_set_id = boundTranslationTermSet.value?.set_id || "";
  retryDialog.translation_term_version = boundTranslationTermSet.value?.version || "";
  retryDialogVisible.value = true;
  if (isAdmin.value && !termRuleSets.value.length) {
    try {
      await loadTermRuleSets();
      retryDialog.term_rule_set_id ||= termRuleSets.value[0]?.id || "";
    } catch (caught) {
      error.value = normalizeApiError(caught);
    }
  }
}

async function handleRetryTermRuleSetChange(): Promise<void> {
  retryDialog.term_rule_set_version = "";
  try {
    await loadTermRuleSetDetail(retryDialog.term_rule_set_id);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

function resetProposalForm(): void {
  proposalForm.source_term = "";
  proposalForm.category_id = termRuleCategories.value[0]?.id || "";
  proposalForm.segments = [
    { segment_text: "V", render_type: "plain" },
    { segment_text: "IN", render_type: "subscript" },
  ];
  proposalForm.reason = "";
  proposalForm.page_number = null;
  proposalForm.context_before = job.value ? `source=${sourceFilename.value}; mode=${job.value.mode}` : "";
  proposalForm.context_after = "";
}

function validateProposalForm(): boolean {
  if (!proposalForm.source_term.trim()) {
    ElMessage.warning("请填写原文术语。");
    return false;
  }
  if (!proposalForm.category_id) {
    ElMessage.warning("请选择分类。");
    return false;
  }
  if (!proposalForm.reason.trim()) {
    ElMessage.warning("请填写原因说明。");
    return false;
  }
  if (!proposalForm.segments.length || proposalForm.segments.some((segment) => !segment.segment_text.trim())) {
    ElMessage.warning("请填写完整分段文本。");
    return false;
  }
  return true;
}

async function submitTermRuleProposal(): Promise<void> {
  if (!job.value || !validateProposalForm()) {
    return;
  }
  proposalSubmitting.value = true;
  error.value = null;
  try {
    await termProposalsApi.create({
      intent: "create",
      source_term: proposalForm.source_term,
      category_id: proposalForm.category_id,
      segments: proposalForm.segments,
      reason: proposalForm.reason,
      source_job_id: job.value.id,
      source_file_id: job.value.source_file_id,
      page_number: proposalForm.page_number,
      context_before: proposalForm.context_before || null,
      context_after: proposalForm.context_after || null,
      observed_term_rule_set_id: boundTermRuleSet.value?.resource_id || null,
      observed_term_rule_version: boundTermRuleSet.value?.version || null,
      target_rule_id: null,
    });
    ElMessage.success("术语规则建议已提交。");
    proposalDialogVisible.value = false;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    proposalSubmitting.value = false;
  }
}

function openTranslationTermProposalDialog(): void {
  if (!job.value) {
    return;
  }
  resetTranslationProposalForm();
  translationProposalDialogVisible.value = true;
}

function resetTranslationProposalForm(): void {
  translationProposalForm.action = "add";
  translationProposalForm.source_term = "";
  translationProposalForm.target_term = "";
  translationProposalForm.priority = 0;
  translationProposalForm.domain = "";
  translationProposalForm.category = "";
  translationProposalForm.note = job.value ? `source=${sourceFilename.value}; mode=${job.value.mode}` : "";
}

function validateTranslationProposalForm(): boolean {
  if (!translationProposalForm.source_term.trim()) {
    ElMessage.warning("请填写原文术语。");
    return false;
  }
  if (translationProposalForm.action !== "delete" && !translationProposalForm.target_term.trim()) {
    ElMessage.warning("请填写目标译文。");
    return false;
  }
  return true;
}

async function submitTranslationTermProposal(): Promise<void> {
  if (!job.value || !validateTranslationProposalForm()) {
    return;
  }
  translationProposalSubmitting.value = true;
  error.value = null;
  try {
    await translationTermProposalsApi.create({
      language_pair: "en2zh",
      source_job_id: job.value.id,
      source_file_id: job.value.source_file_id,
      observed_translation_term_set_id: boundTranslationTermSet.value?.set_id || null,
      observed_translation_term_version: boundTranslationTermSet.value?.version || null,
      changes: [
        {
          action: translationProposalForm.action,
          source_term: translationProposalForm.source_term,
          target_term: translationProposalForm.action === "delete" ? null : translationProposalForm.target_term,
          priority: translationProposalForm.priority,
          domain: translationProposalForm.domain || null,
          category: translationProposalForm.category || null,
          note: translationProposalForm.note || null,
        },
      ],
    });
    ElMessage.success("翻译术语建议已提交。");
    translationProposalDialogVisible.value = false;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    translationProposalSubmitting.value = false;
  }
}

function stopPolling(): void {
  if (pollTimer !== undefined) {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

function syncPolling(): void {
  stopPolling();
  if (!job.value || !isActiveJobStatus(job.value.status) || document.hidden) {
    return;
  }
  pollTimer = window.setInterval(() => {
    void loadAll();
  }, 4000);
}

async function handleDownload(target: DocumentJobResponse): Promise<void> {
  downloadLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.createDownloadUrl(target.id);
    window.open(response.download_url, "_blank", "noopener");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    downloadLoading.value = false;
  }
}

async function handleRetry(target: DocumentJobResponse): Promise<void> {
  if (isAdmin.value) {
    await openRetryDialog(target);
    return;
  }
  await submitRetry(target, { reason: "frontend retry" });
}

async function submitRetryDialog(): Promise<void> {
  if (!retryDialog.job) {
    return;
  }
  await submitRetry(retryDialog.job, {
    reason: retryDialog.reason || "frontend retry",
    use_latest_term_assets: retryDialog.use_latest_term_assets,
    term_rule_set_id: retryDialog.term_rule_set_id || null,
    term_rule_set_version: retryDialog.use_latest_term_assets ? null : retryDialog.term_rule_set_version || null,
    translation_term_set_id: retryDialog.use_latest_term_assets ? null : retryDialog.translation_term_set_id || null,
    translation_term_version: retryDialog.use_latest_term_assets ? null : retryDialog.translation_term_version || null,
  });
  retryDialogVisible.value = false;
}

async function submitRetry(
  target: DocumentJobResponse,
  payload: Parameters<typeof documentJobsApi.retry>[1],
): Promise<void> {
  retryLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.retry(target.id, payload);
    job.value = response.job;
    ElMessage.success("已提交重试。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    retryLoading.value = false;
  }
}

async function handleCancel(target: DocumentJobResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      "取消后任务会变为终态，不会删除源 PDF、生成 Word 或事件记录。取消后可继续归档隐藏。",
      `取消任务 ${target.id}`,
      {
        confirmButtonText: "取消任务",
        cancelButtonText: "返回",
        type: "warning",
      },
    );
  } catch {
    return;
  }

  cancelLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.cancel(target.id);
    job.value = response.job;
    ElMessage.success("任务已取消。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    cancelLoading.value = false;
  }
}

async function handleArchive(target: DocumentJobResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      "归档后任务会从列表隐藏，不会删除源 PDF、生成 Word 或事件记录。",
      `归档任务 ${target.id}`,
      {
        confirmButtonText: "归档",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }

  archiveLoading.value = true;
  error.value = null;
  try {
    await documentJobsApi.archive(target.id);
    ElMessage.success("任务已归档。");
    await router.push("/jobs");
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    archiveLoading.value = false;
  }
}

function handleVisibilityChange(): void {
  syncPolling();
}

watch(() => job.value?.status, syncPolling);

onMounted(async () => {
  document.addEventListener("visibilitychange", handleVisibilityChange);
  await loadAll();
  syncPolling();
  if (route.query.retry === "1" && isAdmin.value && job.value?.status === "failed") {
    await openRetryDialog(job.value);
  }
});

onBeforeUnmount(() => {
  stopPolling();
  document.removeEventListener("visibilitychange", handleVisibilityChange);
});
</script>

<style scoped lang="scss">
.detail-overview {
  display: grid;
  grid-template-columns: auto minmax(220px, 420px);
  gap: 18px;
  align-items: center;
  margin-bottom: 18px;
}

.snapshot {
  max-height: 260px;
  overflow: auto;
  margin: 0;
  padding: 12px;
  border: 1px solid #d9e2ec;
  border-radius: 6px;
  background: #f8fafc;
  color: #344054;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .detail-overview {
    grid-template-columns: 1fr;
  }
}
</style>
