<!-- frontend/src/pages/TemplateDetailPage.vue: Template Profile version detail and admin lifecycle actions. -->
<template>
  <main class="template-detail-page" aria-labelledby="template-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Template Profile</p>
        <h1 id="template-title">{{ template?.name || templateId }}</h1>
        <p>{{ template?.description || "查看模板详情、版本和验证证据。" }}</p>
      </div>
      <div class="toolbar">
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <section v-if="template" class="detail-grid">
      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">基础信息</h2>
            <p class="section-subtitle">当前生产默认状态和文件信息。</p>
          </div>
          <el-tag v-if="template.is_default" type="success" effect="plain">当前默认模板</el-tag>
        </div>
        <dl class="meta-list">
          <div><dt>模板 ID</dt><dd class="mono">{{ template.id }}</dd></div>
          <div><dt>当前版本</dt><dd>{{ template.version }}</dd></div>
          <div><dt>模板文件</dt><dd>{{ template.template.file_name || "-" }}</dd></div>
          <div><dt>文件大小</dt><dd>{{ formatBytes(template.template.size_bytes) }}</dd></div>
        </dl>
        <el-button :icon="Download" :disabled="!template.downloadable" @click="downloadTemplate">下载模板</el-button>
      </el-card>

      <RoleGate>
        <el-card class="card-flat" shadow="never">
          <div class="section-header">
            <div>
              <h2 class="section-title">上传 draft version</h2>
              <p class="section-subtitle">只支持 .docx，新版本需验证后再发布。</p>
            </div>
          </div>
          <el-upload
            ref="uploadRef"
            action=""
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            :auto-upload="false"
            :limit="1"
            :on-change="handleDraftFileChange"
            :on-remove="handleDraftFileRemove"
          >
            <el-button :icon="Upload">选择模板文件</el-button>
            <template #tip>
              <div class="el-upload__tip">已选择：{{ draftFile?.name || "无" }}</div>
            </template>
          </el-upload>
          <el-input v-model="layoutConfigPath" class="form-gap" clearable placeholder="layout_config_path，可选" />
          <el-input
            v-model="renderPolicyJson"
            class="form-gap"
            type="textarea"
            :rows="3"
            placeholder="render_policy_json，默认 {}"
          />
          <el-button type="primary" :loading="uploading" :disabled="!draftFile" @click="uploadDraftVersion">
            上传 draft
          </el-button>
        </el-card>
      </RoleGate>
    </section>

    <el-card class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">版本列表</h2>
          <p class="section-subtitle">publish 和 set-default 是两个显式动作。</p>
        </div>
      </div>

      <el-table :data="versions" :loading="loading" empty-text="暂无版本">
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="versionTagType(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column label="验证证据" min-width="260">
          <template #default="{ row }">
            <div class="evidence">
              <span>job: <span class="mono">{{ row.verification_job_id || "-" }}</span></span>
              <small>{{ row.verification_note || "未填写验证说明" }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="发布时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column label="发布原因" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.publish_reason || "-" }}</template>
        </el-table-column>
        <el-table-column label="admin 操作" width="330" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <div class="row-actions">
                <el-button link type="primary" @click="openValidationDialog(row)">创建验证任务</el-button>
                <el-button link type="success" :disabled="row.status === 'published'" @click="openPublishDialog(row)">
                  发布
                </el-button>
                <el-button link type="warning" :disabled="row.is_default || row.status !== 'published'" @click="openDefaultDialog(row)">
                  设默认
                </el-button>
                <el-button link type="danger" :disabled="row.is_default || row.status === 'disabled'" @click="disableVersion(row)">
                  禁用
                </el-button>
              </div>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="validationDialog.visible" title="创建模板验证任务" width="560px">
      <p class="dialog-note">
        将用 <span class="mono">{{ templateVersionId(validationDialog.version) }}</span> 创建 document job。
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
      <el-radio-group v-model="validationDialog.mode" class="form-gap">
        <el-radio-button label="direct_pdf_to_word">直接转 Word</el-radio-button>
        <el-radio-button label="en2zh_pdf_to_word">英译中</el-radio-button>
      </el-radio-group>
      <template #footer>
        <el-button @click="validationDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="validationDialog.submitting" :disabled="!validationDialog.file" @click="createValidationJob">
          创建任务
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="publishDialog.visible" title="发布模板版本" width="560px">
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
  </main>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadFile, type UploadInstance, type UploadRawFile } from "element-plus";
import { Download, Refresh, Upload } from "@element-plus/icons-vue";

import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import { templatesApi } from "@/api/templates";
import type { DocumentJobMode, TemplateDetailResponse, TemplateVersionResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatBytes, formatDateTime } from "@/utils/format";
import { uploadFileContent, validatePdfFile } from "@/utils/upload";

const props = defineProps<{
  templateId: string;
}>();

const auth = useAuthStore();
const template = ref<TemplateDetailResponse | null>(null);
const versions = ref<TemplateVersionResponse[]>([]);
const loading = ref(false);
const uploading = ref(false);
const error = ref<ApiClientError | null>(null);
const draftFile = ref<File | null>(null);
const layoutConfigPath = ref("");
const renderPolicyJson = ref("{}");
const uploadRef = ref<UploadInstance>();
const validationUploadRef = ref<UploadInstance>();
const publishFormRef = ref<FormInstance>();
const defaultFormRef = ref<FormInstance>();

const validationDialog = reactive({
  visible: false,
  version: null as TemplateVersionResponse | null,
  file: null as File | null,
  mode: "direct_pdf_to_word" as DocumentJobMode,
  submitting: false,
});

