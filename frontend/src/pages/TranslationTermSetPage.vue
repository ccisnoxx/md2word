<!-- frontend/src/pages/TranslationTermSetPage.vue: Admin Translation Term Set CSV import, export and version actions. -->
<template>
  <main class="translation-term-set-page" aria-labelledby="translation-term-set-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Translation Term Set</p>
        <h1 id="translation-term-set-title">翻译术语集</h1>
        <p>通过 CSV 管理 draft，查看版本并执行发布、设默认和回滚。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
    </section>

    <ApiErrorAlert :error="error" />

    <el-alert
      v-if="unavailable"
      type="warning"
      title="当前部署未启用 MySQL resource service，Translation Term Set 管理不可用。"
      :closable="false"
      show-icon
    />

    <section v-else class="term-set-grid">
      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">术语集</h2>
            <p class="section-subtitle">选择 set 查看 draft 和 published versions。</p>
          </div>
        </div>
        <el-table :data="sets" :loading="loading" empty-text="暂无 Translation Term Set" @row-click="selectSet">
          <el-table-column prop="set_id" label="set_id" min-width="210" show-overflow-tooltip />
          <el-table-column prop="language_pair" label="语言方向" width="110" />
          <el-table-column prop="default_version" label="默认版本" width="150" show-overflow-tooltip />
          <el-table-column prop="version_count" label="版本数" width="90" />
        </el-table>
      </el-card>

      <el-card class="card-flat" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Draft 摘要</h2>
            <p class="section-subtitle">CSV 导入是本阶段唯一 draft 修改入口。</p>
          </div>
          <el-tag v-if="draft?.snapshot_hash" class="mono" effect="plain">{{ draft.snapshot_hash }}</el-tag>
        </div>
        <el-empty v-if="!selectedSetId" description="请选择术语集" :image-size="90" />
        <template v-else>
          <dl class="summary-list">
            <div><dt>base version</dt><dd>{{ draft?.base_version || "-" }}</dd></div>
            <div><dt>term_count</dt><dd>{{ draft?.term_count ?? "-" }}</dd></div>
            <div><dt>validation</dt><dd>{{ draft?.validation.valid ? "valid" : "invalid" }}</dd></div>
          </dl>
          <RoleGate>
            <div class="action-row">
              <el-button type="primary" :disabled="!selectedSetId" @click="openImportDialog">导入 CSV</el-button>
              <el-button type="success" :disabled="!selectedSetId" @click="openPublishDialog">发布 draft</el-button>
              <el-button :disabled="!selectedSetId" @click="exportVersion(null)">导出默认 CSV</el-button>
            </div>
          </RoleGate>
        </template>
      </el-card>
    </section>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Draft validation</h2>
          <p class="section-subtitle">errors 会阻断发布，warnings 作为发布前提示。</p>
        </div>
      </div>
      <el-table :data="validationFindings" :loading="loading" empty-text="暂无 validation findings">
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="row.level === 'error' ? 'danger' : 'warning'" effect="plain">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="code" width="220" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="normalized_source_term" width="220" show-overflow-tooltip />
        <el-table-column prop="message" label="message" min-width="260" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Published versions</h2>
          <p class="section-subtitle">rollback 只切默认指针，不生成新版本。</p>
        </div>
      </div>
      <el-table :data="detail?.versions || []" :loading="loading" empty-text="暂无 published version">
        <el-table-column prop="version" label="版本" width="170" show-overflow-tooltip />
        <el-table-column label="默认" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_default" type="success" effect="plain">默认</el-tag>
            <span v-else class="muted">否</span>
          </template>
        </el-table-column>
        <el-table-column prop="term_count" label="术语数" width="90" />
        <el-table-column prop="snapshot_hash" label="snapshot" min-width="210" show-overflow-tooltip />
        <el-table-column label="发布时间" width="190">
          <template #default="{ row }">{{ formatDateTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column prop="published_by" label="发布人" width="120" />
        <el-table-column prop="release_note" label="发布说明" min-width="180" show-overflow-tooltip />
        <el-table-column v-if="isAdmin" label="admin 操作" width="260" fixed="right">
          <template #default="{ row }">
            <RoleGate>
              <el-button link type="primary" @click="exportVersion(row.version)">导出</el-button>
              <el-button link type="warning" :disabled="row.is_default" @click="setDefault(row.version)">设默认</el-button>
              <el-button link type="danger" @click="rollback(row.version)">Rollback</el-button>
            </RoleGate>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="!unavailable" class="card-flat" shadow="never">
      <div class="section-header">
        <div>
          <h2 class="section-title">Draft entries</h2>
          <p class="section-subtitle">本阶段只读展示，不提供逐行编辑。</p>
        </div>
      </div>
      <el-table :data="draft?.entries || []" :loading="loading" empty-text="暂无 draft entries">
        <el-table-column prop="source_term" label="source_term" min-width="180" show-overflow-tooltip />
        <el-table-column prop="target_term" label="target_term" min-width="180" show-overflow-tooltip />
        <el-table-column prop="normalized_source_term" label="normalized" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="status" width="100" />
        <el-table-column prop="priority" label="priority" width="90" />
        <el-table-column prop="domain" label="domain" width="140" show-overflow-tooltip />
        <el-table-column prop="category" label="category" width="140" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-dialog v-model="importDialog.visible" title="导入 Translation Term CSV" width="720px">
      <el-form ref="importFormRef" :model="importDialog.form" :rules="importRules" label-width="90px">
        <el-form-item label="dedupe" prop="dedupe">
          <el-segmented v-model="importDialog.form.dedupe" :options="dedupeOptions" />
        </el-form-item>
        <el-form-item label="CSV" prop="csv_text">
          <el-input
            v-model="importDialog.form.csv_text"
            type="textarea"
            :rows="12"
            class="mono"
            placeholder="language_pair,source_term,target_term,version"
          />
        </el-form-item>
      </el-form>
      <el-alert
        v-if="lastImportReport"
        class="dialog-alert"
        type="success"
        :title="`导入 ${lastImportReport.imported_rows} 行，重复 ${lastImportReport.duplicate_rows} 行。`"
        :closable="false"
        show-icon
      />
      <template #footer>
        <el-button @click="importDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="importCsv">导入到 draft</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="publishDialog.visible" title="发布 Translation Term Set draft" width="540px">
      <el-form ref="publishFormRef" :model="publishDialog.form" :rules="publishRules" label-width="100px">
        <el-form-item label="发布说明" prop="release_note">
          <el-input v-model="publishDialog.form.release_note" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="publishDialog.form.make_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="publishDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="publishing" @click="publishDraft">发布</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="exportDialog.visible" title="导出 Translation Term CSV" width="760px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="set_id">{{ exportDialog.manifest?.set_id || "-" }}</el-descriptions-item>
        <el-descriptions-item label="version">{{ exportDialog.manifest?.version || "-" }}</el-descriptions-item>
        <el-descriptions-item label="language_pair">{{ exportDialog.manifest?.language_pair || "-" }}</el-descriptions-item>
        <el-descriptions-item label="exported_by">{{ exportDialog.manifest?.exported_by || "-" }}</el-descriptions-item>
      </el-descriptions>
      <el-input v-model="exportDialog.csv_text" type="textarea" :rows="14" class="mono export-text" readonly />
      <template #footer>
        <el-button @click="copyExport">复制 CSV</el-button>
        <el-button type="primary" @click="downloadExport">下载 CSV</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

