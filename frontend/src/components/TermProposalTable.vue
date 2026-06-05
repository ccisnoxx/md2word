<!-- File: frontend/src/components/TermProposalTable.vue -->
<!-- Purpose: Render Term Rule proposal queues and highlight the selected proposal row. -->
<template>
  <div class="proposal-table-wrap">
    <el-table
      ref="tableRef"
      :data="items"
      :loading="loading"
      empty-text="暂无 proposal"
      :row-class-name="rowClassName"
      @selection-change="handleSelectionChange"
    >
      <el-table-column v-if="selectable" type="selection" width="48" :selectable="isProposalSelectable" />
      <el-table-column prop="id" label="ID" width="110" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">{{ proposalIntentText[row.intent] || row.intent }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">{{ proposalStatusText[row.status] || row.status }}</template>
      </el-table-column>
      <el-table-column prop="source_term" label="术语" min-width="130" />
      <el-table-column label="分类" min-width="140">
        <template #default="{ row }">{{ categories[row.category_id] || row.category_id }}</template>
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
import { ref } from "vue";
import type { TableInstance } from "element-plus";

import type { TermRuleProposalResponse } from "@/api/types";
import { formatDateTime } from "@/utils/format";

const props = defineProps<{
  items: TermRuleProposalResponse[];
  categories: Record<string, string>;
  loading: boolean;
  selectedId?: string | null;
  selectable?: boolean;
}>();

const emit = defineEmits<{
  select: [proposal: TermRuleProposalResponse];
  "selection-change": [proposals: TermRuleProposalResponse[]];
}>();

const tableRef = ref<TableInstance>();

const proposalIntentText: Record<string, string> = {
  create: "新增",
  update: "编辑",
  disable: "禁用",
};

const proposalStatusText: Record<string, string> = {
  pending_review: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
  published: "已发布",
};

// 根据页面层传入的 selectedId 高亮当前 proposal，保持 table 组件无业务状态。
function rowClassName({ row }: { row: TermRuleProposalResponse }): string {
  return row.id === props.selectedId ? "is-selected-row" : "";
}

// 只允许待审核 proposal 参与批量审核，避免前端批量操作绕过后端 pending-only 语义。
function isProposalSelectable(row: TermRuleProposalResponse): boolean {
  return row.status === "pending_review";
}

// 把 Element Plus selection 事件转发给页面层，由页面维护批量审核状态。
function handleSelectionChange(selection: TermRuleProposalResponse[]): void {
  emit("selection-change", selection);
}

// 供页面在批量操作后主动清空表格勾选状态。
function clearSelection(): void {
  tableRef.value?.clearSelection();
}

defineExpose({ clearSelection });
</script>

<style scoped lang="scss">
.proposal-table-wrap {
  overflow-x: auto;
}

:deep(.el-table__row.is-selected-row td) {
  background: #ecf5ff;
}

.job-link {
  color: #2563eb;
  font-weight: 600;
}
</style>
