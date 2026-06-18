<!-- frontend/src/components/ConfigTodoSummary.vue: Render config workbench release-gate summary. -->
<template>
  <el-card class="config-summary card-flat app-panel-card" shadow="never">
    <div class="section-header">
      <div>
        <h2 class="section-title">运行门禁总览</h2>
        <p class="section-subtitle">聚合 P0 document_jobs、模板、术语和翻译配置状态。</p>
      </div>
      <div class="summary-actions">
        <el-tag v-if="summary" :type="statusTagType(summary.overall_status)" effect="plain">
          {{ statusLabel(summary.overall_status) }}
        </el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="$emit('refresh')">刷新</el-button>
      </div>
    </div>

    <ApiErrorAlert :error="error" />

    <el-skeleton v-if="loading" :rows="3" animated />
    <el-empty v-else-if="!summary" description="暂无配置工作台总览" :image-size="80" />
    <template v-else>
      <div class="summary-metric-grid app-metric-grid">
        <article v-for="item in metrics" :key="item.key" class="metric-item app-metric-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.helper }}</small>
        </article>
      </div>

      <el-alert
        v-if="summary.release_gate.blockers.length"
        class="gate-alert"
        type="error"
        title="P0 document_jobs 门禁阻断"
        :closable="false"
        show-icon
      >
        <ul class="finding-list">
          <li v-for="item in releaseGateBlockerItems" :key="item.code">{{ item.message }}</li>
        </ul>
      </el-alert>
      <el-alert
        v-else-if="summary.release_gate.warnings.length"
        class="gate-alert"
        type="warning"
        title="P0 document_jobs 门禁告警"
        :closable="false"
        show-icon
      >
        <ul class="finding-list">
          <li v-for="item in releaseGateWarningItems" :key="item.code">{{ item.message }}</li>
        </ul>
      </el-alert>
    </template>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Refresh } from "@element-plus/icons-vue";

import type { ConfigWorkbenchStatus, ConfigTodoSummaryResponse } from "@/api/configSummary";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { configWorkbenchStatusText, readinessCodeText } from "@/utils/displayText";
import type { ApiClientError } from "@/utils/errors";
import { formatDateTime } from "@/utils/format";

const props = defineProps<{
  summary: ConfigTodoSummaryResponse | null;
  loading: boolean;
  error: ApiClientError | null;
}>();

defineEmits<{
  refresh: [];
}>();

const metrics = computed(() => {
  const summary = props.summary;
  if (!summary) {
    return [];
  }
  const blockedGroups = summary.groups.filter((group) => group.status === "blocked").length;
  const warningGroups = summary.groups.filter((group) => group.status === "warning").length;
  const unavailableGroups = summary.groups.filter((group) => group.status === "unavailable").length;
  return [
    {
      key: "p0-gate",
      label: "P0 文档任务",
      value: summary.release_gate.p0_document_jobs_ready ? "就绪" : "已阻断",
      helper: summary.release_gate.p0_document_jobs_required ? "生产门禁已启用" : "当前环境非强制",
    },
    {
      key: "blocked",
      label: "阻断配置组",
      value: blockedGroups,
      helper: "需要先处理再发布",
    },
    {
      key: "warning",
      label: "告警配置组",
      value: warningGroups,
      helper: "存在待审核、草稿或告警",
    },
    {
      key: "unavailable",
      label: "不可用配置组",
      value: unavailableGroups,
      helper: "通常表示未启用 MySQL 资源版本服务",
    },
    {
      key: "updated",
      label: "更新时间",
      value: formatDateTime(summary.generated_at),
      helper: "后端聚合生成时间",
    },
  ];
});

const releaseGateBlockerItems = computed(() => releaseGateFindings("blockers", "blocker_findings"));
const releaseGateWarningItems = computed(() => releaseGateFindings("warnings", "warning_findings"));

function statusLabel(status: ConfigWorkbenchStatus): string {
  return configWorkbenchStatusText(status);
}

function releaseGateFindings(
  codeKey: "blockers" | "warnings",
  findingKey: "blocker_findings" | "warning_findings",
): { code: string; message: string }[] {
  const summary = props.summary;
  if (!summary) {
    return [];
  }
  const findings = summary.release_gate[findingKey] || [];
  if (findings.length) {
    return findings.map((item) => ({ code: item.code, message: item.message }));
  }
  return summary.release_gate[codeKey].map((code) => ({ code, message: readinessCodeText(code) }));
}

function statusTagType(status: ConfigWorkbenchStatus): "success" | "warning" | "danger" | "info" {
  if (status === "ready") {
    return "success";
  }
  if (status === "blocked") {
    return "danger";
  }
  if (status === "warning") {
    return "warning";
  }
  return "info";
}
</script>

<style scoped lang="scss">
.config-summary {
  min-width: 0;
}

.summary-actions {
  display: flex;
  align-items: center;
  gap: var(--app-space-2);
}

.summary-metric-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.metric-item {
  min-height: 104px;
}

.metric-item strong {
  font-size: 22px;
  line-height: 1.15;
}

.metric-item small {
  font-size: 12px;
}

.gate-alert {
  margin-top: var(--app-space-3);
}

.finding-list {
  margin: 8px 0 0;
  padding-left: 18px;
}

@media (max-width: 1120px) {
  .summary-metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .section-header,
  .summary-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