const publishDialog = reactive({
  visible: false,
  version: null as TemplateVersionResponse | null,
  submitting: false,
  form: {
    verification_job_id: "",
    verification_note: "",
    publish_reason: "",
  },
});

const defaultDialog = reactive({
  visible: false,
  version: null as TemplateVersionResponse | null,
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

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [templateResponse, versionResponse] = await Promise.all([
      templatesApi.get(props.templateId),
      templatesApi.listVersions(props.templateId),
    ]);
    template.value = templateResponse;
    versions.value = versionResponse.items;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

function handleDraftFileChange(uploadFile: UploadFile): void {
  const rawFile = uploadFile.raw as UploadRawFile | undefined;
  if (!rawFile) {
    return;
  }
  if (!rawFile.name.toLowerCase().endsWith(".docx")) {
    error.value = { message: "模板文件必须是 .docx 格式。", raw: rawFile.name };
    uploadRef.value?.clearFiles();
    draftFile.value = null;
    return;
  }
  draftFile.value = rawFile;
  error.value = null;
}

function handleDraftFileRemove(): void {
  draftFile.value = null;
}

async function uploadDraftVersion(): Promise<void> {
  if (!draftFile.value) {
    return;
  }
  uploading.value = true;
  error.value = null;
  try {
    await templatesApi.createVersion(props.templateId, {
      template: draftFile.value,
      layout_config_path: layoutConfigPath.value,
      render_policy_json: renderPolicyJson.value,
    });
    ElMessage.success("Template draft version 已上传。");
    uploadRef.value?.clearFiles();
    draftFile.value = null;
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    uploading.value = false;
  }
}

async function downloadTemplate(): Promise<void> {
  if (!template.value) {
    return;
  }
  try {
    const blob = await templatesApi.download(template.value.id);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = template.value.template.file_name || `${template.value.id}.docx`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

function openValidationDialog(version: TemplateVersionResponse): void {
  validationDialog.version = version;
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
    error.value = { message: validationError, raw: validationError };
    validationUploadRef.value?.clearFiles();
    validationDialog.file = null;
    return;
  }
  validationDialog.file = rawFile;
}

function handleValidationFileRemove(): void {
  validationDialog.file = null;
}

function templateVersionId(version: TemplateVersionResponse | null): string {
  if (!version) {
    return "-";
  }
  return version.template_version_id || `${props.templateId}@${version.version}`;
}

async function createValidationJob(): Promise<void> {
  if (!validationDialog.file || !validationDialog.version) {
    return;
  }
  validationDialog.submitting = true;
  error.value = null;
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
      mode: validationDialog.mode,
      document_language: validationDialog.mode === "en2zh_pdf_to_word" ? "en" : "auto",
      template_version_id: templateVersionId(validationDialog.version),
      debug_full_text: false,
    });
    ElMessage.success(`验证任务已创建：${response.job_id}`);
    validationDialog.visible = false;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    validationDialog.submitting = false;
  }
}

function openPublishDialog(version: TemplateVersionResponse): void {
  publishDialog.version = version;
  publishDialog.form.verification_job_id = version.verification_job_id || "";
  publishDialog.form.verification_note = version.verification_note || "";
  publishDialog.form.publish_reason = "";
  publishDialog.visible = true;
}

async function publishVersion(): Promise<void> {
  if (!publishDialog.version) {
    return;
  }
  const valid = await publishFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishDialog.submitting = true;
  error.value = null;
  try {
    await templatesApi.publishVersion(props.templateId, publishDialog.version.version, {
      make_default: false,
      verification_job_id: publishDialog.form.verification_job_id,
      verification_note: publishDialog.form.verification_note,
      publish_reason: publishDialog.form.publish_reason,
    });
    ElMessage.success("模板版本已发布。");
    publishDialog.visible = false;
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    publishDialog.submitting = false;
  }
}

function openDefaultDialog(version: TemplateVersionResponse): void {
  defaultDialog.version = version;
  defaultDialog.form.set_default_reason = "";
  defaultDialog.visible = true;
}

async function setDefaultVersion(): Promise<void> {
  if (!defaultDialog.version) {
    return;
  }
  const valid = await defaultFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  defaultDialog.submitting = true;
  error.value = null;
  try {
    await templatesApi.setDefaultVersion(props.templateId, defaultDialog.version.version, {
      set_default_reason: defaultDialog.form.set_default_reason,
    });
    ElMessage.success("默认模板版本已切换。");
    defaultDialog.visible = false;
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    defaultDialog.submitting = false;
  }
}

async function disableVersion(version: TemplateVersionResponse): Promise<void> {
  try {
    await ElMessageBox.confirm("禁用后该版本不能作为后续默认版本使用，当前默认版本不可禁用。", `禁用版本 ${version.version}`, {
      confirmButtonText: "禁用",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await templatesApi.disableVersion(props.templateId, version.version);
    ElMessage.success("模板版本已禁用。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

function versionTagType(status: string): "success" | "info" | "warning" | "danger" {
  if (status === "published") {
    return "success";
  }
  if (status === "draft") {
    return "warning";
  }
  if (status === "disabled") {
    return "danger";
  }
  return "info";
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.template-detail-page {
  display: grid;
  gap: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
  gap: 16px;
}

.meta-list {
  display: grid;
  gap: 10px;
  margin: 0 0 16px;
}

.meta-list div {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr);
  gap: 10px;
}

.meta-list dt {
  color: #667085;
}

.meta-list dd {
  margin: 0;
}

.form-gap {
  margin-top: 12px;
}

.evidence {
  display: grid;
  gap: 4px;
}

.evidence small,
.dialog-note {
  color: #667085;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 960px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
