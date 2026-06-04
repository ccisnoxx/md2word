<!-- frontend/src/components/TranslationTermProposalTable.vue: Shared table for Translation Term Proposal queues. -->
<template>
  <div class="proposal-table-wrap">
    <el-table :data="items" :loading="loading" empty-text="暂无 Translation Term Proposal">
      <el-table-column prop="id" label="ID" width="120" />
      <el-table-column label="动作" width="90">
        <template #default="{ row }">{{ actionText[row.changes[0]?.action] || row.changes[0]?.action || "-" }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">{{ statusText[row.status] || row.status }}</template>
      </el-table-column>
      <el-table-column label="原文术语" min-width="140">
        <template #default="{ row }">{{ row.changes[0]?.source_term || "-" }}</template>
      </el-table-column>
      <el-table-column label="目标译文" min-width="150">
        <template #default="{ row }">{{ row.changes[0]?.target_term || "-" }}</template>
      </el-table-column>
      <el-table-column label="绑定版本" min-width="180">
        <template #default="{ row }">
          {{ row.observed_translation_term_set_id || "-" }}@{{ row.observed_translation_term_version || "-" }}
        </template>
      </el-table-column>
      <el-table-column label="来源任务" min-width="150">
        <template #default="{ row }">
          <router-link
            v-if="row.source_job_id"
            class="job-link"
            :to="{ name: 'job-detail', params: { jobId: row.source_job_id } }"
          >
            {{ row.source_job_id }}
          </router-link>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="190">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="$emit('select', row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import type { TranslationTermProposalResponse } from "@/api/types";
import { formatDateTime } from "@/utils/format";

defineProps<{
  items: TranslationTermProposalResponse[];
  loading: boolean;
}>();

defineEmits<{
  select: [proposal: TranslationTermProposalResponse];
}>();

const actionText: Record<string, string> = {
  add: "新增",
  update: "编辑",
  delete: "删除",
};

const statusText: Record<string, string> = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
  published: "已发布",
};
</script>

<style scoped lang="scss">
.proposal-table-wrap {
  overflow-x: auto;
}

.job-link {
  color: #2563eb;
  font-weight: 600;
}
</style>
