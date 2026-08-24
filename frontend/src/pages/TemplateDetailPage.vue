<!-- frontend/src/pages/TemplateDetailPage.vue: Word 模板文件与版本生命周期管理页。 -->
<template>
  <main class="template-detail-page app-page" aria-labelledby="template-title">
    <WorkbenchPageHeader
      title-id="template-title"
      kicker="Word 模板文档"
      title="Word 模板文档"
      :description="`${template?.name || templateId}：管理 DOCX 模板文件、默认页眉内容、公司 Logo 和模板版本发布流程。`"
      wide
      section-class="page-heading app-page-header"
      actions-class="toolbar"
    >
      <template #actions>
        <el-button :icon="Brush" @click="openStyleConfig">页面样式配置</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
      </template>
    </WorkbenchPageHeader>

    <ApiErrorAlert class="app-page-shell app-page-shell--wide" :error="error" />

    <section v-if="template" class="document-grid app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="模板文件"
        subtitle="DOCX 文件决定默认页眉、Logo、基础版式骨架和可下载模板资产。"
        card-class="document-summary-card"
      >
        <template #actions>
          <el-tag v-if="template.is_default" type="success" effect="plain">当前默认模板</el-tag>
        </template>
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
      </WorkbenchPanelCard>

      <WorkbenchPanelCard
        title="职责边界"
        subtitle="模板文档和页面样式配置分开维护，发布后通过同一 Template Version 生效。"
        card-class="boundary-card"
      >
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
      </WorkbenchPanelCard>

      <RoleGate>
        <WorkbenchPanelCard
          title="上传模板 draft"
          subtitle="只上传 .docx。新版本需创建验证任务、发布并设为默认后才会影响后续 Word 生成。"
          card-class="upload-card"
        >
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
        </WorkbenchPanelCard>
      </RoleGate>
    </section>

    <section class="app-page-shell app-page-shell--wide">
      <WorkbenchPanelCard
        title="版本列表"
        subtitle="publish 和 set-default 是两个显式动作；页面样式 draft 也会出现在这里。"
        card-class="app-table-card"
      >
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
              <TemplateVersionLifecycleActions
                :template-id="props.templateId"
                :version="row"
                management
                :auto-open-validation="requestedValidationVersion === row.version"
                @changed="loadAll"
                @failed="error = $event"
              />
            </RoleGate>
          </template>
        </el-table-column>
        </el-table>
      </WorkbenchPanelCard>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, type UploadFile, type UploadInstance, type UploadRawFile } from "element-plus";
import { Brush, Download, Refresh, Upload } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { templatesApi } from "@/api/templates";
import type {
  TemplateDetailResponse,
  TemplateVersionResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import TemplateVersionLifecycleActions from "@/components/TemplateVersionLifecycleActions.vue";
import WorkbenchPageHeader from "@/components/WorkbenchPageHeader.vue";
import WorkbenchPanelCard from "@/components/WorkbenchPanelCard.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatBytes, formatDateTime } from "@/utils/format";

const props = defineProps<{
  templateId: string;
}>();

const router = useRouter();
const route = useRoute();
const template = ref<TemplateDetailResponse | null>(null);
const versions = ref<TemplateVersionResponse[]>([]);
const loading = ref(false);
const uploading = ref(false);
const error = ref<ApiClientError | null>(null);
const draftFile = ref<File | null>(null);
const renderPolicyJson = ref("{}");
const uploadRef = ref<UploadInstance>();
const requestedValidationVersion = computed(() => Number(route.query.validate_version));

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

onMounted(() => void loadAll());
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
.evidence small {
  color: var(--app-color-text-muted);
}

.form-gap {
  margin-top: 12px;
}

.evidence {
  display: grid;
  gap: 4px;
}

@media (max-width: 900px) {
  .document-grid {
    grid-template-columns: 1fr;
  }
}
</style>
