<!-- 文件：frontend/src/components/PdfUploadPanel.vue；用途：两栏渐进式授权、上传 PDF 并创建单个文档任务。 -->
<template>
  <el-card class="upload-card card-flat" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">上传 PDF 创建任务</h2>
        <p class="section-subtitle">默认创建原文 PDF 转可编辑 Word 任务。</p>
      </div>
      <el-tag type="info" effect="plain">单文件</el-tag>
    </div>

    <ApiErrorAlert :error="error" />

    <div class="upload-workbench-grid">
      <section class="upload-primary-pane" aria-label="上传与任务参数">
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

        <div v-if="selectedFile" class="selected-file-strip" role="status">
          <div class="selected-file-meta">
            <strong :title="selectedFile.name">{{ selectedFile.name }}</strong>
            <small>{{ formatBytes(selectedFile.size) }}</small>
          </div>
          <el-button link size="small" :disabled="submitting" @click="clearSelectedFile">清除</el-button>
        </div>

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
        <p v-if="!selectedModeRequiresTranslationResources" class="section-subtitle mode-caption">
          保持原文语言和语义，不调用 AI。
        </p>

        <div v-if="!selectedModeRequiresTranslationResources" class="language-row">
          <div class="language-row-header">
            <span class="mode-label">原文语言</span>
            <small class="language-hint">{{ selectedLanguageHint }}</small>
          </div>
          <el-radio-group v-model="directDocumentLanguage" size="small" aria-label="原文语言">
            <el-radio-button
              v-for="option in documentLanguageOptions"
              :key="option.value"
              :label="option.value"
            >
              {{ option.label }}
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

        <div class="upload-footer">
          <div class="muted">{{ statusText }}</div>
          <el-button type="primary" :icon="Upload" :loading="submitting" :disabled="createDisabled" @click="submit">
            创建任务
          </el-button>
        </div>
      </section>

      <aside class="config-panel" v-loading="configLoading" aria-label="任务配置与门禁">
        <div class="config-panel-header">
          <div>
            <strong>任务配置</strong>
            <small>默认使用当前 published 版本，可在下方按需覆盖已发布配置。</small>
          </div>
          <div class="config-panel-actions">
            <el-tag size="small" effect="plain">{{ configSummary?.resource_mode || "unknown" }}</el-tag>
            <el-button link size="small" :loading="configLoading" @click="loadConfigSummary">重新加载</el-button>
          </div>
        </div>

        <ApiErrorAlert :error="configError" />

        <div class="config-summary-grid">
          <div v-for="item in effectiveConfigItems" :key="item.key" class="config-summary-item">
            <div class="config-summary-item-head">
              <span>{{ item.label }}</span>
              <el-tag v-if="item.overridden" size="small" type="warning" effect="plain">已覆盖</el-tag>
            </div>
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

        <div class="config-advanced-shell">
          <button
            type="button"
            class="config-advanced-toggle"
            :aria-expanded="advancedConfigOpen"
            aria-controls="pdf-upload-advanced-config"
            @click="advancedConfigOpen = !advancedConfigOpen"
          >
            <span class="config-advanced-toggle-copy">
              <el-icon class="config-advanced-chevron" :class="{ 'is-open': advancedConfigOpen }">
                <ArrowRight />
              </el-icon>
              <strong>高级：覆盖已发布版本</strong>
            </span>
            <span class="config-advanced-toggle-meta">
              <el-tag v-if="customOverrideCount > 0" size="small" type="warning" effect="plain">
                已自定义 {{ customOverrideCount }} 项
              </el-tag>
              <small v-else>{{ advancedConfigOpen ? "收起" : "展开" }}</small>
            </span>
          </button>

          <div
            v-show="advancedConfigOpen"
            id="pdf-upload-advanced-config"
            class="config-selection"
          >
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
                <span>符号与排版规则</span>
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
      </aside>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, type UploadFile, type UploadInstance, type UploadRawFile } from "element-plus";
import { ArrowRight, Upload, UploadFilled } from "@element-plus/icons-vue";

