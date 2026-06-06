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
      <el-table-column label="任务 ID" min-width="150">
        <template #default="{ row }">
          <router-link class="mono" :to="`/jobs/${row.id}`">{{ row.id }}</router-link>
        </template>
      </el-table-column>
      <el-table-column label="源 PDF" min-width="190">
        <template #default="{ row }">
          <span class="filename" :title="getJobSourceFilename(row)">{{ getJobSourceFilename(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="模式" min-width="130">
        <template #default="{ row }">{{ jobModeText[row.mode] || row.mode }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="110">
        <template #default="{ row }"><JobStatusBadge :status="row.status" /></template>
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
      <el-table-column label="归档" min-width="150">
        <template #default="{ row }">
          <span v-if="row.archived_at" class="archived-mark">
            <el-tag size="small" type="info" effect="plain">已归档</el-tag>
            <span>{{ formatDateTime(row.archived_at) }}</span>
          </span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="进度" min-width="170">
        <template #default="{ row }">
          <JobProgress :status="row.status" :stage="row.stage" :progress="row.progress" />
        </template>
      </el-table-column>
      <el-table-column label="错误" min-width="120">
        <template #default="{ row }">
          <span v-if="row.error_code" class="mono error-code">{{ row.error_code }}</span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="155">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="150">
        <template #default="{ row }">
          <div class="action-row">
            <el-button size="small" text type="primary" @click="$router.push(`/jobs/${row.id}`)">查看</el-button>
            <el-button
              size="small"
              text
              type="primary"
              :disabled="!canDownloadDocumentJob(row)"
              @click="$emit('download', row)"
            >
              下载
            </el-button>
            <el-button
              size="small"
              text
              type="warning"
              :disabled="!canRetryDocumentJob(row)"
              @click="$emit('retry', row)"
            >
              重试
            </el-button>
            <el-button
              size="small"
              text
              type="danger"
              :disabled="!canCancelDocumentJob(row)"
              @click="$emit('cancel', row)"
            >
              取消
            </el-button>
            <el-button
              size="small"
              text
              :disabled="!canArchiveDocumentJob(row)"
              @click="$emit('archive', row)"
            >
              归档
            </el-button>
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
import type { DocumentJobResponse } from "@/api/types";
import JobProgress from "@/components/JobProgress.vue";
import JobStatusBadge from "@/components/JobStatusBadge.vue";
import {
  canArchiveDocumentJob,
  canCancelDocumentJob,
  canDownloadDocumentJob,
  canRetryDocumentJob,
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

defineEmits<{
  "page-change": [page: number];
  "selection-change": [jobs: DocumentJobResponse[]];
  download: [job: DocumentJobResponse];
  retry: [job: DocumentJobResponse];
  cancel: [job: DocumentJobResponse];
  archive: [job: DocumentJobResponse];
}>();

function isBatchSelectable(row: DocumentJobResponse): boolean {
  return canRetryDocumentJob(row) || canArchiveDocumentJob(row);
}

// 表格 slot 的 row 类型较宽，统一在 helper 内按 DocumentJobResponse 读取 QA 状态。
function translationQaStatusLabel(row: DocumentJobResponse): string {
  return translationQaStatusText[row.translation_qa_status];
}

// 表格 slot 的 row 类型较宽，统一在 helper 内映射 QA tag 类型。
function translationQaTagType(row: DocumentJobResponse): "success" | "warning" | "danger" | "info" {
  return translationQaStatusTagType(row.translation_qa_status);
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

.filename {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.archived-mark {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
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
