<!-- File: frontend/src/components/TermRuleGovernanceReports.vue -->
<!-- Purpose: Render Term Rule Set draft diff and preflight governance reports. -->
<template>
  <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">Draft diff</h2>
        <p class="section-subtitle">默认比较当前 default published version 与 draft。</p>
      </div>
      <el-button :loading="diffLoading" @click="emit('refresh')">刷新 diff</el-button>
    </div>
    <div class="diff-summary app-governance-grid">
      <div v-for="item in diffCounters" :key="item.key" class="diff-counter app-governance-metric">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>
    <el-table :data="diffReport?.items || []" :loading="diffLoading" empty-text="暂无 draft diff">
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="termRuleChangeTypeTagType(row.change_type)" effect="plain">
            {{ termRuleChangeTypeLabel(row.change_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source_term" label="Source term" min-width="150" show-overflow-tooltip />
      <el-table-column label="Changed fields" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.changed_fields.join(", ") || "-" }}</template>
      </el-table-column>
      <el-table-column label="Before" min-width="170">
        <template #default="{ row }">
          <TermPreview v-if="row.before" :segments="row.before.segments" />
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="After" min-width="170">
        <template #default="{ row }">
          <TermPreview v-if="row.after" :segments="row.after.segments" />
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="app-panel-card app-table-card app-page-shell app-page-shell--wide" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">发布前校验</h2>
        <p class="section-subtitle">Errors 和 conflicts 会阻止发布；warnings 仅提示。</p>
      </div>
      <el-tag :type="preflightStatusType" effect="plain">
        {{ preflightStatusLabel }}
      </el-tag>
    </div>
    <el-table :data="preflightFindings" :loading="preflightLoading" empty-text="暂无 preflight finding">
      <el-table-column label="级别" width="100">
        <template #default="{ row }">
          <el-tag :type="termRuleFindingTagType(row.severity)" effect="plain">{{ row.severity }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="Code" width="210" show-overflow-tooltip />
      <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
      <el-table-column prop="source_term" label="Source term" width="150" show-overflow-tooltip />
      <el-table-column prop="path" label="Path" width="180" show-overflow-tooltip />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

import type {
  TermRuleSetDiffResponse,
  TermRuleSetPreflightResponse,
} from "@/api/types";
import TermPreview from "@/components/TermPreview.vue";
import {
  termRuleChangeTypeLabel,
  termRuleChangeTypeTagType,
  termRuleDiffCounters,
  termRuleFindingTagType,
  termRulePreflightFindings,
  termRulePreflightStatusLabel,
  termRulePreflightStatusType,
} from "@/composables/useTermRuleGovernanceDisplay";

const props = defineProps<{
  diffReport: TermRuleSetDiffResponse | null;
  preflightReport: TermRuleSetPreflightResponse | null;
  diffLoading: boolean;
  preflightLoading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

const diffCounters = computed(() => termRuleDiffCounters(props.diffReport));
const preflightFindings = computed(() => termRulePreflightFindings(props.preflightReport));
const preflightStatusLabel = computed(() => termRulePreflightStatusLabel(props.preflightReport));
const preflightStatusType = computed(() => termRulePreflightStatusType(props.preflightReport));
</script>

<style scoped lang="scss">
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

@media (max-width: 1120px) {
  .diff-summary {
    grid-template-columns: 1fr;
  }
}
</style>