import type {
  DocumentJobConfigSummaryResponse,
  DocumentJobCreateRequest,
  DocumentJobMode,
  DocumentLanguage,
} from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { useAuthStore } from "@/stores/auth";
import { getMaxUploadBytes, uploadFileContent, validatePdfFile } from "@/utils/upload";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { LEGACY_DEFAULT_TEMPLATE_WARNING, readinessCodeText } from "@/utils/displayText";
import { configOptionKey, configVersionId, findConfigOption } from "@/utils/configOptions";
import {
  documentJobConfigWarningsForMode,
  isTranslationModeAvailable,
  translationResourceDefaultsForMode,
} from "@/utils/documentJobConfig";
import {
  documentJobModeDefinitions,
  documentJobModeCreateLanguage,
  documentJobModeOptions,
  documentJobModeRequiresTranslationResources,
  documentJobModeTranslationMode,
  documentLanguageMineruHint,
  documentLanguageOptions,
  formatBytes,
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
const directDocumentLanguage = ref<DocumentLanguage>("auto");
const advancedConfigOpen = ref(false);
const selectedTemplateVersion = ref("");
const selectedTermRuleVersion = ref("");
const selectedTranslationTermVersion = ref("");
const selectedTranslationProfileVersion = ref("");
const debugFullText = ref(false);
const maxUploadMb = computed(() => Math.round(getMaxUploadBytes() / 1024 / 1024));
const isAdmin = computed(() => auth.user?.role === "admin");
const configWarnings = computed(() => documentJobConfigWarningsForMode(configSummary.value, mode.value).map(readinessCodeText));
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
  disabled: documentJobModeRequiresTranslationResources(option.mode)
    && !isTranslationModeAvailable(configSummary.value, documentJobModeTranslationMode(option.mode)),
})));
const firstUnavailableModeOption = computed(() =>
  selectableModeOptions.value.find((option) => option.disabled),
);
const selectedModeRequiresTranslationResources = computed(() => documentJobModeRequiresTranslationResources(mode.value));
const selectedLanguageHint = computed(() => documentLanguageMineruHint(directDocumentLanguage.value));
const selectedModeDisabled = computed(() =>
  selectedModeRequiresTranslationResources.value
  && !isTranslationModeAvailable(configSummary.value, selectedTranslationMode.value),
);
const modeReadinessHint = computed(() => {
  if (!configSummary.value) {
    return "";
  }
  const unavailableMode = selectedModeDisabled.value
    ? mode.value
    : firstUnavailableModeOption.value?.mode;
  return unavailableMode
    ? selectedModeRequiresTranslationResources.value
      ? `${documentJobModeDefinitions[unavailableMode].shortLabel} 需要默认翻译术语集和翻译配置发布后才能选择。`
      : `${documentJobModeDefinitions[unavailableMode].shortLabel}未就绪。`
    : "";
});
const selectedTranslationDefaults = computed(() =>
  translationResourceDefaultsForMode(configSummary.value, selectedTranslationMode.value),
);
const selectedTemplateOption = computed(() =>
  findConfigOption(configSummary.value?.options.templates || [], selectedTemplateVersion.value),
);
const templateUnavailable = computed(() => (
  !selectedTemplateOption.value && configSummary.value?.readiness.warnings.includes(LEGACY_DEFAULT_TEMPLATE_WARNING)
));
const configurationBlocksCreate = computed(() => (
  configLoading.value || configUnavailable.value || p0ExecutionBlocked.value || selectedModeDisabled.value || templateUnavailable.value
));
const createDisabled = computed(() => !selectedFile.value || configurationBlocksCreate.value);
const selectedTermRuleOption = computed(() =>
  findConfigOption(configSummary.value?.options.term_rule_sets || [], selectedTermRuleVersion.value),
);
const filteredTranslationTermOptions = computed(() =>
  filterConfigOptionsByLanguagePair(configSummary.value?.options.translation_term_sets || [], selectedTranslationMode.value),
);
const filteredTranslationProfileOptions = computed(() =>
  filterConfigOptionsByLanguagePair(configSummary.value?.options.translation_profiles || [], selectedTranslationMode.value),
);
const selectedTranslationTermOption = computed(() =>
  findConfigOption(filteredTranslationTermOptions.value, selectedTranslationTermVersion.value),
);
const selectedTranslationProfileOption = computed(() =>
  findConfigOption(filteredTranslationProfileOptions.value, selectedTranslationProfileVersion.value),
);
const effectiveConfigItems = computed(() => {
  const defaults = configSummary.value?.defaults;
  const items = [
    {
      key: "template",
      label: "模板",
      value: selectedTemplateOption.value?.label || defaults?.template?.label || "未配置",
      overridden: Boolean(selectedTemplateOption.value),
    },
    {
      key: "term-rule-set",
      label: "符号与排版规则",
      value: selectedTermRuleOption.value?.label || defaults?.term_rule_set?.label || "未配置",
      overridden: Boolean(selectedTermRuleOption.value),
    },
  ];
  if (selectedModeRequiresTranslationResources.value) {
    items.push(
      {
        key: "translation-term-set",
        label: "翻译术语集",
        value: selectedTranslationTermOption.value?.label || selectedTranslationDefaults.value?.translation_term_set?.label || "未配置",
        overridden: Boolean(selectedTranslationTermOption.value),
      },
      {
        key: "translation-profile",
        label: "翻译配置",
        value: selectedTranslationProfileOption.value?.label || selectedTranslationDefaults.value?.translation_profile?.label || "未配置",
        overridden: Boolean(selectedTranslationProfileOption.value),
      },
    );
  }
  return items;
});
const customOverrideCount = computed(() => {
  let count = 0;
  if (selectedTemplateOption.value) {
    count += 1;
  }
  if (selectedTermRuleOption.value) {
    count += 1;
  }
  if (selectedModeRequiresTranslationResources.value) {
    if (selectedTranslationTermOption.value) {
      count += 1;
    }
    if (selectedTranslationProfileOption.value) {
      count += 1;
    }
    if (isAdmin.value && debugFullText.value) {
      count += 1;
    }
  }
  return count;
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

function clearSelectedFile(): void {
  uploadRef.value?.clearFiles();
  handleFileRemove();
}

function handleExceed(): void {
  ElMessage.warning("当前仅支持单文件上传。");
}

async function submit(): Promise<void> {
  if (!selectedFile.value || submitting.value || configurationBlocksCreate.value) {
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
      document_language: selectedModeRequiresTranslationResources.value
        ? documentJobModeCreateLanguage(mode.value)
        : directDocumentLanguage.value,
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
    directDocumentLanguage.value = "auto";
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

watch(templateUnavailable, (unavailable) => {
  // 默认模板受限时自动展开覆盖区，降低用户寻找替代模板的成本。
  if (unavailable) {
    advancedConfigOpen.value = true;
  }
});

onMounted(() => {
  void loadConfigSummary();
});

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
  box-shadow: var(--app-shadow-subtle);
}

.upload-card :deep(.el-card__body) {
  padding: var(--app-space-5);
}

.upload-workbench-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 1fr);
  gap: var(--app-space-5);
  align-items: start;
  margin-top: var(--app-space-3);
}

.upload-primary-pane {
  min-width: 0;
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
  margin: 0 0 16px;
}

.selected-file-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--app-space-3);
  margin-top: var(--app-space-3);
  padding: 10px 12px;
  border: 1px solid var(--app-color-primary-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-primary-soft);
}

