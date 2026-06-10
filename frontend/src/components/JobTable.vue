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
            <el-button
              size="small"
              text
              type="primary"
              :disabled="!canDownloadDocumentJob(row)"
              :title="documentJobActionDisabledReason(row, 'download')"
              @click="$emit('download', row)"
            >
              下载
            </el-button>
            <el-dropdown trigger="click" @command="handleRowCommand(row, $event)">
              <el-button size="small" text :icon="MoreFilled">更多</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    command="retry"
                    :disabled="!canRetryDocumentJob(row)"
                    :title="documentJobActionDisabledReason(row, 'retry')"
                  >
                    重试
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="clone"
                    :disabled="!canCloneDocumentJob(row)"
                    :title="documentJobActionDisabledReason(row, 'clone')"
                  >
                    重新发起
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="cancel"
                    :disabled="!canCancelDocumentJob(row)"
                    :title="documentJobActionDisabledReason(row, 'cancel')"
                  >
                    取消
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="archive"
                    :disabled="!canArchiveDocumentJob(row)"
                    :title="documentJobActionDisabledReason(row, 'archive')"
                  >
                    归档
                  </el-dropdown-item>
                  <el-dropdown-item
                    command="unarchive"
                    :disabled="!canUnarchiveDocumentJob(row)"
                    :title="documentJobActionDisabledReason(row, 'unarchive')"
                  >
                    取消归档
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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

import type { DocumentJobResponse } from "@/api/types";
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canCloneDocumentJob,
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

defineProps<{
  jobs: DocumentJobResponse[];
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
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
  }
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

.action-row :deep(.el-button + .el-button) {
  margin-left: 0;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
