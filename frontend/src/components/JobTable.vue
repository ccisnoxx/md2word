<!-- frontend/src/components/JobTable.vue: Paginated table for document_jobs. -->
<template>
  <div class="job-table">
    <el-table v-loading="loading" :data="jobs" border class="table" empty-text="暂无任务">
      <el-table-column label="任务 ID" min-width="170">
        <template #default="{ row }">
          <router-link class="mono" :to="`/jobs/${row.id}`">{{ row.id }}</router-link>
        </template>
      </el-table-column>
      <el-table-column label="模式" min-width="150">
        <template #default="{ row }">{{ jobModeText[row.mode] || row.mode }}</template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }"><JobStatusBadge :status="row.status" /></template>
      </el-table-column>
      <el-table-column label="进度" min-width="190">
        <template #default="{ row }">
          <JobProgress :status="row.status" :stage="row.stage" :progress="row.progress" />
        </template>
      </el-table-column>
      <el-table-column label="错误" min-width="140">
        <template #default="{ row }">
          <span v-if="row.error_code" class="mono error-code">{{ row.error_code }}</span>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="170">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="$router.push(`/jobs/${row.id}`)">查看</el-button>
          <el-button
            size="small"
            text
            type="primary"
            :disabled="row.status !== 'succeeded'"
            @click="$emit('download', row)"
          >
            下载
          </el-button>
          <el-button
            size="small"
            text
            type="warning"
            :disabled="row.status !== 'failed'"
            @click="$emit('retry', row)"
          >
            重试
          </el-button>
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
import { formatDateTime, jobModeText } from "@/utils/format";

defineProps<{
  jobs: DocumentJobResponse[];
  loading: boolean;
  page: number;
  pageSize: number;
  total: number;
}>();

defineEmits<{
  "page-change": [page: number];
  download: [job: DocumentJobResponse];
  retry: [job: DocumentJobResponse];
}>();
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

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
