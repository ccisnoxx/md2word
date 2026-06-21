<!-- File: frontend/src/components/TermRuleApprovedProposalsPanel.vue -->
<!-- Purpose: Render approved term-rule proposals that should be checked before publishing. -->
<template>
  <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">已通过待核对建议</h2>
        <p class="section-subtitle">发布前核对本次已审核合并的来源建议。</p>
      </div>
    </div>
    <TermProposalTable
      :items="items"
      :categories="categories"
      :loading="loading"
      @select="emit('select', $event)"
    />
  </el-card>
</template>

<script setup lang="ts">
import type { TermRuleProposalResponse } from "@/api/types";
import TermProposalTable from "@/components/TermProposalTable.vue";

defineProps<{
  items: TermRuleProposalResponse[];
  categories: Record<string, string>;
  loading: boolean;
}>();

const emit = defineEmits<{
  select: [proposal: TermRuleProposalResponse];
}>();
</script>
