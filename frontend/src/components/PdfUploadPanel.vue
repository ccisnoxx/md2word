<!-- frontend/src/components/PdfUploadPanel.vue: Authorize, upload, and create one document job from a PDF. -->
<template>
  <el-card class="upload-card card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">上传 PDF 创建任务</h2>
        <p class="section-subtitle">默认创建 PDF 直接转 Word 任务。</p>
      </div>
      <el-tag type="info" effect="plain">单文件</el-tag>
    </div>

    <ApiErrorAlert :error="error" />

    <el-steps class="upload-steps" :active="activeStep" finish-status="success" process-status="process">
      <el-step title="选择 PDF" />
      <el-step title="上传文件" />
      <el-step title="创建任务" />
    </el-steps>

    <el-upload
      ref="uploadRef"
      drag
      action=""
      accept=".pdf,application/pdf"
      :auto-upload="false"
      :limit="1"
      :on-change="handleFileChange"
      :on-remove="handleFileRemove"
      :on-exceed="handleExceed"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">拖入 PDF，或点击选择文件</div>
      <template #tip>
        <div class="el-upload__tip">最大 {{ maxUploadMb }} MB；后端会继续校验文件内容和页数。</div>
      </template>
    </el-upload>

    <div v-if="enableEn2zh" class="mode-row">
      <span class="mode-label">任务模式</span>
      <el-radio-group v-model="mode" size="small">
        <el-radio-button label="direct_pdf_to_word">直接转 Word</el-radio-button>
        <el-radio-button label="en2zh_pdf_to_word">英译中</el-radio-button>
      </el-radio-group>
    </div>

    <div class="config-panel" v-loading="configLoading">
      <div class="config-panel-header">
        <div>
          <strong>任务配置</strong>
          <small>{{ isAdmin ? "默认配置，可按需指定 published 版本。" : "使用当前默认配置创建任务。" }}</small>
        </div>
        <div class="config-panel-actions">
          <el-tag size="small" effect="plain">{{ configSummary?.resource_mode || "unknown" }}</el-tag>
          <el-button link size="small" :loading="configLoading" @click="loadConfigSummary">重新加载</el-button>
        </div>
      </div>
      <ApiErrorAlert :error="configError" />
      <div class="config-summary-grid">
        <div v-for="item in defaultConfigItems" :key="item.key" class="config-summary-item">
          <span>{{ item.label }}</span>
          <b>{{ item.value }}</b>
        </div>
      </div>
      <el-alert
        v-if="configWarnings.length"
        class="config-warning"
        type="warning"
        :closable="false"
        show-icon
        :title="configWarnings.join('；')"
      />
      <el-alert
        v-if="p0ExecutionBlocked"
        class="config-warning"
        type="error"
        title="P0 执行链路未就绪"
        :closable="false"
        show-icon
      >
        <ul class="config-blocker-list">
          <li v-for="blocker in p0ReadinessMessages" :key="blocker">{{ blocker }}</li>
        </ul>
      </el-alert>

      <div v-if="isAdmin" class="admin-config">
        <el-divider />
        <div class="admin-config-grid">
          <label>
            <span>模板版本</span>
            <el-select v-model="selectedTemplateVersion" clearable filterable placeholder="使用默认模板">
              <el-option
                v-for="option in configSummary?.options.templates || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </label>
          <label>
            <span>术语规则集</span>
            <el-select v-model="selectedTermRuleVersion" clearable filterable placeholder="使用默认规则集">
              <el-option
                v-for="option in configSummary?.options.term_rule_sets || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </label>
          <label v-if="mode === 'en2zh_pdf_to_word'">
            <span>翻译术语集</span>
            <el-select v-model="selectedTranslationTermVersion" clearable filterable placeholder="使用默认翻译术语">
              <el-option
                v-for="option in configSummary?.options.translation_term_sets || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </label>
          <label v-if="mode === 'en2zh_pdf_to_word'">
            <span>翻译配置</span>
            <el-select v-model="selectedTranslationProfileVersion" clearable filterable placeholder="使用默认翻译配置">
              <el-option
                v-for="option in configSummary?.options.translation_profiles || []"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </label>
        </div>
      </div>
    </div>

    <div class="upload-footer">
      <div class="muted">{{ statusText }}</div>
      <el-button type="primary" :icon="Upload" :loading="submitting" :disabled="createDisabled" @click="submit">
        创建任务
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, type UploadFile, type UploadInstance, type UploadRawFile } from "element-plus";
import { Upload, UploadFilled } from "@element-plus/icons-vue";

