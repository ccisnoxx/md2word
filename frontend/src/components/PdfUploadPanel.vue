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
        <el-radio-button label="en2zh_pdf_to_word">英译中实验</el-radio-button>
      </el-radio-group>
    </div>

    <section v-if="isAdmin" class="term-assets-panel" aria-label="术语资产版本选择">
      <div class="mode-label">术语资产版本</div>
      <el-select v-model="termRuleSetId" clearable filterable placeholder="默认 Term Rule Set" @change="handleTermRuleSetChange">
        <el-option v-for="set in termRuleSets" :key="set.id" :label="set.id" :value="set.id" />
      </el-select>
      <el-select v-model="termRuleSetVersion" clearable filterable placeholder="默认或 published 历史版本">
        <el-option
          v-for="version in selectedTermRuleVersions"
          :key="version.version"
          :label="`${version.version}${version.is_default ? '（默认）' : ''}`"
          :value="version.version"
        />
      </el-select>
      <el-input v-model="translationTermSetId" placeholder="Translation Term Set，默认 translation-terms-en2zh" />
      <el-input v-model="translationTermVersion" placeholder="Translation Term Version，例如 v1" />
    </section>

    <div class="upload-footer">
      <div class="muted">{{ statusText }}</div>
      <el-button type="primary" :icon="Upload" :loading="submitting" :disabled="!selectedFile" @click="submit">
        创建任务
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, type UploadFile, type UploadInstance, type UploadRawFile } from "element-plus";
import { Upload, UploadFilled } from "@element-plus/icons-vue";

import type { DocumentJobMode, TermRuleSetDetailResponse, TermRuleSetListItemResponse } from "@/api/types";
import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import { termRuleSetsApi } from "@/api/termRuleSets";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { useAuthStore } from "@/stores/auth";
import { getMaxUploadBytes, uploadFileContent, validatePdfFile } from "@/utils/upload";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

const emit = defineEmits<{
  created: [jobId: string];
}>();

const auth = useAuthStore();
const uploadRef = ref<UploadInstance>();
const selectedFile = ref<File | null>(null);
const submitting = ref(false);
const statusText = ref("等待选择 PDF。");
const error = ref<ApiClientError | null>(null);
const mode = ref<DocumentJobMode>("direct_pdf_to_word");
const enableEn2zh = import.meta.env.VITE_ENABLE_EN2ZH === "true";
const maxUploadMb = computed(() => Math.round(getMaxUploadBytes() / 1024 / 1024));
const isAdmin = computed(() => auth.user?.role === "admin");
const termRuleSets = ref<TermRuleSetListItemResponse[]>([]);
const termRuleSetDetails = ref<Record<string, TermRuleSetDetailResponse>>({});
const termRuleSetId = ref("");
const termRuleSetVersion = ref("");
const translationTermSetId = ref("");
const translationTermVersion = ref("");
const selectedTermRuleVersions = computed(() => {
  const selected = termRuleSetId.value || termRuleSets.value[0]?.id || "";
  return termRuleSetDetails.value[selected]?.versions || [];
});

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
  statusText.value = `已选择 ${rawFile.name}。`;
}

function handleFileRemove(): void {
  selectedFile.value = null;
  statusText.value = "等待选择 PDF。";
}

function handleExceed(): void {
  ElMessage.warning("MVP 只支持单文件上传。");
}

async function loadTermRuleSets(): Promise<void> {
  if (!isAdmin.value) {
    return;
  }
  try {
    const response = await termRuleSetsApi.list();
    termRuleSets.value = response.items;
    await Promise.all(response.items.map((item) => loadTermRuleSetDetail(item.id)));
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function loadTermRuleSetDetail(setId: string): Promise<void> {
  if (!setId || termRuleSetDetails.value[setId]) {
    return;
  }
  termRuleSetDetails.value[setId] = await termRuleSetsApi.get(setId);
}

async function handleTermRuleSetChange(): Promise<void> {
  termRuleSetVersion.value = "";
  try {
    await loadTermRuleSetDetail(termRuleSetId.value);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function submit(): Promise<void> {
  if (!selectedFile.value || submitting.value) {
    return;
  }

  submitting.value = true;
  error.value = null;

  try {
    statusText.value = "正在获取上传授权。";
    const authorization = await filesApi.createUploadUrl({
      filename: selectedFile.value.name,
      mime_type: selectedFile.value.type || "application/pdf",
      size_bytes: selectedFile.value.size,
      file_type: "source_pdf",
    });

    statusText.value = "正在上传 PDF 内容。";
    await uploadFileContent(authorization, selectedFile.value, auth.token);

    statusText.value = "正在创建转换任务。";
    const response = await documentJobsApi.create({
      source_file_id: authorization.file_id,
      mode: mode.value,
      document_language: mode.value === "en2zh_pdf_to_word" ? "en" : "auto",
      term_rule_set_id: isAdmin.value ? termRuleSetId.value || null : null,
      term_rule_set_version: isAdmin.value ? termRuleSetVersion.value || null : null,
      translation_term_set_id: isAdmin.value ? translationTermSetId.value || null : null,
      translation_term_version: isAdmin.value ? translationTermVersion.value || null : null,
      debug_full_text: false,
    });

    ElMessage.success("任务已创建。");
    uploadRef.value?.clearFiles();
    selectedFile.value = null;
    statusText.value = "任务创建成功。";
    emit("created", response.job_id);
  } catch (caught) {
    error.value = normalizeApiError(caught);
    statusText.value = "创建任务失败。";
  } finally {
    submitting.value = false;
  }
}

onMounted(() => {
  void loadTermRuleSets();
});
</script>

<style scoped lang="scss">
.upload-card {
  border: 1px solid #d9e2ec;
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

.term-assets-panel {
  display: grid;
  gap: 10px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #d9e2ec;
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
}
</style>
