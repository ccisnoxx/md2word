<!-- File: frontend/src/components/TranslationTermProposalTable.vue -->
<!-- Purpose: Render Translation Term Proposal queues and highlight the selected proposal row. -->
<template>
  <div class="proposal-table-wrap">
    <el-table
      ref="tableRef"
      :data="items"
      :loading="loading"
      empty-text="暂无翻译术语建议"
      :row-class-name="rowClassName"
      @selection-change="handleSelectionChange"
    >
      <el-table-column v-if="selectable" type="selection" width="48" :selectable="isProposalSelectable" />
      <el-table-column prop="id" label="ID" width="120" />
      <el-table-column label="动作" width="90">
        <template #default="{ row }">{{ translationProposalAction(row.changes[0]?.action) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">{{ proposalStatusText(row.status) }}</template>
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
import { ref } from "vue";
import type { TableInstance } from "element-plus";

import type { TranslationTermProposalResponse } from "@/api/types";
import { proposalStatusText, translationProposalActionText } from "@/utils/displayText";
import { formatDateTime } from "@/utils/format";

const props = defineProps<{
  items: TranslationTermProposalResponse[];
  loading: boolean;
  selectedId?: string | null;
  selectable?: boolean;
}>();

const emit = defineEmits<{
  select: [proposal: TranslationTermProposalResponse];
  "selection-change": [proposals: TranslationTermProposalResponse[]];
}>();

const tableRef = ref<TableInstance>();

function translationProposalAction(action: string | undefined): string {
  return action ? translationProposalActionText(action) : "-";
}

// 根据页面层传入的 selectedId 高亮当前 proposal，避免 table 自己维护选中状态。
function rowClassName({ row }: { row: TranslationTermProposalResponse }): string {
  return row.id === props.selectedId ? "is-selected-row" : "";
}

// 只允许待审核 proposal 参与批量审核，避免前端绕过后端 pending-only 语义。
function isProposalSelectable(row: TranslationTermProposalResponse): boolean {
  return row.status === "pending";
}

// 把 Element Plus selection 事件转发给页面层，由页面维护批量审核状态。
function handleSelectionChange(selection: TranslationTermProposalResponse[]): void {
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
