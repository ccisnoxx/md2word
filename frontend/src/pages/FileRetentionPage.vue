<!-- File: frontend/src/pages/FileRetentionPage.vue -->
<!-- Purpose: Render the Admin-only retention plan, metadata expiry, and guarded physical deletion page. -->
<template>
  <main class="file-retention-page" aria-labelledby="file-retention-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Storage</p>
        <h1 id="file-retention-title">文件保留计划</h1>
        <p>查看已过保留期的 document_files，先标记 expired，再按 dry-run 结果手动物理删除本地文件。</p>
      </div>
      <div class="heading-actions">
        <el-button :icon="Refresh" :loading="loading" @click="() => loadPlan()">刷新</el-button>
        <el-button
          type="warning"
          :icon="Finished"
          :disabled="markableCount === 0"
          :loading="marking"
          @click="markExpired"
        >
          标记 expired
        </el-button>
        <el-button :disabled="selectedFileIds.length === 0" :loading="previewing" @click="previewPhysicalDelete">
          预览物理删除
        </el-button>
        <el-button
          type="danger"
          :disabled="!canOpenDeleteDialog"
          :loading="deleting"
          @click="openPhysicalDeleteDialog"
        >
          执行物理删除
        </el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <el-alert
      class="retention-notice"
      type="warning"
      title="metadata-only"
      :closable="false"
      show-icon
    >
      标记 expired 仍是 metadata-only。物理删除只支持已 expired 的本地文件，必须先预览、选择文件、填写 reason 并输入确认短语；任务记录、事件、metadata 行和 object_key 会保留。
    </el-alert>

    <section v-loading="loading" class="summary-grid" aria-label="文件保留计划摘要">
      <article class="summary-card">
        <span>候选文件</span>
        <strong>{{ candidateCount }}</strong>
        <small>已选择：{{ selectedFileIds.length }} · 可标记 uploaded：{{ markableCount }}</small>
      </article>
      <article class="summary-card">
        <span>保留天数</span>
        <strong>{{ plan?.retention_days ?? "-" }}</strong>
        <small>来自后端当前配置</small>
      </article>
      <article class="summary-card">
        <span>文件总数</span>
        <strong>{{ totalValue("files_seen") }}</strong>
        <small>有 expires_at：{{ totalValue("files_with_expires_at") }}</small>
      </article>
      <article class="summary-card">
        <span>生成时间</span>
        <strong class="summary-time">{{ formatDateTime(plan?.generated_at) }}</strong>
        <small>action: {{ plan?.action_mode || "dry_run" }}</small>
      </article>
    </section>

    <section class="retention-table-section" aria-label="过期候选文件">
      <div class="section-header">
        <div>
          <h2 class="section-title">过期候选</h2>
          <p class="section-subtitle">根据 `expires_at` 生成，`deleted` 状态文件不会进入候选；物理删除只执行 selected expired local 文件。</p>
        </div>
        <div class="toolbar">
          <el-tag effect="plain" :type="plan?.deletion_supported ? 'danger' : 'info'">
            deletion_supported={{ String(plan?.deletion_supported ?? false) }}
          </el-tag>
          <el-tag effect="plain">selected={{ selectedFileIds.length }}</el-tag>
        </div>
      </div>

      <el-table
        :data="plan?.candidates || []"
        empty-text="暂无过期候选文件"
        class="retention-table"
        table-layout="fixed"
        row-key="file_id"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="file_id" label="File ID" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.file_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="job_id" label="Job" min-width="170">
          <template #default="{ row }">
            <router-link v-if="row.job_id" :to="`/jobs/${row.job_id}`" class="mono">
              {{ row.job_id }}
            </router-link>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="Type" min-width="140" />
        <el-table-column prop="storage_provider" label="Storage" min-width="140" />
        <el-table-column prop="status" label="Status" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status)" effect="plain">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="size_bytes" label="Size" width="110">
          <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column prop="expires_at" label="Expires" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column prop="object_key" label="Object Key" min-width="320">
          <template #default="{ row }">
            <span class="mono object-key">{{ row.object_key }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="260" />
      </el-table>
    </section>

    <section v-if="deleteReport" class="retention-table-section" aria-label="物理删除预览和执行结果">
      <div class="section-header">
        <div>
          <h2 class="section-title">物理删除结果</h2>
          <p class="section-subtitle">
            {{ deleteReport.action_mode }} · generated {{ formatDateTime(deleteReport.generated_at) }} ·
            required confirmation: <span class="mono">{{ deleteReport.confirmation_phrase }}</span>
          </p>
        </div>
        <div class="toolbar">
          <el-tag type="success" effect="plain">deletable={{ totalDeleteValue("deletable") }}</el-tag>
          <el-tag type="danger" effect="plain">deleted={{ totalDeleteValue("deleted") }}</el-tag>
          <el-tag type="warning" effect="plain">skipped={{ totalDeleteValue("skipped") }}</el-tag>
          <el-tag type="danger" effect="plain">failed={{ totalDeleteValue("failed") }}</el-tag>
        </div>
      </div>

      <el-table :data="deleteReport.items" empty-text="暂无物理删除结果" class="retention-table" table-layout="fixed">
        <el-table-column prop="file_id" label="File ID" min-width="180">
          <template #default="{ row }">
            <span class="mono">{{ row.file_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="outcome" label="Outcome" min-width="180">
          <template #default="{ row }">
            <el-tag size="small" :type="outcomeTag(row.outcome)" effect="plain">{{ row.outcome }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status_before" label="Before" width="110">
          <template #default="{ row }">{{ row.status_before || "-" }}</template>
        </el-table-column>
        <el-table-column prop="status_after" label="After" width="110">
          <template #default="{ row }">{{ row.status_after || "-" }}</template>
        </el-table-column>
        <el-table-column prop="storage_provider" label="Storage" min-width="130">
          <template #default="{ row }">{{ row.storage_provider || "-" }}</template>
        </el-table-column>
        <el-table-column prop="deleted" label="Deleted" width="100">
          <template #default="{ row }">{{ row.deleted ? "yes" : "no" }}</template>
        </el-table-column>
        <el-table-column prop="metadata_updated" label="Metadata" width="110">
          <template #default="{ row }">{{ row.metadata_updated ? "updated" : "unchanged" }}</template>
        </el-table-column>
        <el-table-column prop="reason" label="Reason" min-width="280" show-overflow-tooltip />
        <el-table-column prop="object_key" label="Object Key" min-width="320">
          <template #default="{ row }">
            <span class="mono object-key">{{ row.object_key || "-" }}</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="deleteDialog.visible" title="执行物理删除" width="640px">
      <el-alert class="delete-warning" type="error" title="不可逆操作" :closable="false" show-icon>
        该操作会删除 selected expired local/local_object 文件内容；metadata 行、任务记录、事件和 object_key 会保留。
      </el-alert>
      <el-form label-position="top">
        <el-form-item label="Selected file IDs">
          <el-input :model-value="selectedFileIds.join('\n')" type="textarea" :rows="4" readonly class="mono" />
        </el-form-item>
        <el-form-item label="Reason">
          <el-input v-model="deleteDialog.reason" type="textarea" :rows="2" placeholder="说明为什么执行本次物理删除" />
        </el-form-item>
        <el-form-item label="Confirmation phrase">
          <el-input v-model="deleteDialog.confirmation" :placeholder="deleteReport?.confirmation_phrase || 'DELETE EXPIRED FILES'" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteDialog.visible = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="executePhysicalDelete">确认物理删除</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Finished, Refresh } from "@element-plus/icons-vue";

import { filesApi } from "@/api/files";
import type {
  FileRetentionCandidateResponse,
  FileRetentionDeleteOutcome,
  FileRetentionDeleteResponse,
  FileRetentionPlanResponse,
} from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { formatBytes, formatDateTime } from "@/utils/format";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";

type StatusTag = "success" | "warning" | "info" | "danger";

const plan = ref<FileRetentionPlanResponse | null>(null);
const selectedCandidates = ref<FileRetentionCandidateResponse[]>([]);
const deleteReport = ref<FileRetentionDeleteResponse | null>(null);
const loading = ref(false);
const marking = ref(false);
const previewing = ref(false);
const deleting = ref(false);
const error = ref<ApiClientError | null>(null);
const deleteDialog = reactive({
  visible: false,
  reason: "",
  confirmation: "",
});

const candidateCount = computed(() => plan.value?.candidates.length ?? 0);
const markableCount = computed(() => (
  plan.value?.candidates.filter((candidate) => candidate.status === "uploaded").length ?? 0
));
const selectedFileIds = computed(() => selectedCandidates.value.map((candidate) => candidate.file_id));
const deletablePreviewCount = computed(() => (
  deleteReport.value?.items.filter((item) => item.outcome === "deletable").length ?? 0
));
const canOpenDeleteDialog = computed(() => (
  selectedFileIds.value.length > 0
  && deleteReport.value?.action_mode === "delete_preview"
  && selectedFileIds.value.join("\n") === deleteReport.value.requested_file_ids.join("\n")
  && deletablePreviewCount.value > 0
));

// 读取当前 retention dry-run 计划。
async function loadPlan(preserveDeleteReport = false): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    plan.value = await filesApi.getRetentionPlan();
    selectedCandidates.value = [];
    if (!preserveDeleteReport) {
      deleteReport.value = null;
    }
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

// 将当前过期候选标记为 expired，但不执行物理删除。
async function markExpired(): Promise<void> {
  if (markableCount.value === 0) {
    return;
  }
  try {
    await ElMessageBox.confirm(
      "该操作只会把当前 uploaded 过期候选的 metadata 状态标记为 expired，不会删除任何文件内容。",
      "标记过期文件",
      {
        confirmButtonText: "标记 expired",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }

  marking.value = true;
  error.value = null;
  try {
    const response = await filesApi.markRetentionExpired();
    plan.value = response;
    selectedCandidates.value = [];
    deleteReport.value = null;
    ElMessage.success(`已标记 ${response.marked_file_ids.length} 个文件。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    marking.value = false;
  }
}

// 记录表格选择，选择变化会清空已有 dry-run 结果。
function handleSelectionChange(rows: FileRetentionCandidateResponse[]): void {
  selectedCandidates.value = rows;
  deleteReport.value = null;
}

// 对当前选择的文件执行物理删除 dry-run。
async function previewPhysicalDelete(): Promise<void> {
  if (selectedFileIds.value.length === 0) {
    return;
  }
  previewing.value = true;
  error.value = null;
  try {
    const response = await filesApi.previewRetentionDelete({ file_ids: selectedFileIds.value });
    deleteReport.value = response;
    ElMessage.success(`已预览 ${response.items.length} 个文件，deletable=${response.totals.deletable ?? 0}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    previewing.value = false;
  }
}

// 打开物理删除确认框，要求用户重新输入 reason 和确认短语。
function openPhysicalDeleteDialog(): void {
  if (!canOpenDeleteDialog.value) {
    ElMessage.warning("请先对当前选择执行物理删除预览。");
    return;
  }
  deleteDialog.reason = "";
  deleteDialog.confirmation = "";
  deleteDialog.visible = true;
}

// 执行 selected expired 文件物理删除，并刷新 retention plan。
async function executePhysicalDelete(): Promise<void> {
  if (!canOpenDeleteDialog.value || !deleteReport.value) {
    return;
  }
  deleting.value = true;
  error.value = null;
  try {
    const response = await filesApi.deleteExpiredRetentionFiles({
      file_ids: deleteReport.value.requested_file_ids,
      reason: deleteDialog.reason,
      confirmation: deleteDialog.confirmation,
    });
    deleteReport.value = response;
    deleteDialog.visible = false;
    await loadPlan(true);
    ElMessage.success(`物理删除完成：deleted=${response.totals.deleted ?? 0}，skipped=${response.totals.skipped ?? 0}。`);
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    deleting.value = false;
  }
}

// 读取 totals 中的数值，缺失时展示 0。
function totalValue(key: string): number {
  return plan.value?.totals[key] ?? 0;
}

// 读取物理删除 report totals 中的数值，缺失时展示 0。
function totalDeleteValue(key: string): number {
  return deleteReport.value?.totals[key] ?? 0;
}

// 将 metadata 状态映射为表格标签样式。
function statusTag(status: string): StatusTag {
  if (status === "uploaded") {
    return "warning";
  }
  if (status === "expired") {
    return "info";
  }
  if (status === "deleted") {
    return "danger";
  }
  return "success";
}

// 将物理删除 outcome 映射为结果标签样式。
function outcomeTag(outcome: FileRetentionDeleteOutcome): StatusTag {
  if (outcome === "deleted" || outcome === "already_missing" || outcome === "deletable") {
    return "success";
  }
  if (outcome === "failed") {
    return "danger";
  }
  if (outcome === "skipped_unsupported_storage") {
    return "warning";
  }
  return "info";
}

onMounted(() => {
  void loadPlan();
});
</script>

<style scoped lang="scss">
.file-retention-page {
  display: grid;
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.heading-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.retention-notice {
  margin-bottom: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  display: grid;
  gap: 6px;
  min-height: 112px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.summary-card span,
.summary-card strong,
.summary-card small {
  display: block;
}

.summary-card span {
  color: #667085;
  font-size: 13px;
}

.summary-card strong {
  color: #111827;
  font-size: 24px;
  line-height: 1.2;
}

.summary-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.summary-time {
  font-size: 16px !important;
  line-height: 1.4 !important;
}

.retention-table-section {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.section-title {
  margin: 0;
  color: #111827;
  font-size: 18px;
}

.section-subtitle {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.retention-table {
  width: 100%;
}

.mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.object-key {
  overflow-wrap: anywhere;
}

.delete-warning {
  margin-bottom: 14px;
}

@media (max-width: 920px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