import { translationTermSetsApi } from "@/api/translationTermSets";
import type {
  TranslationTermSetDetailResponse,
  TranslationTermSetDraftResponse,
  TranslationTermSetExportManifestResponse,
  TranslationTermSetImportReportResponse,
  TranslationTermSetListItemResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import RoleGate from "@/components/RoleGate.vue";
import { useAuthStore } from "@/stores/auth";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

type FindingRow = {
  level: "error" | "warning";
  code: string;
  message: string;
  normalized_source_term: string | null;
};

const auth = useAuthStore();
const isAdmin = computed(() => auth.user?.role === "admin");
const sets = ref<TranslationTermSetListItemResponse[]>([]);
const selectedSetId = ref("");
const detail = ref<TranslationTermSetDetailResponse | null>(null);
const draft = ref<TranslationTermSetDraftResponse | null>(null);
const loading = ref(false);
const unavailable = ref(false);
const importing = ref(false);
const publishing = ref(false);
const error = ref<ApiClientError | null>(null);
const lastImportReport = ref<TranslationTermSetImportReportResponse | null>(null);
const importFormRef = ref<FormInstance>();
const publishFormRef = ref<FormInstance>();

const dedupeOptions = [
  { label: "reject", value: "reject" },
  { label: "keep_first", value: "keep_first" },
];

const importDialog = reactive({
  visible: false,
  form: {
    csv_text: "",
    dedupe: "reject" as "reject" | "keep_first",
  },
});

const publishDialog = reactive({
  visible: false,
  form: {
    make_default: true,
    release_note: "",
  },
});

const exportDialog = reactive({
  visible: false,
  manifest: null as TranslationTermSetExportManifestResponse | null,
  csv_text: "",
});

const importRules: FormRules = {
  csv_text: [{ required: true, message: "请粘贴 CSV 内容", trigger: "blur" }],
};

const publishRules: FormRules = {
  release_note: [{ required: true, message: "请填写发布说明", trigger: "blur" }],
};

const validationFindings = computed<FindingRow[]>(() => {
  const report = draft.value?.validation;
  if (!report) {
    return [];
  }
  return [
    ...report.errors.map((item) => ({ ...item, level: "error" as const })),
    ...report.warnings.map((item) => ({ ...item, level: "warning" as const })),
  ];
});

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = null;
  unavailable.value = false;
  try {
    const response = await translationTermSetsApi.list();
    sets.value = response.items;
    selectedSetId.value ||= sets.value[0]?.set_id || "";
    if (selectedSetId.value) {
      await loadSelectedSet();
    }
  } catch (caught) {
    const normalized = normalizeApiError(caught);
    if (normalized.status === 503) {
      unavailable.value = true;
    }
    error.value = normalized;
  } finally {
    loading.value = false;
  }
}

