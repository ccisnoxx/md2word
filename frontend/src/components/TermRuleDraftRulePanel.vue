<!-- File: frontend/src/components/TermRuleDraftRulePanel.vue -->
<!-- Purpose: Render the Term Rule Set draft-rule list, filters, and row actions. -->
<template>
  <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">草稿规则</h2>
        <p class="section-subtitle">新增、编辑、启停和移除都只作用于草稿。</p>
      </div>
      <div class="rule-actions">
        <el-button type="primary" :icon="Plus" :disabled="!selectedSetId" @click="emit('create')">
          新增规则
        </el-button>
        <el-button :icon="EditPen" :disabled="!selectedSetId" @click="emit('create', 'advanced')">
          新增高级规则
        </el-button>
      </div>
    </div>

    <div class="toolbar filters app-filter-panel" role="search">
      <el-select v-model="filters.categoryId" clearable placeholder="全部分类" class="filter-select">
        <el-option v-for="category in categories" :key="category.id" :label="category.name" :value="category.id" />
      </el-select>
      <el-select v-model="filters.enabled" placeholder="全部状态" class="filter-select">
        <el-option label="全部状态" value="all" />
        <el-option label="仅启用" value="enabled" />
        <el-option label="仅停用" value="disabled" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        clearable
        class="keyword-input"
        placeholder="搜索源术语"
        @keyup.enter="emit('search')"
      />
      <el-button type="primary" :icon="Search" :loading="loading" @click="emit('search')">
        搜索
      </el-button>
      <el-button @click="emit('reset')">清除</el-button>
    </div>

    <el-table :data="rules" :loading="loading" empty-text="暂无草稿规则" class="rule-table">
      <el-table-column prop="source_term" label="源术语" min-width="150" show-overflow-tooltip />
      <el-table-column label="预览" min-width="150">
        <template #default="{ row }">
          <TermPreview :segments="row.segments" />
        </template>
      </el-table-column>
      <el-table-column prop="category_name" label="分类" min-width="130" show-overflow-tooltip />
      <el-table-column label="适用范围" width="116">
        <template #default="{ row }">{{ applyScopeLabel(row.apply_scope) }}</template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="94" />
      <el-table-column label="状态" width="92">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" effect="plain">
            {{ row.enabled ? "启用" : "停用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :icon="EditPen" @click="emit('edit', row)">编辑</el-button>
          <el-button
            link
            type="warning"
            :icon="Switch"
            :loading="togglingRuleId === row.id"
            @click="emit('toggle', row)"
          >
            {{ row.enabled ? "停用" : "启用" }}
          </el-button>
          <el-button
            link
            type="danger"
            :icon="Delete"
            :loading="deletingRuleId === row.id"
            @click="emit('delete', row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > filters.pageSize"
      v-model:current-page="filters.page"
      v-model:page-size="filters.pageSize"
      class="table-pagination"
      layout="total, prev, pager, next"
      :total="total"
      :page-sizes="[20, 50, 100]"
      @current-change="emit('load')"
      @size-change="emit('search')"
    />
  </el-card>
</template>

<script setup lang="ts">
import { Delete, EditPen, Plus, Search, Switch } from "@element-plus/icons-vue";

import type {
  TermRuleCategoryListItemResponse,
  TermRuleResponse,
} from "@/api/types";
import TermPreview from "@/components/TermPreview.vue";
import type { RuleDialogVariant } from "@/composables/useTermRuleForm";

export type DraftRuleEnabledFilter = "all" | "enabled" | "disabled";

export type DraftRuleFilters = {
  page: number;
  pageSize: number;
  categoryId: string;
  enabled: DraftRuleEnabledFilter;
  keyword: string;
};

defineProps<{
  selectedSetId: string;
  categories: TermRuleCategoryListItemResponse[];
  filters: DraftRuleFilters;
  rules: TermRuleResponse[];
  total: number;
  loading: boolean;
  deletingRuleId: string;
  togglingRuleId: string;
}>();

const emit = defineEmits<{
  create: [variant?: RuleDialogVariant];
  edit: [rule: TermRuleResponse];
  toggle: [rule: TermRuleResponse];
  delete: [rule: TermRuleResponse];
  search: [];
  reset: [];
  load: [];
}>();

function applyScopeLabel(scope: string): string {
  const labels: Record<string, string> = {
    both: "正文+表格",
    markdown: "正文",
    table: "表格",
  };
  return labels[scope] || scope;
}
</script>

<style scoped lang="scss">
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  margin-bottom: var(--app-space-3);
}

.rule-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--app-space-2);
  justify-content: flex-end;
}

.filter-select {
  width: 180px;
}

.keyword-input {
  width: min(320px, 100%);
}

.rule-table {
  width: 100%;
}

.table-pagination {
  justify-content: flex-end;
  margin-top: 12px;
}

@media (max-width: 760px) {
  .filter-select,
  .keyword-input {
    width: 100%;
  }

  .filters {
    grid-template-columns: 1fr;
  }
}
</style>
