<!-- File: frontend/src/components/JobTable.vue -->
<!-- Purpose: 展示 document_jobs 分页表格、批量选择和任务级操作入口。 -->
<template>
  <div class="job-table">
    <el-table
      v-loading="loading"
      :data="jobs"
      border
      class="table"
      empty-text="暂无任务"
      @selection-change="$emit('selection-change', $event)"
    >
      <el-table-column type="selection" width="46" :selectable="isBatchSelectable" />
      <el-table-column label="任务" min-width="320">
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
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态与进度" min-width="220">
        <template #default="{ row }">
          <div class="status-stack">
            <JobStatusBadge :status="row.status" />
            <JobProgress :status="row.status" :stage="row.stage" :progress="row.progress" />
          </div>
        </template>
      </el-table-column>
      <el-table-column label="翻译 QA" min-width="128">
        <template #default="{ row }">
          <el-tag
            v-if="row.mode === 'en2zh_pdf_to_word'"
            size="small"
            :type="translationQaTagType(row)"
            effect="plain"
          >
            {{ translationQaStatusLabel(row) }}
          </el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="异常" min-width="150">
        <template #default="{ row }">
          <span v-if="row.error_code" class="mono error-code" :title="row.error_code">{{ row.error_code }}</span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="155">
        <template #default="{ row }">
          <span class="updated-time">{{ formatDateTime(row.updated_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="168" fixed="right">
        <template #default="{ row }">
          <div class="action-row">
            <el-button size="small" text type="primary" @click="$router.push(`/jobs/${row.id}`)">查看</el-button>
            <el-tooltip
              :disabled="!documentJobActionDisabledReason(row, 'download')"
              :content="documentJobActionDisabledReason(row, 'download')"
              placement="top"
            >
              <span class="action-tooltip-anchor">
                <el-button
                  size="small"
                  text
                  type="primary"
                  :loading="isActionPending(row, 'download')"
                  :disabled="isJobPending(row) || !canDownloadDocumentJob(row)"
                  @click="$emit('download', row)"
                >
                  下载
                </el-button>
              </span>
            </el-tooltip>
            <el-dropdown trigger="click" @command="handleRowCommand(row, $event)">
              <el-button size="small" text :icon="MoreFilled" :disabled="isJobPending(row)">更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
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
        @current-change="$emit('page-change', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { MoreFilled } from "@element-plus/icons-vue";

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
  formatDateTime,
  getJobSourceFilename,
  jobModeText,
  translationQaStatusTagType,
  translationQaStatusText,
} from "@/utils/format";

const props = defineProps<{
  jobs: DocumentJobResponse[];
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
  actionPending?: Record<string, DocumentJobActionId | undefined>;
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

function isBatchSelectable(row: DocumentJobResponse): boolean {
  return canRetryDocumentJob(row) || canArchiveDocumentJob(row) || canCancelDocumentJob(row);
}

// 表格 slot 的 row 类型较宽，统一在 helper 内按 DocumentJobResponse 读取 QA 状态。
function translationQaStatusLabel(row: DocumentJobResponse): string {
  return translationQaStatusText[row.translation_qa_status];
}

// 表格 slot 的 row 类型较宽，统一在 helper 内映射 QA tag 类型。
function translationQaTagType(row: DocumentJobResponse): "success" | "warning" | "danger" | "info" {
  return translationQaStatusTagType(row.translation_qa_status);
}

function handleRowCommand(row: DocumentJobResponse, command: string | number | object): void {
  if (typeof command !== "string") {
    return;
  }
  if (command === "retry") {
    emit("retry", row);
  } else if (command === "clone") {
    emit("clone", row);
  } else if (command === "cancel") {
    emit("cancel", row);
  } else if (command === "archive") {
    emit("archive", row);
  } else if (command === "unarchive") {
    emit("unarchive", row);
  } else if (command === "delete") {
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
}

.table {
  width: 100%;
}

.error-code {
  color: #b42318;
}

.job-main {
  display: grid;
  gap: 6px;
  min-width: 0;
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
  color: #1d4ed8;
  font-weight: 650;
}

.job-meta {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 6px;
  color: #667085;
}

.job-id {
  display: inline-block;
  max-width: 168px;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.status-stack {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.error-code,
.updated-time {
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

.action-pending-label {
  color: #667085;
  font-size: 12px;
}

.action-row :deep(.el-button + .el-button) {
  margin-left: 0;
}

.action-tooltip-anchor,
.dropdown-action-label {
  display: inline-flex;
}

.dropdown-action-label {
  display: grid;
  gap: 2px;
  min-width: 124px;
  white-space: normal;
}

.dropdown-action-reason {
  color: #909399;
  font-size: 11px;
  line-height: 1.3;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