async function selectSet(row: TranslationTermSetListItemResponse): Promise<void> {
  selectedSetId.value = row.set_id;
  await loadSelectedSet();
}

async function loadSelectedSet(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const [detailResponse, draftResponse] = await Promise.all([
    translationTermSetsApi.get(selectedSetId.value),
    translationTermSetsApi.getDraft(selectedSetId.value),
  ]);
  detail.value = detailResponse;
  draft.value = draftResponse;
}

function openImportDialog(): void {
  importDialog.form.csv_text = "";
  importDialog.form.dedupe = "reject";
  lastImportReport.value = null;
  importDialog.visible = true;
}

async function importCsv(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const valid = await importFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  importing.value = true;
  error.value = null;
  try {
    const response = await translationTermSetsApi.importCsv(selectedSetId.value, {
      csv_text: importDialog.form.csv_text,
      target: "draft",
      dedupe: importDialog.form.dedupe,
    });
    lastImportReport.value = response.import_report;
    ElMessage.success("CSV 已导入 draft。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    importing.value = false;
  }
}

function openPublishDialog(): void {
  publishDialog.form.release_note = "";
  publishDialog.form.make_default = true;
  publishDialog.visible = true;
}

async function publishDraft(): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  const valid = await publishFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  publishing.value = true;
  error.value = null;
  try {
    await translationTermSetsApi.publish(selectedSetId.value, {
      make_default: publishDialog.form.make_default,
      release_note: publishDialog.form.release_note,
    });
    ElMessage.success("Translation Term Set draft 已发布。");
    publishDialog.visible = false;
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    publishing.value = false;
  }
}

async function exportVersion(version: string | null): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  error.value = null;
  try {
    const response = await translationTermSetsApi.exportCsv(selectedSetId.value, version);
    exportDialog.manifest = response.manifest;
    exportDialog.csv_text = response.csv_text;
    exportDialog.visible = true;
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function copyExport(): Promise<void> {
  if (!exportDialog.csv_text) {
    return;
  }
  await navigator.clipboard.writeText(exportDialog.csv_text);
  ElMessage.success("CSV 已复制。");
}

function downloadExport(): void {
  if (!exportDialog.csv_text || !exportDialog.manifest) {
    return;
  }
  const blob = new Blob([exportDialog.csv_text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${exportDialog.manifest.set_id}-${exportDialog.manifest.version}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function setDefault(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm("将该 published version 切换为默认翻译术语集版本。", `设默认 ${version}`, {
      confirmButtonText: "设默认",
      cancelButtonText: "取消",
      type: "warning",
    });
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationTermSetsApi.setDefault(selectedSetId.value, version);
    ElMessage.success("默认翻译术语集已切换。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

async function rollback(version: string): Promise<void> {
  if (!selectedSetId.value) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "Rollback 只会切换默认版本指针，不会生成新版本。",
      `Rollback ${version}`,
      {
        confirmButtonText: "Rollback",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  error.value = null;
  try {
    await translationTermSetsApi.rollback(selectedSetId.value, { version });
    ElMessage.success("已完成 rollback。");
    await loadAll();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  }
}

onMounted(() => {
  void loadAll();
});
</script>

<style scoped lang="scss">
.translation-term-set-page {
  display: grid;
  gap: 16px;
}

.term-set-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(340px, 0.9fr);
  gap: 16px;
}

.summary-list {
  display: grid;
  gap: 10px;
  margin: 0 0 16px;
}

.summary-list div {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: 10px;
}

.summary-list dt {
  color: #667085;
}

.summary-list dd {
  min-width: 0;
  margin: 0;
  color: #111827;
  overflow-wrap: anywhere;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dialog-alert {
  margin-top: 12px;
}

.export-text {
  margin-top: 14px;
}

@media (max-width: 1040px) {
  .term-set-grid {
    grid-template-columns: 1fr;
  }
}
</style>
