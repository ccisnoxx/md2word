<!-- frontend/src/pages/TemplateDetailPage.vue: Word template document file and version lifecycle page. -->
<template>
  <main class="template-detail-page app-page" aria-labelledby="template-title">
    <section class="page-heading app-page-header app-page-shell app-page-shell--wide">
      <div>
        <p class="page-kicker">Word 模板文档</p>
        <h1 id="template-title" class="page-title">Word 模板文档</h1>
        <p class="page-description">{{ template?.name || templateId }}：管理 DOCX 模板文件、默认页眉内容、公司 Logo 和模板版本发布流程。</p>
      </div>
      <div class="toolbar">
        <el-button :icon="Brush" @click="openStyleConfig">页面样式配置</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </section>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <section v-if="template" class="document-grid app-page-shell app-page-shell--wide">
      <el-card class="app-panel-card document-summary-card" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">模板文件</h2>
            <p class="section-subtitle">DOCX 文件决定默认页眉、Logo、基础版式骨架和可下载模板资产。</p>
          </div>
          <el-tag v-if="template.is_default" type="success" effect="plain">当前默认模板</el-tag>
        </div>
        <dl class="meta-list">
          <div><dt>模板 ID</dt><dd class="mono">{{ template.id }}</dd></div>
          <div><dt>当前版本</dt><dd>{{ template.version }}</dd></div>
          <div><dt>模板文件</dt><dd>{{ template.template.file_name || "-" }}</dd></div>
          <div><dt>文件大小</dt><dd>{{ formatBytes(template.template.size_bytes) }}</dd></div>
        </dl>
        <div class="document-actions app-action-row">
          <el-button :icon="Download" :disabled="!template.downloadable" @click="downloadTemplate">下载模板</el-button>
          <el-button :icon="Brush" type="primary" plain @click="openStyleConfig">配置页面样式</el-button>
        </div>
      </el-card>

      <el-card class="app-panel-card boundary-card" shadow="never">
        <div class="section-header compact">
          <div>
            <h2 class="section-title">职责边界</h2>
            <p class="section-subtitle">模板文档和页面样式配置分开维护，发布后通过同一 Template Version 生效。</p>
          </div>
        </div>
        <div class="boundary-list">
          <article>
            <strong>模板文档负责</strong>
            <span>公司 Logo、默认页眉/页脚内容、DOCX 文件、版本验证和发布。</span>
          </article>
          <article>
            <strong>页面样式负责</strong>
            <span>页边距、标题、目录、正文、表格、页眉/页脚文字样式等输出格式。</span>
          </article>
        </div>
      </el-card>

      <RoleGate>
        <el-card class="app-panel-card upload-card" shadow="never">
          <div class="section-header">
            <div>
              <h2 class="section-title">上传模板 draft</h2>
              <p class="section-subtitle">只上传 .docx。新版本需创建验证任务、发布并设为默认后才会影响后续 Word 生成。</p>
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
          <el-input
            v-model="renderPolicyJson"
            class="form-gap"
            type="textarea"
            :rows="3"
            placeholder="render_policy_json，高级可选，默认 {}"
          />
          <el-button type="primary" :loading="uploading" :disabled="!draftFile" @click="uploadDraftVersion">
            上传 draft
          </el-button>
        </el-card>
      </RoleGate>
    </section>

    <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">版本列表</h2>
          <p class="section-subtitle">publish 和 set-default 是两个显式动作；页面样式 draft 也会出现在这里。</p>
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
        <el-table-column label="模板文件" min-width="180">
          <template #default="{ row }">{{ row.template.file_name || "-" }}</template>
        </el-table-column>
        <el-table-column label="样式配置" min-width="180">
          <template #default="{ row }">{{ row.layout_config?.file_name || "-" }}</template>
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
              <div class="row-actions app-action-row">
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
        <el-radio-button value="direct_pdf_to_word">直接转 Word</el-radio-button>
        <el-radio-button value="en2zh_pdf_to_word">英译中</el-radio-button>
        <el-radio-button value="ru2zh_pdf_to_word">俄译中</el-radio-button>
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
import { Brush, Download, Refresh, Upload } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";

import { documentJobsApi } from "@/api/documentJobs";
import { filesApi } from "@/api/files";
import { templatesApi } from "@/api/templates";
import type {
  DocumentJobMode,
  TemplateDetailResponse,
  TemplateVersionResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { documentJobModeCreateLanguage, documentJobModeTranslationMode } from "@/utils/format";
import { formatBytes, formatDateTime } from "@/utils/format";
import { uploadFileContent, validatePdfFile } from "@/utils/upload";

const props = defineProps<{
  templateId: string;
}>();

const router = useRouter();
const auth = useAuthStore();
const template = ref<TemplateDetailResponse | null>(null);
const versions = ref<TemplateVersionResponse[]>([]);
const loading = ref(false);
const uploading = ref(false);
const error = ref<ApiClientError | null>(null);
const draftFile = ref<File | null>(null);
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

function openStyleConfig(): void {
  void router.push(`/settings/word-page-styles/${props.templateId}`);
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
      render_policy_json: renderPolicyJson.value,
    });
    ElMessage.success("模板文档 draft version 已上传。");
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
      translation_mode: documentJobModeTranslationMode(validationDialog.mode),
      document_language: documentJobModeCreateLanguage(validationDialog.mode),
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
  gap: var(--app-space-4);
}

.document-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
  gap: var(--app-space-4);
}

.upload-card {
  grid-column: 1 / -1;
}

.document-summary-card,
.boundary-card,
.upload-card {
  border: 1px solid var(--app-color-border);
}

.compact {
  margin-bottom: 10px;
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
  color: var(--app-color-text-muted);
}

.meta-list dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.document-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
}

.boundary-list {
  display: grid;
  gap: 10px;
}

.boundary-list article {
  display: grid;
  gap: 4px;
  padding: var(--app-space-3);
  border: 1px solid var(--app-color-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-color-surface-muted);
}

.boundary-list strong {
  color: var(--app-color-text);
}

.boundary-list span,
.evidence small,
.dialog-note {
  color: var(--app-color-text-muted);
}

.form-gap {
  margin-top: 12px;
}

.evidence {
  display: grid;
  gap: 4px;
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 900px) {
  .document-grid {
    grid-template-columns: 1fr;
  }
}
</style>
