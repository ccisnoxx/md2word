<!-- File: frontend/src/components/TermRuleGovernanceReports.vue -->
<!-- Purpose: Render Term Rule Set draft diff and preflight governance reports. -->
<template>
  <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">草稿差异</h2>
        <p class="section-subtitle">默认比较当前默认发布版本与草稿。</p>
      </div>
      <el-button :loading="diffLoading" @click="emit('refresh')">刷新差异</el-button>
    </div>
    <div class="diff-summary app-governance-grid">
      <div v-for="item in diffCounters" :key="item.key" class="diff-counter app-governance-metric">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>
    <el-alert
      v-if="removedCount > 0"
      class="diff-removed-alert"
      type="warning"
      :closable="false"
      show-icon
    >
      <template #title>草稿将移除 {{ removedCount }} 条规则</template>
      “移除”表示当前草稿相对默认发布版本缺少这些规则；如果直接发布，新默认版本将不再包含这些规则。
    </el-alert>
    <div class="diff-toolbar app-filter-panel">
      <el-select
        v-model="diffFilters.changeType"
        class="diff-filter-select"
        placeholder="全部变更"
        @change="diffFilters.page = 1"
      >
        <el-option v-for="option in diffTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <span class="diff-total">共 {{ filteredDiffItems.length }} 条</span>
    </div>
    <el-table :data="pagedDiffItems" :loading="diffLoading" empty-text="暂无草稿差异">
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="termRuleChangeTypeTagType(row.change_type)" effect="plain">
            {{ termRuleChangeTypeLabel(row.change_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source_term" label="源术语" min-width="150" show-overflow-tooltip />
      <el-table-column label="变更字段" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ termRuleChangedFieldsLabel(row.changed_fields) }}</template>
      </el-table-column>
      <el-table-column label="变更前" min-width="170">
        <template #default="{ row }">
          <TermPreview v-if="row.before" :segments="row.before.segments" />
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="变更后" min-width="170">
        <template #default="{ row }">
          <TermPreview v-if="row.after" :segments="row.after.segments" />
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      v-if="filteredDiffItems.length > diffFilters.pageSize"
      v-model:current-page="diffFilters.page"
      v-model:page-size="diffFilters.pageSize"
      class="table-pagination"
      layout="total, sizes, prev, pager, next"
      :page-sizes="[20, 50, 100]"
      :total="filteredDiffItems.length"
      @size-change="handleDiffPageSizeChange"
    />
  </el-card>

  <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">发布前校验</h2>
        <p class="section-subtitle">错误和冲突会阻止发布；告警仅提示。</p>
      </div>
      <el-tag :type="preflightStatusType" effect="plain">
        {{ preflightStatusLabel }}
      </el-tag>
    </div>
    <el-table :data="preflightFindings" :loading="preflightLoading" empty-text="暂无发布前校验结果">
      <el-table-column label="级别" width="100">
        <template #default="{ row }">
          <el-tag :type="termRuleFindingTagType(row.severity)" effect="plain">
            {{ termRuleFindingSeverityLabel(row.severity) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="代码" width="210" show-overflow-tooltip />
      <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
      <el-table-column prop="source_term" label="源术语" width="150" show-overflow-tooltip />
      <el-table-column prop="path" label="路径" width="180" show-overflow-tooltip />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";

import type {
  TermRuleSetDiffItemResponse,
  TermRuleSetDiffResponse,
  TermRuleSetPreflightResponse,
} from "@/api/types";
import TermPreview from "@/components/TermPreview.vue";
import {
  termRuleChangedFieldsLabel,
  termRuleChangeTypeLabel,
  termRuleChangeTypeTagType,
  termRuleDiffCounters,
  termRuleFindingSeverityLabel,
  termRuleFindingTagType,
  termRulePreflightFindings,
  termRulePreflightStatusLabel,
  termRulePreflightStatusType,
} from "@/composables/useTermRuleGovernanceDisplay";

type DiffChangeFilter = "all" | TermRuleSetDiffItemResponse["change_type"];

const props = defineProps<{
  diffReport: TermRuleSetDiffResponse | null;
  preflightReport: TermRuleSetPreflightResponse | null;
  diffLoading: boolean;
  preflightLoading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

const diffTypeOptions: Array<{ label: string; value: DiffChangeFilter }> = [
  { label: "全部变更", value: "all" },
  { label: "新增", value: "added" },
  { label: "更新", value: "updated" },
  { label: "停用", value: "disabled" },
  { label: "移除", value: "removed" },
  { label: "未变", value: "unchanged" },
];

const diffFilters = reactive({
  changeType: "all" as DiffChangeFilter,
  page: 1,
  pageSize: 20,
});

const diffCounters = computed(() => termRuleDiffCounters(props.diffReport));
const diffItems = computed(() => props.diffReport?.items || []);
const filteredDiffItems = computed(() => {
  if (diffFilters.changeType === "all") {
    return diffItems.value;
  }
  return diffItems.value.filter((item) => item.change_type === diffFilters.changeType);
});
const pagedDiffItems = computed(() => {
  const start = (diffFilters.page - 1) * diffFilters.pageSize;
  return filteredDiffItems.value.slice(start, start + diffFilters.pageSize);
});
const removedCount = computed(() => props.diffReport?.summary.removed ?? 0);
const preflightFindings = computed(() => termRulePreflightFindings(props.preflightReport));
const preflightStatusLabel = computed(() => termRulePreflightStatusLabel(props.preflightReport));
const preflightStatusType = computed(() => termRulePreflightStatusType(props.preflightReport));

function handleDiffPageSizeChange(): void {
  diffFilters.page = 1;
}

watch(
  () => props.diffReport,
  () => {
    diffFilters.page = 1;
  },
);
</script>

<style scoped lang="scss">
.diff-removed-alert {
  margin: var(--app-space-3) 0;
}

.diff-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--app-space-2);
  margin: var(--app-space-3) 0;
}

.diff-filter-select {
  width: 180px;
}

.diff-total {
  color: var(--app-color-text-muted);
  font-size: 13px;
}

.diff-counter {
  min-height: 62px;
}

.diff-counter span {
  display: block;
}

.diff-counter strong {
  display: block;
  margin-top: 4px;
  font-size: 22px;
}

.table-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

@media (max-width: 1120px) {
  .diff-summary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .diff-filter-select {
    width: 100%;
  }
}
</style>
