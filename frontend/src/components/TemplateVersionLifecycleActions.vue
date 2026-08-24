<!-- 统一承载 Template Version 的验证、发布、设默认和管理动作。 -->
<template>
  <div class="template-version-actions app-action-row" :aria-label="`模板版本 ${version.version} 操作`">
    <el-tag v-if="version.is_default" type="success" effect="plain">当前默认</el-tag>
    <el-button v-if="canValidate" link type="primary" @click="openValidationDialog">创建验证任务</el-button>
    <el-button v-if="version.status === 'draft'" link type="success" @click="openPublishDialog">发布</el-button>
    <el-button v-if="version.status === 'published' && !version.is_default" link type="warning" @click="openDefaultDialog">
      设为默认
    </el-button>
    <el-button v-if="canDisable" link type="danger" @click="disableVersion">禁用</el-button>
  </div>

  <el-dialog v-model="validationDialog.visible" title="创建模板验证任务" width="560px">
    <p class="dialog-note">
      将用 <span class="mono">{{ templateVersionId }}</span> 创建 document job。
    </p>
    <el-upload
      ref="validationUploadRef"
      action=""
      accept=".pdf,application/pdf"
      :auto-upload="false"
      :limit="1"
      :on-change="handleValidationFileChange"
      :on-remove="handleValidationFileRemove"
    >
      <el-button :icon="Upload">选择验证 PDF</el-button>
      <template #tip>
        <div class="el-upload__tip">已选择：{{ validationDialog.file?.name || "无" }}</div>
      </template>
    </el-upload>
    <el-radio-group v-model="validationDialog.mode" class="form-gap validation-mode-options">
      <el-radio-button
        v-for="option in documentJobModeOptions"
        :key="option.mode"
        :value="option.mode"
      >
        {{ option.shortLabel }}
      </el-radio-button>
    </el-radio-group>
    <template #footer>
      <el-button @click="validationDialog.visible = false">取消</el-button>
      <el-button
        type="primary"
        :loading="validationDialog.submitting"
        :disabled="!validationDialog.file"
        @click="createValidationJob"
      >
        创建任务
      </el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="publishDialog.visible" title="发布模板版本" width="560px">
    <el-alert
      title="只有状态为 succeeded 且绑定当前版本的验证任务才能发布。"
      type="info"
      show-icon
      :closable="false"
      class="publish-requirement"
    />
    <el-form ref="publishFormRef" :model="publishDialog.form" :rules="publishRules" label-width="118px">
      <el-form-item label="验证任务 ID" prop="verification_job_id">
        <el-input v-model="publishDialog.form.verification_job_id" />
      </el-form-item>
      <el-form-item label="验证说明" prop="verification_note">
        <el-input v-model="publishDialog.form.verification_note" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="发布原因" prop="publish_reason">
        <el-input v-model="publishDialog.form.publish_reason" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="publishDialog.visible = false">取消</el-button>
      <el-button type="primary" :loading="publishDialog.submitting" @click="publishVersion">发布</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="defaultDialog.visible" title="设为默认模板版本" width="520px">
    <el-form ref="defaultFormRef" :model="defaultDialog.form" :rules="defaultRules" label-width="100px">
      <el-form-item label="切换原因" prop="set_default_reason">
        <el-input v-model="defaultDialog.form.set_default_reason" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="defaultDialog.visible = false">取消</el-button>
      <el-button type="warning" :loading="defaultDialog.submitting" @click="setDefaultVersion">设为默认</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadFile, type UploadInstance, type UploadRawFile } from "element-plus";
import { Upload } from "@element-plus/icons-vue";

import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import { templatesApi } from "@/api/templates";
import type { DocumentJobMode, TemplateVersionResponse } from "@/api/types";
import { useAuthStore } from "@/stores/auth";
import {
  documentJobModeCreateLanguage,
  documentJobModeOptions,
  documentJobModeTranslationMode,
} from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { uploadFileContent, validatePdfFile } from "@/utils/upload";

const props = withDefaults(defineProps<{
  templateId: string;
  version: TemplateVersionResponse;
  management?: boolean;
  autoOpenValidation?: boolean;
}>(), {
  management: false,
  autoOpenValidation: false,
});

const emit = defineEmits<{
  changed: [version: TemplateVersionResponse];
  failed: [error: ApiClientError];
}>();

const auth = useAuthStore();
const validationUploadRef = ref<UploadInstance>();
const publishFormRef = ref<FormInstance>();
const defaultFormRef = ref<FormInstance>();
const createdVerificationJobId = ref("");
const validationDialog = reactive({
  visible: false,
  file: null as File | null,
  mode: "direct_pdf_to_word" as DocumentJobMode,
  submitting: false,
});
const publishDialog = reactive({
  visible: false,
  submitting: false,
  form: {
    verification_job_id: "",
    verification_note: "",
    publish_reason: "",
  },
});
const defaultDialog = reactive({
  visible: false,
  submitting: false,
  form: {
    set_default_reason: "",
  },
});

