<!-- File: frontend/src/components/JobTable.vue -->
<!-- Purpose: 展示 document_jobs 分页表格、批量选择和任务级操作入口。 -->
<template>
  <div class="job-table" :class="`is-${density}-density`">
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="jobs"
      border
      :class="['table', `is-${density}-density`]"
      empty-text="暂无任务"
      table-layout="fixed"
      @selection-change="emit('selection-change', $event)"
    >
      <el-table-column v-if="isColumnVisible('selection')" type="selection" width="44" :selectable="isBatchSelectable" />
      <el-table-column v-if="isColumnVisible('identity')" label="任务 / 异常" min-width="360">
        <template #default="{ row }">
          <div class="job-main">
            <router-link class="filename job-title" :to="`/jobs/${row.id}`" :title="getJobSourceFilename(row)">
              {{ getJobSourceFilename(row) }}
            </router-link>
            <div class="job-meta">
              <router-link class="mono job-id" :to="`/jobs/${row.id}`" :title="row.id">{{ row.id }}</router-link>
              <el-tag size="small" effect="plain">{{ jobModeText[row.mode] || row.mode }}</el-tag>
              <el-tag v-if="row.archived_at" size="small" type="info" effect="plain">已归档</el-tag>
            </div>
            <div v-if="failureSummary(row)" class="failure-summary">
              <span class="mono error-code" :title="failureCode(row)">{{ failureCode(row) }}</span>
              <span :title="failureSummary(row)">{{ failureSummary(row) }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('status')" label="状态" min-width="126">
        <template #default="{ row }">
          <div class="status-cell">
            <JobStatusBadge :status="row.status" />
            <span class="muted stage-label">{{ stageLabel(row) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('qa')" label="QA" min-width="126">
        <template #default="{ row }">
          <div v-if="supportsTranslationQa(row)" class="qa-cell">
            <el-tag size="small" :type="translationQaTagType(row)" effect="plain">
              {{ translationQaStatusLabel(row) }}
            </el-tag>
            <span v-if="row.translation_qa_reviewed_by" class="muted qa-reviewer">
              {{ row.translation_qa_reviewed_by }}
            </span>
          </div>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('progress')" label="进度" min-width="170">
        <template #default="{ row }">
          <JobProgress :status="row.status" :stage="row.stage" :progress="row.progress" />
        </template>
      </el-table-column>
      <el-table-column v-if="isColumnVisible('updated')" label="更新" min-width="150">
        <template #default="{ row }">
          <span class="updated-time" :title="`创建：${formatDateTime(row.created_at)}`">
            {{ formatDateTime(row.updated_at) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column
        v-if="isColumnVisible('actions')"
        :key="actionColumnFixed ? 'actions-fixed' : 'actions-static'"
        label="操作"
        width="158"
        :fixed="actionColumnFixed"
      >
        <template #default="{ row }">
          <div class="action-row">
            <el-button
              size="small"
              text
              :type="primaryActionType(row)"
              :loading="isPrimaryActionLoading(row)"
              :disabled="isPrimaryActionDisabled(row)"
              @click="handlePrimaryAction(row)"
            >
              {{ primaryActionLabel(row) }}
            </el-button>
            <el-dropdown trigger="click" placement="bottom-end" @command="handleRowCommand(row, $event)">
              <el-button
                size="small"
                text
                :icon="MoreFilled"
                class="more-action"
                aria-label="更多操作"
                title="更多操作"
              />
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="view">查看详情</el-dropdown-item>
                  <el-dropdown-item
                    command="download"
                    :disabled="isJobPending(row) || !canDownloadDocumentJob(row)"
                  >
                    <span class="dropdown-action-label">
                      <span>下载</span>
                      <small v-if="rowActionDisabledReason(row, 'download')" class="dropdown-action-reason">
                        {{ rowActionDisabledReason(row, 'download') }}
                      </small>
                    </span>
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="retry"
                    :disabled="isJobPending(row) || !canRetryDocumentJob(row)"
                  >
                    <span class="dropdown-action-label">
                      <span>重试</span>
                      <small v-if="rowActionDisabledReason(row, 'retry')" class="dropdown-action-reason">
                        {{ rowActionDisabledReason(row, 'retry') }}
                      </small>
                    </span>
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="clone"
                    :disabled="isJobPending(row) || !canCloneDocumentJob(row)"
                  >
                    <span class="dropdown-action-label">
                      <span>重新发起</span>
                      <small v-if="rowActionDisabledReason(row, 'clone')" class="dropdown-action-reason">
                        {{ rowActionDisabledReason(row, 'clone') }}
                      </small>
                    </span>
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="cancel"
                    :disabled="isJobPending(row) || !canCancelDocumentJob(row)"
                  >
                    <span class="dropdown-action-label">
                      <span>取消</span>
                      <small v-if="rowActionDisabledReason(row, 'cancel')" class="dropdown-action-reason">
                        {{ rowActionDisabledReason(row, 'cancel') }}
                      </small>
                    </span>
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="archive"
                    :disabled="isJobPending(row) || !canArchiveDocumentJob(row)"
                  >
                    <span class="dropdown-action-label">
                      <span>归档</span>
                      <small v-if="rowActionDisabledReason(row, 'archive')" class="dropdown-action-reason">
                        {{ rowActionDisabledReason(row, 'archive') }}
                      </small>
                    </span>
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="unarchive"
                    :disabled="isJobPending(row) || !canUnarchiveDocumentJob(row)"
                  >
                    <span class="dropdown-action-label">
                      <span>取消归档</span>
                      <small v-if="rowActionDisabledReason(row, 'unarchive')" class="dropdown-action-reason">
                        {{ rowActionDisabledReason(row, 'unarchive') }}
                      </small>
                    </span>
                  </el-dropdown-item>
                  <el-dropdown-item
                    v-if="shouldShowDocumentJobAction(row, 'delete')"
                    command="delete"
                    :disabled="isJobPending(row) || !canDeleteDocumentJob(row)"
                  >
                    <span class="dropdown-action-label">
                      <span>删除</span>
                      <small v-if="rowActionDisabledReason(row, 'delete')" class="dropdown-action-reason">
                        {{ rowActionDisabledReason(row, 'delete') }}
                      </small>
                    </span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <span v-if="pendingActionLabel(row)" class="action-pending-label">{{ pendingActionLabel(row) }}</span>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-row">
      <el-pagination
        background
        layout="prev, pager, next, total"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        @current-change="emit('page-change', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { MoreFilled } from "@element-plus/icons-vue";
import { useRouter } from "vue-router";
import type { TableInstance } from "element-plus";

import type { DocumentJobActionId, DocumentJobResponse } from "@/api/types";
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canCloneDocumentJob,
  canDeleteDocumentJob,
  canDownloadDocumentJob,
  canRetryDocumentJob,
  canUnarchiveDocumentJob,
  documentJobActionDisabledReason,
  documentJobModeSupportsTranslationQa,
  formatDateTime,
  getJobSourceFilename,
  jobModeText,
  jobStageText,
  shouldShowDocumentJobAction,
  translationQaStatusTagType,
  translationQaStatusText,
} from "@/utils/format";
import type { WorkbenchTableDensity } from "@/utils/tablePreferences";

const props = defineProps<{
  jobs: DocumentJobResponse[];
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
  actionPending?: Record<string, DocumentJobActionId | undefined>;
  density: WorkbenchTableDensity;
  visibleColumns: string[];
}>();

const emit = defineEmits<{
  "page-change": [page: number];
  "selection-change": [jobs: DocumentJobResponse[]];
  download: [job: DocumentJobResponse];
  retry: [job: DocumentJobResponse];
  clone: [job: DocumentJobResponse];
  cancel: [job: DocumentJobResponse];
  archive: [job: DocumentJobResponse];
  unarchive: [job: DocumentJobResponse];
  delete: [job: DocumentJobResponse];
}>();

type PrimaryRowAction = "download" | "retry" | "view";

const router = useRouter();
const tableRef = ref<TableInstance>();
const actionColumnFixed = ref<"right" | undefined>("right");
let narrowViewportQuery: MediaQueryList | null = null;

function isColumnVisible(columnId: string): boolean {
  return props.visibleColumns.includes(columnId);
}

function syncActionColumnFixed(): void {
  actionColumnFixed.value = narrowViewportQuery?.matches ? undefined : "right";
}

onMounted(() => {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return;
  }
  narrowViewportQuery = window.matchMedia("(max-width: 720px)");
  syncActionColumnFixed();
  narrowViewportQuery.addEventListener("change", syncActionColumnFixed);
});

onBeforeUnmount(() => {
  narrowViewportQuery?.removeEventListener("change", syncActionColumnFixed);
});

watch(
  () => [props.density, props.visibleColumns.join("|")],
  () => {
    void nextTick(() => tableRef.value?.doLayout());
  },
);

function clearSelection(): void {
  tableRef.value?.clearSelection();
}

defineExpose({ clearSelection });

function isBatchSelectable(row: DocumentJobResponse): boolean {
  return canRetryDocumentJob(row) || canArchiveDocumentJob(row) || canCancelDocumentJob(row);
}

function supportsTranslationQa(row: DocumentJobResponse): boolean {
  return documentJobModeSupportsTranslationQa(row.mode);
}

// 表格 slot 的 row 类型较宽，统一在 helper 内按 DocumentJobResponse 读取 QA 状态。
function translationQaStatusLabel(row: DocumentJobResponse): string {
  return translationQaStatusText[row.translation_qa_status];
}

// 表格 slot 的 row 类型较宽，统一在 helper 内映射 QA tag 类型。
function translationQaTagType(row: DocumentJobResponse): "success" | "warning" | "danger" | "info" {
  return translationQaStatusTagType(row.translation_qa_status);
}

function stageLabel(row: DocumentJobResponse): string {
  return jobStageText[row.stage] || row.stage;
}

function failureCode(row: DocumentJobResponse): string {
  return row.error_code || row.failed_stage || "failed";
}

function failureSummary(row: DocumentJobResponse): string {
  if (!row.error_code && !row.error_message && row.status !== "failed") {
    return "";
  }
  const stageText = row.failed_stage ? jobStageText[row.failed_stage] || row.failed_stage : "";
  return [stageText, row.error_message || "进入详情查看失败诊断。"].filter(Boolean).join(" · ");
}

function primaryAction(row: DocumentJobResponse): PrimaryRowAction {
  if (canDownloadDocumentJob(row)) {
    return "download";
  }
  if (canRetryDocumentJob(row)) {
    return "retry";
  }
  return "view";
}

function primaryActionLabel(row: DocumentJobResponse): string {
  const action = primaryAction(row);
  if (action === "download") {
    return "下载";
  }
  if (action === "retry") {
    return "重试";
  }
  return "查看";
}

function primaryActionType(row: DocumentJobResponse): "primary" | "warning" | undefined {
  const action = primaryAction(row);
  if (action === "download" || action === "view") {
    return "primary";
  }
  return "warning";
}

function isPrimaryActionLoading(row: DocumentJobResponse): boolean {
  const action = primaryAction(row);
  return action !== "view" && isActionPending(row, action);
}

function isPrimaryActionDisabled(row: DocumentJobResponse): boolean {
  const action = primaryAction(row);
  return action !== "view" && isJobPending(row);
}

function handlePrimaryAction(row: DocumentJobResponse): void {
  const action = primaryAction(row);
  if (action === "download") {
    emit("download", row);
  } else if (action === "retry") {
    emit("retry", row);
  } else {
    void router.push(`/jobs/${row.id}`);
  }
}

function handleRowCommand(row: DocumentJobResponse, command: string | number | object): void {
  if (typeof command !== "string") {
    return;
  }
  if (command === "view") {
    void router.push(`/jobs/${row.id}`);
  } else if (command === "download") {
    emit("download", row);
  } else if (command === "retry") {
    emit("retry", row);
  } else if (command === "clone") {
    emit("clone", row);
  } else if (command === "cancel") {
    emit("cancel", row);
  } else if (command === "archive") {
    emit("archive", row);
  } else if (command === "unarchive") {
    emit("unarchive", row);
  } else if (command === "delete" && shouldShowDocumentJobAction(row, "delete")) {
    emit("delete", row);
  }
}

function pendingAction(row: DocumentJobResponse): DocumentJobActionId | undefined {
  return props.actionPending?.[row.id];
}

function isActionPending(row: DocumentJobResponse, action: DocumentJobActionId): boolean {
  return pendingAction(row) === action;
}

function isJobPending(row: DocumentJobResponse): boolean {
  return Boolean(pendingAction(row));
}

function rowActionDisabledReason(row: DocumentJobResponse, action: DocumentJobActionId): string {
  if (isJobPending(row)) {
    return "其他操作执行中。";
  }
  return documentJobActionDisabledReason(row, action);
}

function pendingActionLabel(row: DocumentJobResponse): string {
  const action = pendingAction(row);
  if (!action) {
    return "";
  }
  const labels: Record<DocumentJobActionId, string> = {
    download: "下载中",
    retry: "重试中",
    cancel: "取消中",
    archive: "归档中",
    unarchive: "取消归档中",
    clone: "创建中",
    delete: "删除中",
  };
  return labels[action];
}
</script>

<style scoped lang="scss">
.job-table {
  width: 100%;
  overflow-x: auto;
}

.table {
  width: 100%;
}

.table.is-compact-density {
  :deep(.el-table__cell) {
    padding: 6px 0;
  }
}

.job-main {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.is-compact-density .job-main {
  gap: 4px;
}

.filename {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.job-title {
  color: var(--app-color-primary-hover);
  font-weight: 700;
}

.job-meta,
.failure-summary,
.qa-cell,
.status-cell {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
}

.job-meta,
.failure-summary {
  flex-wrap: wrap;
}

.job-id {
  display: inline-block;
  max-width: 168px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.failure-summary {
  padding: 4px 6px;
  border: 1px solid var(--app-color-danger-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-color-danger-soft);
  color: var(--app-color-danger);
  font-size: 12px;
  line-height: 1.35;
}

.is-compact-density .failure-summary {
  padding: 3px 6px;
}

.failure-summary span:last-child {
  overflow: hidden;
  min-width: 0;
  color: var(--app-color-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-cell,
.qa-cell {
  align-items: flex-start;
  flex-direction: column;
}

.is-compact-density .status-cell,
.is-compact-density .qa-cell {
  gap: 4px;
}

.stage-label,
.qa-reviewer,
.updated-time,
.error-code {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.action-row {
  display: flex;
  flex-wrap: nowrap;
  gap: 2px;
  align-items: center;
  white-space: nowrap;
}

.more-action {
  width: 28px;
}

.action-pending-label {
  color: var(--app-color-text-muted);
  font-size: 12px;
}

.action-row :deep(.el-button + .el-button) {
  margin-left: 0;
}

.dropdown-action-label {
  display: grid;
  gap: 2px;
  min-width: 124px;
  white-space: normal;
}

.dropdown-action-reason {
  color: var(--app-color-text-faint);
  font-size: 11px;
  line-height: 1.3;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.is-compact-density .pagination-row {
  margin-top: 10px;
}

@media (max-width: 720px) {
  .job-table {
    overflow-x: auto;
  }

  .table,
  .pagination-row {
    min-width: 980px;
  }

  :deep(.el-table__cell.el-table-fixed-column--right) {
    position: static !important;
    right: auto !important;
    z-index: auto !important;
  }

  :deep(.el-table__cell.el-table-fixed-column--right)::before {
    display: none !important;
  }
}
</style>
