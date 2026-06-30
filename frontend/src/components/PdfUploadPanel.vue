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

    <div class="mode-row">
      <span class="mode-label">任务模式</span>
      <el-radio-group v-model="mode" size="small">
        <el-radio-button
          v-for="option in selectableModeOptions"
          :key="option.mode"
          :label="option.mode"
          :disabled="option.disabled"
        >
          {{ option.shortLabel }}
        </el-radio-button>
      </el-radio-group>
    </div>
    <el-alert
      v-if="modeReadinessHint"
      class="mode-readiness"
      type="warning"
      :closable="false"
      show-icon
      :title="modeReadinessHint"
    />

    <div class="config-panel" v-loading="configLoading">
      <div class="config-panel-header">
        <div>
          <strong>任务配置</strong>
          <small>默认使用当前 published 版本，也可为本次任务指定已发布配置。</small>
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

      <div class="config-selection">
        <el-divider />
        <div class="config-selection-grid">
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
          <label v-if="selectedModeRequiresTranslationResources">
            <span>翻译术语集</span>
            <el-select v-model="selectedTranslationTermVersion" clearable filterable placeholder="使用默认翻译术语">
              <el-option
                v-for="option in filteredTranslationTermOptions"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </label>
          <label v-if="selectedModeRequiresTranslationResources">
            <span>翻译配置</span>
            <el-select v-model="selectedTranslationProfileVersion" clearable filterable placeholder="使用默认翻译配置">
              <el-option
                v-for="option in filteredTranslationProfileOptions"
                :key="configOptionKey(option)"
                :label="option.label"
                :value="configOptionKey(option)"
              />
            </el-select>
          </label>
          <label v-if="isAdmin && selectedModeRequiresTranslationResources" class="switch-row">
            <span>全文调试归档</span>
            <el-switch v-model="debugFullText" active-text="开启" inactive-text="关闭" />
            <small>仅 P1 复核样本使用；归档会按后端保留期过期。</small>
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
import { translationResourceDefaultsForMode } from "@/utils/documentJobConfig";
import {
  documentJobModeDefinitions,
  documentJobModeCreateLanguage,
  documentJobModeOptions,
  documentJobModeRequiresTranslationResources,
  documentJobModeTranslationMode,
} from "@/utils/format";

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
const debugFullText = ref(false);
const maxUploadMb = computed(() => Math.round(getMaxUploadBytes() / 1024 / 1024));
const isAdmin = computed(() => auth.user?.role === "admin");
const configWarnings = computed(() => (configSummary.value?.readiness.warnings || []).map(readinessCodeText));
const selectedTranslationMode = computed(() => documentJobModeTranslationMode(mode.value));
const p0ReadinessBlockers = computed(() => configSummary.value?.readiness.blockers || []);
const p0ExecutionBlocked = computed(() => Boolean(
  configSummary.value?.readiness.p0_document_jobs_required
  && !configSummary.value?.readiness.p0_document_jobs_ready,
));
const p0ReadinessMessages = computed(() => (
  (p0ReadinessBlockers.value.length > 0 ? p0ReadinessBlockers.value : ["p0_document_jobs_not_ready"]).map(readinessCodeText)
));
const configUnavailable = computed(() => Boolean(configError.value || !configSummary.value));
const selectableModeOptions = computed(() => documentJobModeOptions.map((option) => ({
  ...option,
  disabled: documentJobModeRequiresTranslationResources(option.mode) && !isTranslationModeAvailable(documentJobModeTranslationMode(option.mode)),
})));
const firstUnavailableModeOption = computed(() =>
  selectableModeOptions.value.find((option) => option.disabled),
);
const selectedModeRequiresTranslationResources = computed(() => documentJobModeRequiresTranslationResources(mode.value));
const selectedModeDisabled = computed(() =>
  selectedModeRequiresTranslationResources.value && !isTranslationModeAvailable(selectedTranslationMode.value),
);
const createDisabled = computed(() => (
  !selectedFile.value || configLoading.value || configUnavailable.value || p0ExecutionBlocked.value || selectedModeDisabled.value
));
const modeReadinessHint = computed(() => {
  if (!configSummary.value) {
    return "";
  }
  const unavailableMode = selectedModeDisabled.value
    ? mode.value
    : firstUnavailableModeOption.value?.mode;
  return unavailableMode
    ? `${documentJobModeDefinitions[unavailableMode].shortLabel} 需要默认翻译术语集和翻译配置发布后才能选择。`
    : "";
});
const selectedTranslationDefaults = computed(() =>
  translationResourceDefaultsForMode(configSummary.value, selectedTranslationMode.value),
);
const defaultConfigItems = computed(() => {
  const defaults = configSummary.value?.defaults;
  const items = [
    { key: "template", label: "模板", value: defaults?.template?.label || "未配置" },
    { key: "term-rule-set", label: "术语规则集", value: defaults?.term_rule_set?.label || "未配置" },
  ];
  if (selectedModeRequiresTranslationResources.value) {
    items.push(
      {
        key: "translation-term-set",
        label: "翻译术语集",
        value: selectedTranslationDefaults.value?.translation_term_set?.label || "未配置",
      },
      {
        key: "translation-profile",
        label: "翻译配置",
        value: selectedTranslationDefaults.value?.translation_profile?.label || "未配置",
      },
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
  findConfigOption(filteredTranslationTermOptions.value, selectedTranslationTermVersion.value),
);
const selectedTranslationProfileOption = computed(() =>
  findConfigOption(filteredTranslationProfileOptions.value, selectedTranslationProfileVersion.value),
);

const filteredTranslationTermOptions = computed(() =>
  filterConfigOptionsByLanguagePair(configSummary.value?.options.translation_term_sets || [], selectedTranslationMode.value),
);
const filteredTranslationProfileOptions = computed(() =>
  filterConfigOptionsByLanguagePair(configSummary.value?.options.translation_profiles || [], selectedTranslationMode.value),
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
  if (
    !selectedFile.value
    || submitting.value
    || configLoading.value
    || configUnavailable.value
    || p0ExecutionBlocked.value
    || selectedModeDisabled.value
  ) {
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
      translation_mode: selectedTranslationMode.value,
      document_language: documentJobModeCreateLanguage(mode.value),
      debug_full_text: isAdmin.value && selectedModeRequiresTranslationResources.value && debugFullText.value,
    };
    if (selectedTemplateOption.value) {
      payload.template_version_id = configVersionId(selectedTemplateOption.value);
    }
    if (selectedTermRuleOption.value) {
      payload.term_rule_set_id = selectedTermRuleOption.value.resource_id;
      payload.term_rule_set_version = selectedTermRuleOption.value.version;
    }
    if (selectedModeRequiresTranslationResources.value && selectedTranslationTermOption.value) {
      payload.translation_term_set_id = selectedTranslationTermOption.value.resource_id;
      payload.translation_term_version = selectedTranslationTermOption.value.version;
    }
    if (selectedModeRequiresTranslationResources.value && selectedTranslationProfileOption.value) {
      payload.translation_profile_id = selectedTranslationProfileOption.value.resource_id;
      payload.translation_profile_version = selectedTranslationProfileOption.value.version;
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
  if (!documentJobModeRequiresTranslationResources(nextMode)) {
    selectedTranslationTermVersion.value = "";
    selectedTranslationProfileVersion.value = "";
    debugFullText.value = false;
    return;
  }
  selectedTranslationTermVersion.value = "";
  selectedTranslationProfileVersion.value = "";
});

watch(selectedModeDisabled, (disabled) => {
  if (disabled) {
    mode.value = "direct_pdf_to_word";
  }
});

onMounted(() => {
  void loadConfigSummary();
});

function isTranslationModeAvailable(translationMode: string): boolean {
  if (translationMode === "direct") {
    return true;
  }
  const readiness = configSummary.value?.readiness;
  if (!readiness) {
    return false;
  }
  return readiness.translation_modes?.[translationMode] ?? (
    translationMode === "en2zh" ? readiness.en2zh_available : readiness.ru2zh_available
  );
}

function filterConfigOptionsByLanguagePair<T extends { summary?: Record<string, unknown> }>(
  options: T[],
  languagePair: string,
): T[] {
  if (languagePair === "direct") {
    return options;
  }
  return options.filter((option) => {
    const optionLanguagePair = option.summary?.language_pair;
    return typeof optionLanguagePair !== "string" || optionLanguagePair === languagePair;
  });
}
</script>

<style scoped lang="scss">
.upload-card {
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background: linear-gradient(180deg, var(--app-color-surface), var(--app-color-surface-muted));
  box-shadow: var(--app-shadow-panel);
}

.upload-card :deep(.el-card__body) {
  padding: var(--app-space-5);
}

.upload-card :deep(.el-upload-dragger) {
  border-color: var(--app-color-primary-border);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(180deg, var(--app-color-primary-soft), var(--app-color-surface));
  background-size:
    28px 28px,
    28px 28px,
    auto;
  transition:
    border-color 180ms ease-out,
    box-shadow 180ms ease-out,
    background-color 180ms ease-out;
}

.upload-card :deep(.el-upload-dragger:hover) {
  border-color: var(--app-color-primary);
  background:
    linear-gradient(var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--app-color-grid-line) 1px, transparent 1px),
    linear-gradient(180deg, var(--app-color-accent-cyan-soft), var(--app-color-surface));
  background-size:
    28px 28px,
    28px 28px,
    auto;
  box-shadow: var(--app-shadow-focus);
}

.upload-card :deep(.el-icon--upload) {
  color: var(--app-color-primary);
}

.upload-steps {
  margin: 12px 0 18px;
}

.upload-card :deep(.el-button),
.upload-card :deep(.el-select__wrapper),
.upload-card :deep(.el-input__wrapper) {
  border-radius: var(--app-radius-md);
}

.upload-card :deep(.el-button--primary) {
  border-color: var(--app-color-primary);
  background: linear-gradient(135deg, var(--app-color-primary), var(--app-color-primary-hover) 72%, var(--app-color-accent-cyan));
  box-shadow: 0 8px 18px color-mix(in srgb, var(--app-color-primary) 22%, transparent);
}

.mode-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: 14px;
}

.mode-label {
  color: var(--app-color-text-muted);
  font-size: 14px;
}

.mode-readiness {
  margin-top: 10px;
}

.config-panel {
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding: 12px;
  border: 1px solid var(--app-color-accent-cyan-border);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(90deg, var(--app-color-primary-soft), transparent),
    var(--app-color-surface-muted);
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
.config-selection label span {
  display: block;
}

.config-panel-header strong {
  color: var(--app-color-text);
  font-size: 14px;
}

.config-panel-header small,
.config-summary-item span,
.config-selection label span {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.config-summary-grid,
.config-selection-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.config-summary-item {
  min-height: 62px;
  padding: 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: linear-gradient(180deg, var(--app-color-glass-strong), var(--app-color-surface-muted));
}

.config-summary-item b {
  margin-top: 6px;
  color: var(--app-color-text);
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

.config-selection :deep(.el-divider--horizontal) {
  margin: 2px 0 12px;
}

.config-selection label {
  display: grid;
  gap: 6px;
}

.switch-row small {
  color: var(--app-color-text-muted);
  font-size: 12px;
  line-height: 1.4;
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
  .config-selection-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-color-scheme: dark) {
  .upload-card {
    border-color: var(--app-color-border);
    background: var(--app-color-surface);
    box-shadow: var(--app-shadow-panel);
  }

  .config-panel,
  .upload-card :deep(.el-upload-dragger) {
    border-color: var(--app-color-border);
    background: var(--app-color-surface-muted);
  }

  .config-summary-item {
    border-color: var(--app-color-border-soft);
    background: var(--app-color-surface);
  }

  .config-panel-header strong,
  .config-summary-item b {
    color: var(--app-color-text);
  }

  .config-panel-header small,
  .config-summary-item span,
  .config-selection label span,
  .switch-row small,
  .mode-label {
    color: var(--app-color-text-muted);
  }
}
</style>