const publishRules: FormRules = {
  verification_job_id: [{ required: true, message: "请填写验证任务 ID", trigger: "blur" }],
  verification_note: [{ required: true, message: "请填写验证说明", trigger: "blur" }],
  publish_reason: [{ required: true, message: "请填写发布原因", trigger: "blur" }],
};
const defaultRules: FormRules = {
  set_default_reason: [{ required: true, message: "请填写切换原因", trigger: "blur" }],
};
const templateVersionId = computed(() => props.version.template_version_id || `${props.templateId}@${props.version.version}`);
const canValidate = computed(() => props.management || props.version.status === "draft");
const canDisable = computed(() => props.management && !props.version.is_default && props.version.status !== "disabled");

function openValidationDialog(): void {
  validationDialog.file = null;
  validationDialog.mode = "direct_pdf_to_word";
  validationDialog.visible = true;
  validationUploadRef.value?.clearFiles();
}

function handleValidationFileChange(uploadFile: UploadFile): void {
  const rawFile = uploadFile.raw as UploadRawFile | undefined;
  if (!rawFile) {
    return;
  }
  const validationError = validatePdfFile(rawFile);
  if (validationError) {
    emit("failed", { message: validationError, raw: validationError });
    validationUploadRef.value?.clearFiles();
    validationDialog.file = null;
    return;
  }
  validationDialog.file = rawFile;
}

function handleValidationFileRemove(): void {
  validationDialog.file = null;
}

async function createValidationJob(): Promise<void> {
  if (!validationDialog.file) {
    return;
  }
  validationDialog.submitting = true;
  try {
    const authorization = await filesApi.createUploadUrl({
      filename: validationDialog.file.name,
      mime_type: validationDialog.file.type || "application/pdf",
      size_bytes: validationDialog.file.size,
      file_type: "source_pdf",
    });
    await uploadFileContent(authorization, validationDialog.file, auth.token);
    const response = await documentJobsApi.create({
      source_file_id: authorization.file_id,
      translation_mode: documentJobModeTranslationMode(validationDialog.mode),
      document_language: documentJobModeCreateLanguage(validationDialog.mode),
      template_version_id: templateVersionId.value,
      debug_full_text: false,
    });
    createdVerificationJobId.value = response.job_id;
    ElMessage.success(`验证任务已创建：${response.job_id}`);
    validationDialog.visible = false;
  } catch (caught) {
    emit("failed", normalizeApiError(caught));
  } finally {
    validationDialog.submitting = false;
  }
}

function openPublishDialog(): void {
  publishDialog.form.verification_job_id = props.version.verification_job_id || createdVerificationJobId.value;
  publishDialog.form.verification_note = props.version.verification_note || "";
  publishDialog.form.publish_reason = "";
  publishDialog.visible = true;
}

async function publishVersion(): Promise<void> {
  const valid = await publishFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishDialog.submitting = true;
  try {
    const version = await templatesApi.publishVersion(props.templateId, props.version.version, {
      make_default: false,
      verification_job_id: publishDialog.form.verification_job_id,
      verification_note: publishDialog.form.verification_note,
      publish_reason: publishDialog.form.publish_reason,
    });
    ElMessage.success("模板版本已发布。");
    publishDialog.visible = false;
    emit("changed", version);
  } catch (caught) {
    emit("failed", normalizeApiError(caught));
  } finally {
    publishDialog.submitting = false;
  }
}

function openDefaultDialog(): void {
  defaultDialog.form.set_default_reason = "";
  defaultDialog.visible = true;
}

async function setDefaultVersion(): Promise<void> {
  const valid = await defaultFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  defaultDialog.submitting = true;
  try {
    const version = await templatesApi.setDefaultVersion(props.templateId, props.version.version, {
      set_default_reason: defaultDialog.form.set_default_reason,
    });
    ElMessage.success("默认模板版本已切换。");
    defaultDialog.visible = false;
    emit("changed", version);
  } catch (caught) {
    emit("failed", normalizeApiError(caught));
  } finally {
    defaultDialog.submitting = false;
  }
}

async function disableVersion(): Promise<void> {
  try {
    await ElMessageBox.confirm("禁用后该版本不能作为后续默认版本使用，当前默认版本不可禁用。", `禁用版本 ${props.version.version}`, {
      confirmButtonText: "禁用",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  try {
    const version = await templatesApi.disableVersion(props.templateId, props.version.version);
    ElMessage.success("模板版本已禁用。");
    emit("changed", version);
  } catch (caught) {
    emit("failed", normalizeApiError(caught));
  }
}

watch(
  () => props.version.version,
  () => {
    createdVerificationJobId.value = "";
    publishDialog.form.verification_job_id = "";
    publishDialog.form.verification_note = "";
    publishDialog.form.publish_reason = "";
    defaultDialog.form.set_default_reason = "";
  },
);

watch(
  () => props.autoOpenValidation,
  (autoOpen) => {
    if (autoOpen && props.version.status === "draft") {
      openValidationDialog();
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.template-version-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.form-gap {
  margin-top: 12px;
}

.validation-mode-options {
  display: flex;
  flex-wrap: wrap;
}

.dialog-note {
  color: var(--app-color-text-muted);
}

.publish-requirement {
  margin-bottom: 16px;
}
</style>
