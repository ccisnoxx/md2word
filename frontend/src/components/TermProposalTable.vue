<!-- frontend/src/components/TermProposalTable.vue: Shared proposal table for mine/all/review views. -->
<template>
  <div class="proposal-table-wrap">
    <el-table :data="items" :loading="loading" empty-text="暂无 proposal">
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
import type { TermRuleProposalResponse } from "@/api/types";
import { formatDateTime } from "@/utils/format";

defineProps<{
  items: TermRuleProposalResponse[];
  categories: Record<string, string>;
  loading: boolean;
}>();

defineEmits<{
  select: [proposal: TermRuleProposalResponse];
}>();

const proposalIntentText: Record<string, string> = {
  create: "新增",
  update: "编辑",
  disable: "禁用",
};

const proposalStatusText: Record<string, string> = {
  pending_review: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
};
</script>

<style scoped lang="scss">
.proposal-table-wrap {
  overflow-x: auto;
}
</style>