.selected-file-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.selected-file-meta strong {
  color: var(--app-color-text);
  font-size: 13px;
  overflow-wrap: anywhere;
}

.selected-file-meta small {
  color: var(--app-color-text-muted);
  font-size: 12px;
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
  gap: 10px;
  margin-top: 16px;
}

.mode-row :deep(.el-radio-group),
.language-row :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  row-gap: 6px;
  max-width: 100%;
}

.mode-caption {
  margin: 8px 0 0;
}

.language-row {
  display: grid;
  gap: 8px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--app-color-border-soft);
}

.language-row-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.language-hint {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.mode-label {
  color: var(--app-color-text-muted);
  font-size: 14px;
  font-weight: 600;
}

.mode-readiness {
  margin-top: 12px;
}

.config-panel {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 14px;
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

.config-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.config-selection-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.config-summary-item {
  min-height: 62px;
  padding: 10px;
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: linear-gradient(180deg, var(--app-color-glass-strong), var(--app-color-surface-muted));
}

.config-summary-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
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

.config-advanced-shell {
  border-top: 1px solid var(--app-color-border-soft);
  padding-top: 10px;
}

.config-advanced-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: var(--app-radius-sm);
  background: transparent;
  color: var(--app-color-text);
  font: inherit;
  cursor: pointer;
  text-align: left;
  transition: background-color var(--app-motion-fast) var(--app-ease-out);
}

.config-advanced-toggle:hover {
  background: var(--app-color-surface);
  border-color: var(--app-color-border-soft);
}

.config-advanced-toggle:focus-visible {
  outline: 2px solid var(--app-color-primary);
  outline-offset: 2px;
}

.config-advanced-toggle-copy {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.config-advanced-toggle-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.config-advanced-chevron {
  transition: transform var(--app-motion-fast) var(--app-ease-out);
}

.config-advanced-chevron.is-open {
  transform: rotate(90deg);
}

.config-selection :deep(.el-divider--horizontal) {
  margin: 8px 0 12px;
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
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--app-color-border-soft);
}

@media (max-width: 960px) {
  .upload-workbench-grid {
    grid-template-columns: 1fr;
  }

  .config-selection-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
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
    box-shadow: var(--app-shadow-subtle);
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