import type {
  DocumentJobConfigSummaryResponse,
  DocumentJobCreateRequest,
  DocumentJobMode,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { useAuthStore } from "@/stores/auth";
import { getMaxUploadBytes, uploadFileContent, validatePdfFile } from "@/utils/upload";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { readinessCodeText } from "@/utils/displayText";
import { configOptionKey, configVersionId, findConfigOption } from "@/utils/configOptions";

const emit = defineEmits<{
  created: [jobId: string];
}>();

const auth = useAuthStore();
const uploadRef = ref<UploadInstance>();
const selectedFile = ref<File | null>(null);
const submitting = ref(false);
const statusText = ref("等待选择 PDF。");
const createStep = ref<"select" | "authorize" | "upload" | "create" | "done" | "failed">("select");
const error = ref<ApiClientError | null>(null);
const configError = ref<ApiClientError | null>(null);
const configLoading = ref(false);
const configSummary = ref<DocumentJobConfigSummaryResponse | null>(null);
const mode = ref<DocumentJobMode>("direct_pdf_to_word");
const selectedTemplateVersion = ref("");
const selectedTermRuleVersion = ref("");
const selectedTranslationTermVersion = ref("");
const selectedTranslationProfileVersion = ref("");
const enableEn2zh = import.meta.env.VITE_ENABLE_EN2ZH === "true";
const maxUploadMb = computed(() => Math.round(getMaxUploadBytes() / 1024 / 1024));
const isAdmin = computed(() => auth.user?.role === "admin");
const configWarnings = computed(() => (configSummary.value?.readiness.warnings || []).map(readinessCodeText));
const p0ReadinessBlockers = computed(() => configSummary.value?.readiness.blockers || []);
const p0ExecutionBlocked = computed(() => Boolean(
  configSummary.value?.readiness.p0_document_jobs_required
  && !configSummary.value?.readiness.p0_document_jobs_ready,
));
const p0ReadinessMessages = computed(() => (
  (p0ReadinessBlockers.value.length > 0 ? p0ReadinessBlockers.value : ["p0_document_jobs_not_ready"]).map(readinessCodeText)
));
const configUnavailable = computed(() => Boolean(configError.value || !configSummary.value));
const createDisabled = computed(() => (
  !selectedFile.value || configLoading.value || configUnavailable.value || p0ExecutionBlocked.value
));
const defaultConfigItems = computed(() => {
  const defaults = configSummary.value?.defaults;
  const items = [
    { key: "template", label: "模板", value: defaults?.template?.label || "未配置" },
    { key: "term-rule-set", label: "术语规则集", value: defaults?.term_rule_set?.label || "未配置" },
  ];
  if (mode.value === "en2zh_pdf_to_word") {
    items.push(
      { key: "translation-term-set", label: "翻译术语集", value: defaults?.translation_term_set?.label || "未配置" },
      { key: "translation-profile", label: "翻译配置", value: defaults?.translation_profile?.label || "未配置" },
    );
  }
  return items;
});
const activeStep = computed(() => {
  if (createStep.value === "authorize" || createStep.value === "upload") {
    return 1;
  }
  if (createStep.value === "create") {
    return 2;
  }
  if (createStep.value === "done") {
    return 3;
  }
  return selectedFile.value ? 1 : 0;
});

const selectedTemplateOption = computed(() =>
  findConfigOption(configSummary.value?.options.templates || [], selectedTemplateVersion.value),
);
const selectedTermRuleOption = computed(() =>
  findConfigOption(configSummary.value?.options.term_rule_sets || [], selectedTermRuleVersion.value),
);
const selectedTranslationTermOption = computed(() =>
  findConfigOption(configSummary.value?.options.translation_term_sets || [], selectedTranslationTermVersion.value),
);
const selectedTranslationProfileOption = computed(() =>
  findConfigOption(configSummary.value?.options.translation_profiles || [], selectedTranslationProfileVersion.value),
);

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

function handleFileChange(uploadFile: UploadFile): void {
  const rawFile = uploadFile.raw as UploadRawFile | undefined;
  if (!rawFile) {
    return;
  }
  const validationError = validatePdfFile(rawFile);
  if (validationError) {
    selectedFile.value = null;
    error.value = { message: validationError, raw: validationError };
    uploadRef.value?.clearFiles();
    return;
  }
  selectedFile.value = rawFile;
  error.value = null;
  createStep.value = "select";
  statusText.value = `已选择 ${rawFile.name}。`;
}

function handleFileRemove(): void {
  selectedFile.value = null;
  createStep.value = "select";
  statusText.value = "等待选择 PDF。";
}

function handleExceed(): void {
  ElMessage.warning("当前仅支持单文件上传。");
}

async function submit(): Promise<void> {
  if (!selectedFile.value || submitting.value || configLoading.value || configUnavailable.value || p0ExecutionBlocked.value) {
    return;
  }

  submitting.value = true;
  error.value = null;

  try {
    createStep.value = "authorize";
    statusText.value = "正在获取上传授权。";
    const authorization = await filesApi.createUploadUrl({
      filename: selectedFile.value.name,
      mime_type: selectedFile.value.type || "application/pdf",
      size_bytes: selectedFile.value.size,
      file_type: "source_pdf",
    });

    createStep.value = "upload";
    statusText.value = "正在上传 PDF 内容。";
    await uploadFileContent(authorization, selectedFile.value, auth.token);

    createStep.value = "create";
    statusText.value = "正在创建转换任务。";
    const payload: DocumentJobCreateRequest = {
      source_file_id: authorization.file_id,
      mode: mode.value,
      document_language: mode.value === "en2zh_pdf_to_word" ? "en" : "auto",
      debug_full_text: false,
    };
    if (isAdmin.value) {
      if (selectedTemplateOption.value) {
        payload.template_version_id = configVersionId(selectedTemplateOption.value);
      }
      if (selectedTermRuleOption.value) {
        payload.term_rule_set_id = selectedTermRuleOption.value.resource_id;
        payload.term_rule_set_version = selectedTermRuleOption.value.version;
      }
      if (mode.value === "en2zh_pdf_to_word" && selectedTranslationTermOption.value) {
        payload.translation_term_set_id = selectedTranslationTermOption.value.resource_id;
        payload.translation_term_version = selectedTranslationTermOption.value.version;
      }
      if (mode.value === "en2zh_pdf_to_word" && selectedTranslationProfileOption.value) {
        payload.translation_profile_id = selectedTranslationProfileOption.value.resource_id;
        payload.translation_profile_version = selectedTranslationProfileOption.value.version;
      }
    }
    const response = await documentJobsApi.create(payload);

    ElMessage.success("任务已创建。");
    uploadRef.value?.clearFiles();
    selectedFile.value = null;
    createStep.value = "done";
    statusText.value = "任务创建成功。";
    emit("created", response.job_id);
  } catch (caught) {
    error.value = normalizeApiError(caught);
    createStep.value = "failed";
    statusText.value = "创建任务失败。";
  } finally {
    submitting.value = false;
  }
}

watch(mode, (nextMode) => {
  if (nextMode === "direct_pdf_to_word") {
    selectedTranslationTermVersion.value = "";
    selectedTranslationProfileVersion.value = "";
  }
});

onMounted(() => {
  void loadConfigSummary();
});
</script>

<style scoped lang="scss">
.upload-card {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
}

.upload-card :deep(.el-card__body) {
  padding: 20px;
}

.upload-card :deep(.el-upload-dragger) {
  border-color: #d9e2ec;
  border-radius: 8px;
  background: #f8fafc;
  transition:
    border-color 180ms ease-out,
    box-shadow 180ms ease-out,
    background-color 180ms ease-out;
}

.upload-card :deep(.el-upload-dragger:hover) {
  border-color: #93c5fd;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.12);
}

.upload-card :deep(.el-icon--upload) {
  color: #2563eb;
}

.upload-steps {
  margin: 12px 0 18px;
}

.upload-card :deep(.el-button),
.upload-card :deep(.el-select__wrapper),
.upload-card :deep(.el-input__wrapper) {
  border-radius: 8px;
}

.upload-card :deep(.el-button--primary) {
  border-color: #2563eb;
  background: #2563eb;
}

.mode-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}

