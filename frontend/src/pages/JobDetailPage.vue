<!-- File: frontend/src/pages/JobDetailPage.vue -->
<!-- Purpose: 展示单个 document_job 的详情、事件、文件、下载和重试入口。 -->
<template>
  <div class="job-detail-page">
    <div class="section-header">
      <div>
        <h1 class="section-title">任务详情</h1>
        <p class="section-subtitle mono">{{ jobId }}</p>
      </div>
      <div class="toolbar">
        <el-button v-if="job?.mode === 'en2zh_pdf_to_word'" :icon="DataAnalysis" @click="openTranslationQa">
          翻译 QA
        </el-button>
        <JobActions
          v-if="job"
          :job="job"
          :download-loading="downloadLoading"
          :retry-loading="retryLoading"
          :clone-loading="cloneLoading"
          :cancel-loading="cancelLoading"
          :archive-loading="archiveLoading"
          :unarchive-loading="unarchiveLoading"
          @refresh="loadAll"
          @download="handleDownload"
          @retry="handleRetry"
          @clone="handleClone"
          @cancel="handleCancel"
          @archive="handleArchive"
          @unarchive="handleUnarchive"
        />
      </div>
    </div>

    <ApiErrorAlert :error="error" />
    <el-alert
      v-if="lastDownloadLink"
      class="page-section download-link-alert"
      type="success"
      :closable="true"
      show-icon
      :title="lastDownloadLink.label"
      @close="lastDownloadLink = null"
    >
      <div class="download-link-notice">
        <span>有效期至 {{ formatDateTime(lastDownloadLink.expiresAt) }}</span>
        <a :href="lastDownloadLink.url" target="_blank" rel="noopener">打开下载链接</a>
        <el-button text size="small" @click="copyLastDownloadLink">复制链接</el-button>
      </div>
    </el-alert>

    <el-skeleton v-if="loading && !job" :rows="8" animated />

    <template v-else-if="job">
      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="概览" name="overview">
          <el-card class="page-section card-flat" shadow="never">
            <div class="detail-overview">
              <JobStatusBadge :status="job.status" />
              <JobProgress :status="job.status" :stage="job.stage" :progress="job.progress" />
            </div>

            <el-descriptions :column="2" border>
              <el-descriptions-item label="模式">{{ jobModeText[job.mode] || job.mode }}</el-descriptions-item>
              <el-descriptions-item v-if="job.mode === 'en2zh_pdf_to_word'" label="翻译 QA">
                <span class="qa-summary">
                  <el-tag :type="translationQaStatusTagType(job.translation_qa_status)" effect="plain">
                    {{ translationQaStatusText[job.translation_qa_status] }}
                  </el-tag>
                  <span>{{ translationQaReviewText }}</span>
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="文档语言">{{ job.document_language }}</el-descriptions-item>
              <el-descriptions-item label="源 PDF">{{ sourceFilename }}</el-descriptions-item>
              <el-descriptions-item label="源文件 ID">{{ job.source_file_id }}</el-descriptions-item>
              <el-descriptions-item label="来源任务 ID">{{ job.source_job_id || "-" }}</el-descriptions-item>
              <el-descriptions-item label="结果文件 ID">{{ job.result_file_id || "-" }}</el-descriptions-item>
              <el-descriptions-item label="Template">{{ boundTemplateLabel }}</el-descriptions-item>
              <el-descriptions-item label="Term Rule Set">{{ boundTermRuleSetLabel }}</el-descriptions-item>
              <el-descriptions-item label="Translation Term Set">{{ boundTranslationTermSetLabel }}</el-descriptions-item>
              <el-descriptions-item label="Translation Profile">{{ boundTranslationProfileLabel }}</el-descriptions-item>
              <el-descriptions-item label="legacy term_version_id">{{ job.term_version_id || "-" }}</el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatDateTime(job.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatDateTime(job.updated_at) }}</el-descriptions-item>
              <el-descriptions-item label="重试次数">{{ job.retry_count }}</el-descriptions-item>
              <el-descriptions-item label="完成时间">{{ formatDateTime(job.completed_at) }}</el-descriptions-item>
              <el-descriptions-item label="取消时间">{{ formatDateTime(job.canceled_at) }}</el-descriptions-item>
              <el-descriptions-item label="归档时间">{{ formatDateTime(job.archived_at) }}</el-descriptions-item>
              <el-descriptions-item label="归档人">{{ job.archived_by || "-" }}</el-descriptions-item>
              <el-descriptions-item v-if="job.mode === 'en2zh_pdf_to_word' && job.translation_qa_note" label="QA 备注">
                {{ job.translation_qa_note }}
              </el-descriptions-item>
            </el-descriptions>

            <el-alert
              v-if="runningNotice"
              class="state-alert"
              :type="runningNoticeType"
              :closable="false"
              show-icon
              :title="runningNotice"
            />
            <el-alert
              v-if="downloadHint"
              class="state-alert"
              type="success"
              :closable="false"
              show-icon
              :title="downloadHint"
            />
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="诊断" name="diagnostics">
          <el-card class="page-section card-flat" shadow="never">
            <div class="section-header">
              <div>
                <h2 class="section-title">Callback 消息</h2>
                <p class="section-subtitle">MinerU callback 的入库、重放和失败摘要；不展示 callback 原始 payload。</p>
              </div>
              <el-button :icon="Refresh" :loading="callbackSummaryLoading" @click="loadCallbackSummary()">刷新 Callback</el-button>
            </div>
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
              <el-table-column prop="message_id" label="Message" min-width="180">
                <template #default="{ row }"><span class="mono">{{ row.message_id }}</span></template>
              </el-table-column>
              <el-table-column prop="status" label="Status" width="110" />
              <el-table-column prop="attempts" label="Attempts" width="100" />
              <el-table-column prop="error_code" label="Error Code" min-width="180" />
              <el-table-column prop="error_message" label="Error Message" min-width="280" show-overflow-tooltip />
              <el-table-column label="Updated" min-width="170">
                <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
              </el-table-column>
            </el-table>
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
              <p v-if="latestErrorEvent">
                最近错误事件：{{ latestErrorEvent.message }}
                <span v-if="latestErrorEvent.trace_id" class="mono">trace_id={{ latestErrorEvent.trace_id }}</span>
              </p>
            </el-alert>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="失败阶段">{{ job.failed_stage || "-" }}</el-descriptions-item>
              <el-descriptions-item label="错误码">{{ job.error_code || "-" }}</el-descriptions-item>
              <el-descriptions-item label="错误信息">{{ job.error_message || "-" }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
          <el-empty v-else class="page-section" description="当前任务没有失败诊断" />
        </el-tab-pane>

        <el-tab-pane label="上下文" name="context">
          <el-card class="page-section card-flat" shadow="never">
            <div class="section-header">
              <div>
                <h2 class="section-title">任务上下文建议</h2>
                <p class="section-subtitle">从当前任务带入来源文件和绑定术语版本。</p>
              </div>
              <div class="toolbar">
                <el-button type="primary" :icon="EditPen" @click="openTermRuleProposal">提交术语规则建议</el-button>
                <el-button
                  v-if="job.mode === 'en2zh_pdf_to_word'"
                  :icon="EditPen"
                  @click="openTranslationTermProposal"
                >
                  提交翻译术语建议
                </el-button>
              </div>
            </div>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="来源任务">{{ job.id }}</el-descriptions-item>
              <el-descriptions-item label="来源文件">{{ job.source_file_id }}</el-descriptions-item>
              <el-descriptions-item label="Observed Term Rule Set">{{ termRuleProposalVersionLabel }}</el-descriptions-item>
              <el-descriptions-item v-if="job.mode === 'en2zh_pdf_to_word'" label="Observed Translation Term Set">
                {{ translationTermProposalVersionLabel }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card class="page-section card-flat" shadow="never">
            <div class="section-header">
              <div>
                <h2 class="section-title">请求快照</h2>
                <p class="section-subtitle">次级排障信息；主流程通常只需查看状态、失败信息和事件流。</p>
              </div>
            </div>
            <details class="snapshot-details">
              <summary>查看后端记录的非正文任务参数摘要</summary>
              <pre class="snapshot">{{ requestSnapshotPreview }}</pre>
            </details>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="文件" name="files">
          <el-card class="page-section card-flat" shadow="never">
            <div class="section-header">
              <div>
                <h2 class="section-title">文件和结果</h2>
                <p class="section-subtitle">任务绑定文件与生成产物。</p>
              </div>
              <el-button :icon="Refresh" :loading="filesLoading" @click="loadFiles()">刷新文件</el-button>
            </div>
            <el-table v-loading="filesLoading" :data="files" empty-text="暂无已登记文件" class="job-file-table">
              <el-table-column label="角色" width="128">
                <template #default="{ row }">
                  <el-tag size="small" :type="fileTagType(row.file_type)">{{ fileRoleText(row.file_type) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="文件名" min-width="220">
                <template #default="{ row }">
                  <div class="file-name">{{ row.original_filename }}</div>
                  <div class="file-meta mono">{{ row.id }}</div>
                </template>
              </el-table-column>
              <el-table-column label="类型" min-width="150">
                <template #default="{ row }">{{ fileTypeText(row.file_type) }}</template>
              </el-table-column>
              <el-table-column label="大小" width="110">
                <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="116">
                <template #default="{ row }">{{ fileAvailabilityText(row) }}</template>
              </el-table-column>
              <el-table-column label="过期时间" min-width="170">
                <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="108" fixed="right">
                <template #default="{ row }">
                  <el-button
                    size="small"
                    type="primary"
                    :icon="Download"
                    :disabled="!canDownloadFile(row)"
                    :loading="downloadingFileId === row.id"
                    @click="handleFileDownload(row)"
                  >
                    下载
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="事件" name="events">
          <el-card class="page-section card-flat" shadow="never">
            <div class="section-header">
              <div>
                <h2 class="section-title">事件流</h2>
                <p class="section-subtitle">阶段事件和排障 trace 信息。</p>
              </div>
              <div class="toolbar">
                <el-select v-model="eventLevelFilter" clearable placeholder="全部级别" style="width: 132px">
                  <el-option label="info" value="info" />
                  <el-option label="warning" value="warning" />
                  <el-option label="error" value="error" />
                </el-select>
                <el-select v-model="eventStageFilter" clearable placeholder="全部阶段" style="width: 156px">
                  <el-option
                    v-for="stage in eventStageOptions"
                    :key="stage"
                    :label="jobStageText[stage]"
                    :value="stage"
                  />
                </el-select>
                <el-button :icon="Refresh" :loading="eventsLoading" @click="loadEvents()">刷新事件</el-button>
              </div>
            </div>
            <JobEventTimeline :events="filteredEvents" />
          </el-card>
        </el-tab-pane>
      </el-tabs>

      <el-dialog v-model="retryDialogVisible" title="重试任务" width="640px">
        <el-form label-width="150px">
          <el-form-item label="任务 ID">
            <el-input :model-value="retryDialog.job?.id || ''" disabled />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="retryDialog.reason" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="配置策略">
            <el-radio-group v-model="retryDialog.strategy">
              <el-radio label="keep_original">沿用原配置</el-radio>
              <el-radio v-if="isAdmin" label="use_latest_term_assets">使用最新术语默认值</el-radio>
              <el-radio v-if="isAdmin" label="select_term_assets">指定术语版本</el-radio>
            </el-radio-group>
          </el-form-item>
          <template v-if="isAdmin && retryDialog.strategy === 'select_term_assets'">
            <el-form-item label="术语规则集">
              <el-select
                v-model="retryDialog.termRuleVersion"
                clearable
                filterable
                :loading="configLoading"
                placeholder="沿用原术语规则集"
              >
                <el-option
                  v-for="option in configSummary?.options.term_rule_sets || []"
                  :key="option.label"
                  :label="option.label"
                  :value="option.label"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="retryDialog.job?.mode === 'en2zh_pdf_to_word'" label="翻译术语集">
              <el-select
                v-model="retryDialog.translationTermVersion"
                clearable
                filterable
                :loading="configLoading"
                placeholder="沿用原翻译术语集"
              >
                <el-option
                  v-for="option in configSummary?.options.translation_term_sets || []"
                  :key="option.label"
                  :label="option.label"
                  :value="option.label"
                />
              </el-select>
            </el-form-item>
          </template>
          <el-alert
            v-if="isAdmin && retryDialog.strategy === 'use_latest_term_assets'"
            type="info"
            :closable="false"
            show-icon
            title="重试只重绑术语规则集和翻译术语集默认值；模板和翻译配置沿用原任务快照。"
          />
          <ApiErrorAlert :error="configError" />
        </el-form>
        <template #footer>
          <el-button @click="retryDialogVisible = false">取消</el-button>
          <el-button type="warning" :loading="retryLoading" @click="submitRetryDialog">提交重试</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="cloneDialogVisible" title="重新发起为新任务" width="680px">
        <el-form label-width="150px">
          <el-form-item label="源任务 ID">
            <el-input :model-value="cloneDialog.job?.id || ''" disabled />
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="cloneDialog.reason" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="配置策略">
            <el-radio-group v-model="cloneDialog.strategy">
              <el-radio label="keep_source_snapshot">沿用源任务快照</el-radio>
              <el-radio label="use_current_defaults">使用当前默认配置</el-radio>
              <el-radio v-if="isAdmin" label="select_published_versions">指定 published 版本</el-radio>
            </el-radio-group>
          </el-form-item>
          <template v-if="isAdmin && cloneDialog.strategy === 'select_published_versions'">
            <el-form-item label="Template">
              <el-select
                v-model="cloneDialog.templateVersion"
                clearable
                filterable
                :loading="configLoading"
                placeholder="使用当前默认模板"
              >
                <el-option
                  v-for="option in configSummary?.options.templates || []"
                  :key="option.label"
                  :label="option.label"
                  :value="option.label"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="术语规则集">
              <el-select
                v-model="cloneDialog.termRuleVersion"
                clearable
                filterable
                :loading="configLoading"
                placeholder="使用当前默认术语规则集"
              >
                <el-option
                  v-for="option in configSummary?.options.term_rule_sets || []"
                  :key="option.label"
                  :label="option.label"
                  :value="option.label"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="cloneDialog.job?.mode === 'en2zh_pdf_to_word'" label="翻译术语集">
              <el-select
                v-model="cloneDialog.translationTermVersion"
                clearable
                filterable
                :loading="configLoading"
                placeholder="使用当前默认翻译术语集"
              >
                <el-option
                  v-for="option in configSummary?.options.translation_term_sets || []"
                  :key="option.label"
                  :label="option.label"
                  :value="option.label"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="cloneDialog.job?.mode === 'en2zh_pdf_to_word'" label="翻译配置">
              <el-select
                v-model="cloneDialog.translationProfileVersion"
                clearable
                filterable
                :loading="configLoading"
                placeholder="使用当前默认翻译配置"
              >
                <el-option
                  v-for="option in configSummary?.options.translation_profiles || []"
                  :key="option.label"
                  :label="option.label"
                  :value="option.label"
                />
              </el-select>
            </el-form-item>
          </template>
          <el-alert
            v-if="cloneDialog.strategy === 'keep_source_snapshot'"
            type="info"
            :closable="false"
            show-icon
            title="重新发起会创建独立新任务；源任务状态、retry_count、归档状态都不会改变。"
          />
          <ApiErrorAlert :error="configError" />
        </el-form>
        <template #footer>
          <el-button @click="cloneDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="cloneLoading" @click="submitCloneDialog">创建新任务</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { DataAnalysis, Download, EditPen, Refresh } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import type {
  DocumentFileResponse,
  DocumentJobCallbackMessageSummaryResponse,
  DocumentJobCloneRequest,
  DocumentJobConfigSummaryResponse,
  DocumentJobConfigVersionOption,
  DocumentJobEventResponse,
  DocumentJobResourceSnapshot,
  DocumentJobRetryRequest,
  DocumentJobResponse,
  DocumentJobStage,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import JobActions from "@/components/JobActions.vue";
import JobEventTimeline from "@/components/JobEventTimeline.vue";
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import { useAuthStore } from "@/stores/auth";
import {
  formatBytes,
  formatDateTime,
  getJobSourceFilename,
  isActiveJobStatus,
  jobModeText,
  jobStageText,
  translationQaStatusTagType,
  translationQaStatusText,
} from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { copyDownloadLink, openDownloadLink, type DownloadLinkNotice } from "@/utils/download";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const jobId = computed(() => String(route.params.jobId || ""));
const job = ref<DocumentJobResponse | null>(null);
const events = ref<DocumentJobEventResponse[]>([]);
const files = ref<DocumentFileResponse[]>([]);
const callbackSummary = ref<DocumentJobCallbackMessageSummaryResponse | null>(null);
const loading = ref(false);
const eventsLoading = ref(false);
const filesLoading = ref(false);
const callbackSummaryLoading = ref(false);
const downloadLoading = ref(false);
const downloadingFileId = ref<string | null>(null);
const retryLoading = ref(false);
const cloneLoading = ref(false);
const cancelLoading = ref(false);
const archiveLoading = ref(false);
const unarchiveLoading = ref(false);
const retryDialogVisible = ref(false);
const cloneDialogVisible = ref(false);
const activeTab = ref("overview");
const eventLevelFilter = ref<"" | "info" | "warning" | "error">("");
const eventStageFilter = ref<DocumentJobStage | "">("");
const error = ref<ApiClientError | null>(null);
const configError = ref<ApiClientError | null>(null);
const configLoading = ref(false);
const configSummary = ref<DocumentJobConfigSummaryResponse | null>(null);
const lastDownloadLink = ref<DownloadLinkNotice | null>(null);
let pollTimer: number | undefined;

type RetryStrategy = "keep_original" | "use_latest_term_assets" | "select_term_assets";
type CloneConfigStrategy = NonNullable<DocumentJobCloneRequest["config_strategy"]>;

const retryDialog = reactive({
  job: null as DocumentJobResponse | null,
  reason: "frontend retry",
  strategy: "keep_original" as RetryStrategy,
  termRuleVersion: "",
  translationTermVersion: "",
});
const cloneDialog = reactive({
  job: null as DocumentJobResponse | null,
  reason: "frontend clone",
  strategy: "keep_source_snapshot" as CloneConfigStrategy,
  templateVersion: "",
  termRuleVersion: "",
  translationTermVersion: "",
  translationProfileVersion: "",
});
const eventStageOptions: DocumentJobStage[] = [
  "uploaded",
  "parsing",
  "parsed",
  "ir_converting",
  "rendering",
  "uploading",
  "completed",
  "failed",
  "canceled",
];

const isAdmin = computed(() => auth.user?.role === "admin");
const requestSnapshotPreview = computed(() => JSON.stringify(job.value?.request_snapshot || {}, null, 2));
const sourceFilename = computed(() => (job.value ? getJobSourceFilename(job.value) : "-"));
const translationQaReviewText = computed(() => {
  if (!job.value || job.value.translation_qa_status === "unreviewed") {
    return "尚未复核";
  }
  return `${job.value.translation_qa_reviewed_by || "-"} · ${formatDateTime(job.value.translation_qa_reviewed_at)}`;
});
const resourceSnapshot = computed(() => readResourceSnapshot(job.value?.request_snapshot.resources));
const boundTemplate = computed(() => resourceSnapshot.value?.template || null);
const boundTermRuleSet = computed(() => resourceSnapshot.value?.term_rule_set || null);
const boundTranslationTermSet = computed(() => resourceSnapshot.value?.translation_term_set || null);
const boundTranslationProfile = computed(() => resourceSnapshot.value?.translation_profile || null);
const boundTemplateLabel = computed(() => {
  const bound = boundTemplate.value;
  return bound ? `${bound.resource_id}@${bound.version}` : job.value?.template_version_id || "-";
});
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
const boundTranslationProfileLabel = computed(() => {
  const bound = boundTranslationProfile.value;
  if (!bound) {
    const profile = readRecord(job.value?.request_snapshot.translation_profile);
    return versionLabel(
      readString(profile?.translation_profile_id),
      readString(profile?.translation_profile_version),
    );
  }
  return `${bound.resource_id}@${bound.version}`;
});
const termRuleProposalVersionLabel = computed(() =>
  versionLabel(termRuleProposalSetId.value, termRuleProposalVersion.value),
);
const translationTermProposalVersionLabel = computed(() =>
  versionLabel(translationTermProposalSetId.value, translationTermProposalVersion.value),
);
const termRuleProposalSetId = computed(() => {
  const bound = boundTermRuleSet.value;
  if (bound) {
    return bound.resource_id;
  }
  const assets = readRecord(job.value?.request_snapshot.term_assets);
  return readString(assets?.term_rule_set_id);
});
const termRuleProposalVersion = computed(() => {
  const bound = boundTermRuleSet.value;
  if (bound) {
    return bound.version;
  }
  const assets = readRecord(job.value?.request_snapshot.term_assets);
  return readString(assets?.term_rule_set_version);
});
const translationTermProposalSetId = computed(() => {
  const bound = boundTranslationTermSet.value;
  if (bound) {
    return bound.set_id;
  }
  const assets = readRecord(job.value?.request_snapshot.term_assets);
  return readString(assets?.translation_term_set_id);
});
const translationTermProposalVersion = computed(() => {
  const bound = boundTranslationTermSet.value;
  if (bound) {
    return bound.version;
  }
  const assets = readRecord(job.value?.request_snapshot.term_assets);
  return readString(assets?.translation_term_version) || job.value?.term_version_id || null;
});
const selectedRetryTermRuleOption = computed(() =>
  findConfigOption(configSummary.value?.options.term_rule_sets || [], retryDialog.termRuleVersion),
);
const selectedRetryTranslationTermOption = computed(() =>
  findConfigOption(configSummary.value?.options.translation_term_sets || [], retryDialog.translationTermVersion),
);
const selectedCloneTemplateOption = computed(() =>
  findConfigOption(configSummary.value?.options.templates || [], cloneDialog.templateVersion),
);
const selectedCloneTermRuleOption = computed(() =>
  findConfigOption(configSummary.value?.options.term_rule_sets || [], cloneDialog.termRuleVersion),
);
const selectedCloneTranslationTermOption = computed(() =>
  findConfigOption(configSummary.value?.options.translation_term_sets || [], cloneDialog.translationTermVersion),
);
const selectedCloneTranslationProfileOption = computed(() =>
  findConfigOption(configSummary.value?.options.translation_profiles || [], cloneDialog.translationProfileVersion),
);
const filteredEvents = computed(() =>
  events.value.filter((event) => {
    if (eventLevelFilter.value && event.level !== eventLevelFilter.value) {
      return false;
    }
    if (eventStageFilter.value && event.stage !== eventStageFilter.value) {
      return false;
    }
    return true;
  }),
);
const latestErrorEvent = computed(() => [...events.value].reverse().find((event) => event.level === "error") || null);
const failureSummary = computed(() => {
  if (!job.value) {
    return "任务处理失败。";
  }
  const stage = job.value.failed_stage || job.value.stage || "unknown";
  const code = job.value.error_code || "unknown";
  return `任务在 ${stage} 阶段失败，错误码 ${code}。`;
});
const failureHelpText = computed(() => {
  const code = job.value?.error_code || "";
  if (code === "document_job_invalid_input") {
    return "输入文件或任务参数不满足后端校验。请换一个 PDF 或联系管理员确认输入限制。";
  }
  if (job.value?.failed_stage === "parsing") {
    return "PDF 解析阶段失败。可先重试；如果仍失败，请把错误码和 trace_id 交给技术运营排查 MinerU 或文件内容问题。";
  }
  if (job.value?.failed_stage === "uploading") {
    return "结果保存阶段失败。通常与对象存储或文件登记有关，请重试后再联系技术运营。";
  }
  return "可以点击重试；如果后端返回 409，说明当前失败不可重试或次数已达上限，请按返回原因处理。";
});
const runningNotice = computed(() => {
  if (!job.value || !isActiveJobStatus(job.value.status)) {
    return "";
  }
  const timeoutAt = parseDate(job.value.timeout_at);
  if (timeoutAt && timeoutAt.getTime() <= Date.now()) {
    return "任务已超过预计超时时间，仍会继续轮询；请刷新事件流，必要时联系技术运营。";
  }
  const updatedAt = parseDate(job.value.updated_at);
  if (updatedAt && Date.now() - updatedAt.getTime() > 10 * 60 * 1000) {
    return "任务已超过 10 分钟没有状态更新，请查看事件流或稍后刷新。";
  }
  return "任务处理中，页面会自动轮询，终态后停止。";
});
const runningNoticeType = computed<"info" | "warning">(() => {
  if (!job.value || !isActiveJobStatus(job.value.status)) {
    return "info";
  }
  const timeoutAt = parseDate(job.value.timeout_at);
  const updatedAt = parseDate(job.value.updated_at);
  if ((timeoutAt && timeoutAt.getTime() <= Date.now()) || (updatedAt && Date.now() - updatedAt.getTime() > 10 * 60 * 1000)) {
    return "warning";
  }
  return "info";
});
const downloadHint = computed(() => {
  if (job.value?.status !== "succeeded") {
    return "";
  }
  return "结果已生成。点击下载会重新获取临时链接，链接失效后再次点击下载即可。";
});
const callbackSummaryItems = computed(() => [
  { label: "pending", value: String(callbackStatusCount("pending")) },
  { label: "running", value: String(callbackStatusCount("running")) },
  { label: "processed", value: String(callbackStatusCount("processed")) },
  { label: "failed", value: String(callbackStatusCount("failed")) },
  { label: "ignored", value: String(callbackStatusCount("ignored")) },
  { label: "replayable", value: String(callbackSummary.value?.replayable_count ?? 0) },
  { label: "oldest replayable", value: secondsLabel(callbackSummary.value?.oldest_replayable_age_seconds ?? null) },
]);

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

function parseDate(value?: string | null): Date | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function secondsLabel(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return `${value} 秒`;
}

function callbackStatusCount(status: string): number {
  return callbackSummary.value?.status_counts[status] ?? 0;
}

async function loadJob(targetJobId = jobId.value): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.get(targetJobId);
    if (targetJobId === jobId.value) {
      job.value = response;
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

async function loadEvents(targetJobId = jobId.value): Promise<void> {
  eventsLoading.value = true;
  try {
    const response = await documentJobsApi.listEvents(targetJobId);
    if (targetJobId === jobId.value) {
      events.value = response.items;
    }
  } catch (caught) {
    if (targetJobId === jobId.value) {
      error.value = normalizeApiError(caught);
    }
  } finally {
    if (targetJobId === jobId.value) {
      eventsLoading.value = false;
    }
  }
}

async function loadFiles(targetJobId = jobId.value): Promise<void> {
  filesLoading.value = true;
  try {
    const response = await documentJobsApi.listFiles(targetJobId);
    if (targetJobId === jobId.value) {
      files.value = response.files;
    }
  } catch (caught) {
    if (targetJobId === jobId.value) {
      error.value = normalizeApiError(caught);
    }
  } finally {
    if (targetJobId === jobId.value) {
      filesLoading.value = false;
    }
  }
}

async function loadCallbackSummary(targetJobId = jobId.value): Promise<void> {
  callbackSummaryLoading.value = true;
  try {
    const response = await documentJobsApi.getCallbackMessageSummary(targetJobId);
    if (targetJobId === jobId.value) {
      callbackSummary.value = response;
    }
  } catch (caught) {
    if (targetJobId === jobId.value) {
      error.value = normalizeApiError(caught);
    }
  } finally {
    if (targetJobId === jobId.value) {
      callbackSummaryLoading.value = false;
    }
  }
}

async function loadAll(): Promise<void> {
  const targetJobId = jobId.value;
  await loadJob(targetJobId);
  if (targetJobId !== jobId.value) {
    return;
  }
  if (job.value) {
    await Promise.all([loadEvents(targetJobId), loadFiles(targetJobId), loadCallbackSummary(targetJobId)]);
  } else {
    events.value = [];
    files.value = [];
    callbackSummary.value = null;
  }
}

function openRetryDialog(target: DocumentJobResponse): void {
  retryDialog.job = target;
  retryDialog.reason = "frontend retry";
  retryDialog.strategy = "keep_original";
  retryDialog.termRuleVersion = "";
  retryDialog.translationTermVersion = "";
  retryDialogVisible.value = true;
  if (isAdmin.value && !configSummary.value) {
    void loadConfigSummary();
  }
}

function openCloneDialog(target: DocumentJobResponse): void {
  cloneDialog.job = target;
  cloneDialog.reason = "frontend clone";
  cloneDialog.strategy = "keep_source_snapshot";
  cloneDialog.templateVersion = "";
  cloneDialog.termRuleVersion = "";
  cloneDialog.translationTermVersion = "";
  cloneDialog.translationProfileVersion = "";
  cloneDialogVisible.value = true;
  if (isAdmin.value && !configSummary.value) {
    void loadConfigSummary();
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

function proposalBaseQuery(tab: "new" | "translation-new"): Record<string, string> {
  if (!job.value) {
    return { tab };
  }
  return {
    tab,
    source_job_id: job.value.id,
    source_file_id: job.value.source_file_id,
  };
}

function appendQueryValue(query: Record<string, string>, key: string, value?: string | null): void {
  if (value) {
    query[key] = value;
  }
}

function openTermRuleProposal(): void {
  const query = proposalBaseQuery("new");
  appendQueryValue(query, "observed_term_rule_set_id", termRuleProposalSetId.value);
  appendQueryValue(query, "observed_term_rule_version", termRuleProposalVersion.value);
  void router.push({ name: "term-proposals", query });
}

function openTranslationTermProposal(): void {
  const query = proposalBaseQuery("translation-new");
  appendQueryValue(query, "observed_translation_term_set_id", translationTermProposalSetId.value);
  appendQueryValue(query, "observed_translation_term_version", translationTermProposalVersion.value);
  void router.push({ name: "term-proposals", query });
}

function openTranslationQa(): void {
  if (!job.value) {
    return;
  }
  void router.push({ name: "job-translation-qa", params: { jobId: job.value.id } });
}

async function handleDownload(target: DocumentJobResponse): Promise<void> {
  downloadLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.createDownloadUrl(target.id);
    lastDownloadLink.value = {
      label: `任务 ${target.id} 的下载链接已生成`,
      url: response.download_url,
      expiresAt: response.expires_at,
      fileName: response.file.original_filename,
    };
    const opened = openDownloadLink(response.download_url);
    if (opened) {
      ElMessage.success(`下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
    } else {
      ElMessage.warning("浏览器可能拦截了新窗口，页面已显示下载链接。");
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    downloadLoading.value = false;
  }
}

async function handleFileDownload(file: DocumentFileResponse): Promise<void> {
  if (!job.value) {
    return;
  }
  downloadingFileId.value = file.id;
  error.value = null;
  try {
    const response = await documentJobsApi.createDownloadUrl(job.value.id, file.id);
    lastDownloadLink.value = {
      label: `${file.original_filename} 的下载链接已生成`,
      url: response.download_url,
      expiresAt: response.expires_at,
      fileName: response.file.original_filename,
    };
    const opened = openDownloadLink(response.download_url);
    if (opened) {
      ElMessage.success(`下载链接已生成，有效期至 ${formatDateTime(response.expires_at)}。`);
    } else {
      ElMessage.warning("浏览器可能拦截了新窗口，页面已显示下载链接。");
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    downloadingFileId.value = null;
  }
}

async function copyLastDownloadLink(): Promise<void> {
  if (!lastDownloadLink.value) {
    return;
  }
  const copied = await copyDownloadLink(lastDownloadLink.value.url);
  if (copied) {
    ElMessage.success("下载链接已复制。");
    return;
  }
  ElMessage.warning("当前浏览器不支持自动复制。");
}

function handleRetry(target: DocumentJobResponse): void {
  openRetryDialog(target);
}

function handleClone(target: DocumentJobResponse): void {
  openCloneDialog(target);
}

async function handleCancel(target: DocumentJobResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      "取消会将任务标记为 canceled 并停止后续处理；如果任务已进入外部服务，系统不承诺强制中断该外部处理。文件和事件记录会保留。",
      "取消任务",
      {
        confirmButtonText: "确认取消",
        cancelButtonText: "返回",
        type: "warning",
      },
    );
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
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
      "归档只会把终态任务从默认列表隐藏，不会删除源文件、结果文件或事件记录。开启列表的“含归档”后仍可查看。",
      "归档任务",
      {
        confirmButtonText: "确认归档",
        cancelButtonText: "返回",
        type: "info",
      },
    );
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
    return;
  }
  archiveLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.archive(target.id);
    job.value = response.job;
    ElMessage.success("任务已归档。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    archiveLoading.value = false;
  }
}

async function handleUnarchive(target: DocumentJobResponse): Promise<void> {
  try {
    await ElMessageBox.confirm(
      "取消归档会让任务重新出现在默认列表中，不会修改源文件、结果文件或事件记录。",
      "取消归档",
      {
        confirmButtonText: "确认取消归档",
        cancelButtonText: "返回",
        type: "info",
      },
    );
  } catch (caught) {
    if (caught === "cancel" || caught === "close") {
      return;
    }
    error.value = normalizeApiError(caught);
    return;
  }
  unarchiveLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.unarchive(target.id);
    job.value = response.job;
    ElMessage.success("任务已取消归档。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    unarchiveLoading.value = false;
  }
}

async function submitRetryDialog(): Promise<void> {
  if (!retryDialog.job) {
    return;
  }
  await submitRetry(retryDialog.job, buildRetryPayload());
  retryDialogVisible.value = false;
}

async function submitCloneDialog(): Promise<void> {
  if (!cloneDialog.job) {
    return;
  }
  cloneLoading.value = true;
  error.value = null;
  try {
    const response = await documentJobsApi.clone(cloneDialog.job.id, buildClonePayload());
    cloneDialogVisible.value = false;
    ElMessage.success("已创建新任务。");
    await router.push({ name: "job-detail", params: { jobId: response.job_id } });
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    cloneLoading.value = false;
  }
}

function buildRetryPayload(): DocumentJobRetryRequest {
  const payload: DocumentJobRetryRequest = {
    reason: retryDialog.reason || "frontend retry",
  };
  if (!isAdmin.value) {
    return payload;
  }
  if (retryDialog.strategy === "use_latest_term_assets") {
    payload.use_latest_term_assets = true;
    return payload;
  }
  if (retryDialog.strategy !== "select_term_assets") {
    return payload;
  }
  if (selectedRetryTermRuleOption.value) {
    payload.term_rule_set_id = selectedRetryTermRuleOption.value.resource_id;
    payload.term_rule_set_version = selectedRetryTermRuleOption.value.version;
  }
  if (retryDialog.job?.mode === "en2zh_pdf_to_word" && selectedRetryTranslationTermOption.value) {
    payload.translation_term_set_id = selectedRetryTranslationTermOption.value.resource_id;
    payload.translation_term_version = selectedRetryTranslationTermOption.value.version;
  }
  return payload;
}

function buildClonePayload(): DocumentJobCloneRequest {
  const payload: DocumentJobCloneRequest = {
    reason: cloneDialog.reason || "frontend clone",
    config_strategy: cloneDialog.strategy,
  };
  if (!isAdmin.value || cloneDialog.strategy !== "select_published_versions") {
    return payload;
  }
  if (selectedCloneTemplateOption.value) {
    payload.template_version_id = configVersionId(selectedCloneTemplateOption.value);
  }
  if (selectedCloneTermRuleOption.value) {
    payload.term_rule_set_id = selectedCloneTermRuleOption.value.resource_id;
    payload.term_rule_set_version = selectedCloneTermRuleOption.value.version;
  }
  if (cloneDialog.job?.mode === "en2zh_pdf_to_word" && selectedCloneTranslationTermOption.value) {
    payload.translation_term_set_id = selectedCloneTranslationTermOption.value.resource_id;
    payload.translation_term_version = selectedCloneTranslationTermOption.value.version;
  }
  if (cloneDialog.job?.mode === "en2zh_pdf_to_word" && selectedCloneTranslationProfileOption.value) {
    payload.translation_profile_id = selectedCloneTranslationProfileOption.value.resource_id;
    payload.translation_profile_version = selectedCloneTranslationProfileOption.value.version;
  }
  return payload;
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

async function loadConfigSummary(): Promise<void> {
  configLoading.value = true;
  configError.value = null;
  try {
    configSummary.value = await documentJobsApi.getConfigSummary();
  } catch (caught) {
    configError.value = normalizeApiError(caught);
  } finally {
    configLoading.value = false;
  }
}

function findConfigOption(
  options: DocumentJobConfigVersionOption[],
  label: string,
): DocumentJobConfigVersionOption | null {
  return options.find((option) => option.label === label) || null;
}

function configVersionId(option: DocumentJobConfigVersionOption): string {
  return `${option.resource_id}@${option.version}`;
}

function handleVisibilityChange(): void {
  syncPolling();
}

function resetPageStateForRouteChange(): void {
  stopPolling();
  job.value = null;
  events.value = [];
  files.value = [];
  callbackSummary.value = null;
  error.value = null;
  configError.value = null;
  lastDownloadLink.value = null;
  retryDialogVisible.value = false;
  cloneDialogVisible.value = false;
  eventLevelFilter.value = "";
  eventStageFilter.value = "";
  activeTab.value = "overview";
}

// 文件区只做展示映射；文件归属、过期和下载权限以后端校验为准。
function fileRoleText(fileType: string): string {
  if (fileType === "source_pdf") {
    return "源文件";
  }
  if (fileType === "generated_word") {
    return "结果";
  }
  if (fileType === "ai_call_log" || fileType === "ai_debug_archive") {
    return "日志";
  }
  return "中间产物";
}

function fileTypeText(fileType: string): string {
  const labels: Record<string, string> = {
    source_pdf: "源 PDF",
    generated_word: "生成 Word",
    mineru_raw_result: "MinerU 原始结果",
    document_ir: "DocumentIR",
    image_asset: "图片资产",
    ai_call_log: "AI 调用日志",
    ai_debug_archive: "AI debug 归档",
  };
  return labels[fileType] || fileType;
}

function fileTagType(fileType: string): "success" | "warning" | "info" {
  if (fileType === "generated_word") {
    return "success";
  }
  if (fileType === "ai_call_log" || fileType === "ai_debug_archive") {
    return "warning";
  }
  return "info";
}

function isFileExpired(file: DocumentFileResponse): boolean {
  const expiresAt = parseDate(file.expires_at);
  return Boolean(expiresAt && expiresAt.getTime() <= Date.now());
}

function canDownloadFile(file: DocumentFileResponse): boolean {
  return file.status === "uploaded" && !isFileExpired(file);
}

function fileAvailabilityText(file: DocumentFileResponse): string {
  if (file.status !== "uploaded") {
    return file.status;
  }
  if (isFileExpired(file)) {
    return "已过期";
  }
  return "可下载";
}

watch(() => job.value?.status, syncPolling);

watch(jobId, async (nextJobId, previousJobId) => {
  if (!nextJobId || nextJobId === previousJobId) {
    return;
  }
  resetPageStateForRouteChange();
  await loadAll();
  syncPolling();
  if (route.query.retry === "1" && job.value?.status === "failed") {
    openRetryDialog(job.value);
  }
});

onMounted(async () => {
  document.addEventListener("visibilitychange", handleVisibilityChange);
  await loadAll();
  syncPolling();
  if (route.query.retry === "1" && job.value?.status === "failed") {
    openRetryDialog(job.value);
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

.state-alert {
  margin-top: 14px;
}

.download-link-alert {
  margin-top: 0;
}

.download-link-notice {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.download-link-notice span {
  color: #667085;
  font-size: 13px;
}

.download-link-notice a {
  color: #2563eb;
  font-weight: 700;
  text-decoration: none;
}

.qa-summary {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.failure-summary {
  margin-bottom: 14px;
}

.failure-summary p {
  margin: 4px 0 0;
}

.snapshot-details {
  color: #344054;
}

.snapshot-details summary {
  margin-bottom: 10px;
  cursor: pointer;
  font-weight: 600;
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

.job-file-table {
  width: 100%;
}

.file-name {
  word-break: break-word;
  font-weight: 600;
  color: #1f2937;
}

.file-meta {
  margin-top: 3px;
  color: #667085;
  font-size: 12px;
  word-break: break-all;
}

@media (max-width: 760px) {
  .detail-overview {
    grid-template-columns: 1fr;
  }
}
</style>