.mode-label {
  color: #344054;
  font-size: 14px;
}

.config-panel {
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #f8fafc;
}

.config-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.config-panel-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.config-panel-header strong,
.config-panel-header small,
.config-summary-item span,
.config-summary-item b,
.admin-config label span {
  display: block;
}

.config-panel-header strong {
  color: #111827;
  font-size: 14px;
}

.config-panel-header small,
.config-summary-item span,
.admin-config label span {
  color: #667085;
  font-size: 12px;
}

.config-summary-grid,
.admin-config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.config-summary-item {
  min-height: 62px;
  padding: 10px;
  border: 1px solid #edf0f3;
  border-radius: 8px;
  background: #fff;
}

.config-summary-item b {
  margin-top: 6px;
  color: #111827;
  font-size: 13px;
  word-break: break-all;
}

.config-warning {
  margin-top: 0;
}

.config-blocker-list {
  margin: 4px 0 0;
  padding-left: 18px;
}

.admin-config :deep(.el-divider--horizontal) {
  margin: 2px 0 12px;
}

.admin-config label {
  display: grid;
  gap: 6px;
}

.upload-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
}

@media (max-width: 720px) {
  .upload-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .config-summary-grid,
  .admin-config-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-color-scheme: dark) {
  .upload-card {
    border-color: rgba(148, 163, 184, 0.2);
    background: rgba(10, 16, 32, 0.9);
    box-shadow: 0 16px 42px rgba(0, 0, 0, 0.26);
  }

  .config-panel,
  .upload-card :deep(.el-upload-dragger) {
    border-color: rgba(148, 163, 184, 0.2);
    background: rgba(15, 23, 42, 0.66);
  }

  .config-summary-item {
    border-color: rgba(148, 163, 184, 0.16);
    background: rgba(15, 23, 42, 0.72);
  }

  .config-panel-header strong,
  .config-summary-item b {
    color: #f8fafc;
  }

  .config-panel-header small,
  .config-summary-item span,
  .admin-config label span,
  .mode-label {
    color: #aab6ca;
  }
}
</style>
