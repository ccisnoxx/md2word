<!-- File: frontend/src/pages/OpsDashboardPage.vue -->
<!-- Purpose: Render the Admin-only read-only operations dashboard. -->
<template>
  <main class="ops-dashboard-page" aria-labelledby="ops-dashboard-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">Operations</p>
        <h1 id="ops-dashboard-title">运维看板</h1>
        <p>只读汇总 worker、队列、readiness、存储和任务风险；恢复动作仍需在既有任务页面或外部流程中处理。</p>
      </div>
      <div class="heading-actions">
        <el-tag :type="opsStatus.tagType" effect="plain">{{ opsStatus.label }}</el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新看板</el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <el-alert type="info" title="read-only" :closable="false" show-icon>
      此页面只调用 health 和 document-jobs 读取接口，不提供重试、取消、归档、恢复 MinerU 结果、cleanup 或真实删除操作。
    </el-alert>

    <section v-loading="loading" class="summary-grid" aria-label="运维摘要">
      <article class="summary-card status-card" :class="`is-${opsStatus.key}`">
        <span class="status-dot" aria-hidden="true"></span>
        <div>
          <span>整体状态</span>
          <strong>{{ opsStatus.label }}</strong>
          <small>{{ opsStatus.description }}</small>
        </div>
      </article>

      <article class="summary-card">
        <span>Worker</span>
        <strong>{{ workerMode }}</strong>
        <small>dispatcher: {{ stageDispatcher }}</small>
      </article>

      <article class="summary-card">
        <span>Stage queue</span>
        <strong>{{ queuePressureLabel }}</strong>
        <small>failed {{ stageFailedCount }} · stale {{ staleRunningCount }} · replayable {{ replayableCount }}</small>
      </article>

      <article class="summary-card">
        <span>Document jobs</span>
        <strong>{{ failedJobsTotal }} / {{ runningJobsTotal }}</strong>
        <small>失败 / 运行中样例来自 document-jobs 只读列表</small>
      </article>
    </section>

    <section v-if="alertItems.length" class="alert-grid" aria-label="运维告警和建议">
      <el-alert
        v-for="item in alertItems"
        :key="item.key"
        :type="item.alertType"
        :title="item.title"
        :closable="false"
        show-icon
      >
        <div class="alert-description">{{ item.description }}</div>
        <router-link v-if="item.to" :to="item.to">{{ item.linkText }}</router-link>
      </el-alert>
    </section>

    <section class="dashboard-panels" aria-label="worker 和系统详情">
      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Worker / Queue</h2>
            <p class="section-subtitle">来自 health readiness 和 metrics 的 stage message 观察值。</p>
          </div>
          <router-link to="/system-status">系统状态</router-link>
        </div>
        <div class="metric-table">
          <div v-for="item in queueMetricItems" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-card>

      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Runtime</h2>
            <p class="section-subtitle">metadata、artifact storage 和 readiness 关键字段。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in runtimeItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="card-flat dashboard-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Resources</h2>
            <p class="section-subtitle">默认资源版本和版本数量。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in resourceItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>

    <section class="job-panels" aria-label="任务样例">
      <el-card class="card-flat job-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">失败任务样例</h2>
            <p class="section-subtitle">最多展示 5 条最近更新的失败任务。</p>
          </div>
          <router-link :to="failedJobsRoute">查看全部失败任务</router-link>
        </div>
        <el-table :data="failedJobs" empty-text="暂无失败任务" table-layout="fixed" class="job-table">
          <el-table-column label="Job" min-width="190">
            <template #default="{ row }">
              <router-link :to="`/jobs/${row.id}`" class="mono">{{ row.id }}</router-link>
            </template>
          </el-table-column>
          <el-table-column label="Stage" min-width="130">
            <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
          </el-table-column>
          <el-table-column label="Updated" min-width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
          <el-table-column label="Error" min-width="280" show-overflow-tooltip>
            <template #default="{ row }">{{ jobErrorSummary(row) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="card-flat job-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">运行中任务样例</h2>
            <p class="section-subtitle">最多展示 5 条最近更新的运行中任务。</p>
          </div>
          <router-link :to="runningJobsRoute">查看全部运行中任务</router-link>
        </div>
        <el-table :data="runningJobs" empty-text="暂无运行中任务" table-layout="fixed" class="job-table">
          <el-table-column label="Job" min-width="190">
            <template #default="{ row }">
              <router-link :to="`/jobs/${row.id}`" class="mono">{{ row.id }}</router-link>
            </template>
          </el-table-column>
          <el-table-column label="Stage" min-width="130">
            <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
          </el-table-column>
          <el-table-column label="Progress" width="120">
            <template #default="{ row }">{{ row.progress }}%</template>
          </el-table-column>
          <el-table-column label="Updated" min-width="170">
            <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>

    <section class="reference-grid" aria-label="运维相关入口">
      <router-link to="/system-status">系统状态</router-link>
      <router-link to="/system-status/audit-events">审计日志</router-link>
      <router-link to="/system-status/file-retention">文件保留计划</router-link>
      <router-link :to="failedJobsRoute">失败任务筛选</router-link>
      <router-link :to="runningJobsRoute">运行中任务筛选</router-link>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";

import { documentJobsApi } from "@/api/documentJobs";
import { healthApi } from "@/api/health";
import type { DocumentJobResponse, DocumentJobStage, HealthMetricsResponse, HealthReadyResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatBytes, formatDateTime, jobStageText } from "@/utils/format";

type AlertType = "success" | "warning" | "info" | "error";
type TagType = "success" | "warning" | "danger" | "info";

type DetailItem = {
  label: string;
  value: string;
};

type MetricItem = {
  label: string;
  value: number | string;
};

type OpsStatusView = {
  key: "ok" | "watch" | "needs-attention" | "unknown";
  label: string;
  description: string;
  tagType: TagType;
};

type OpsAlert = {
  key: string;
  title: string;
  description: string;
  alertType: AlertType;
  to?: string | { path: string; query: Record<string, string> };
  linkText?: string;
};

const ready = ref<HealthReadyResponse | null>(null);
const metrics = ref<HealthMetricsResponse | null>(null);
const failedJobs = ref<DocumentJobResponse[]>([]);
const runningJobs = ref<DocumentJobResponse[]>([]);
const failedJobsTotal = ref(0);
const runningJobsTotal = ref(0);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);
const refreshedAt = ref<string | null>(null);

const failedJobsRoute = { path: "/jobs", query: { status: "failed", sort: "updated_at_desc" } };
const runningJobsRoute = { path: "/jobs", query: { status: "running", sort: "updated_at_desc" } };

const checks = computed<Record<string, unknown>>(() => ready.value?.dependency_checks ?? {});
const blockers = computed(() => stringListCheck("readiness_blockers"));
const warnings = computed(() => stringListCheck("readiness_warnings"));
const workerMode = computed(() => metrics.value?.worker_mode || stringCheck("worker_mode"));
const stageDispatcher = computed(() => metrics.value?.stage_dispatcher || stringCheck("stage_dispatcher"));
const stageFailedCount = computed(() => stageCount("failed"));
const stageRunningCount = computed(() => stageCount("running"));
const stagePendingCount = computed(() => stageCount("pending"));
const staleRunningCount = computed(() => numberCheck("stage_spool_running_stale_messages") ?? 0);
const replayableCount = computed(() => numberCheck("stage_spool_replayable_messages") ?? 0);

const queuePressureLabel = computed(() => {
  const total = stagePendingCount.value + stageRunningCount.value + stageFailedCount.value;
  if (total === 0 && staleRunningCount.value === 0 && replayableCount.value === 0) {
    return "clear";
  }
  return `${total} messages`;
});

const opsStatus = computed<OpsStatusView>(() => {
  if (!ready.value && !metrics.value) {
    return {
      key: "unknown",
      label: "unknown",
      description: "尚未取得运维状态。",
      tagType: "info",
    };
  }
  if (blockers.value.length > 0 || stageFailedCount.value > 0 || staleRunningCount.value > 0) {
    return {
      key: "needs-attention",
      label: "needs attention",
      description: "存在阻断项、失败 stage message 或 stale running message。",
      tagType: "danger",
    };
  }
  if (warnings.value.length > 0 || replayableCount.value > 0 || failedJobsTotal.value > 0 || runningJobsTotal.value > 0) {
    return {
      key: "watch",
      label: "watch",
      description: "核心链路未阻断，但存在需要持续观察的运行信号。",
      tagType: "warning",
    };
  }
  return {
    key: "ok",
    label: "ok",
    description: "当前未发现 readiness 或队列风险信号。",
    tagType: "success",
  };
});

const staleRunningGuidance = computed(() => {
  if (workerMode.value === "external") {
    return "external worker 模式下，应先确认独立 worker 进程是否存活，再结合任务事件判断是否需要后续处理。";
  }
  return "in_process 模式下，stale running 可能来自进程退出残留；先查看任务详情和系统状态，必要时按现有部署流程处理。";
});

const alertItems = computed<OpsAlert[]>(() => {
  const items: OpsAlert[] = [];
  if (blockers.value.length > 0) {
    items.push({
      key: "readiness-blockers",
      title: `Readiness blockers: ${blockers.value.length}`,
      description: blockers.value.join("、"),
      alertType: "error",
      to: "/system-status",
      linkText: "查看系统状态",
    });
  }
  if (warnings.value.length > 0) {
    items.push({
      key: "readiness-warnings",
      title: `Readiness warnings: ${warnings.value.length}`,
      description: warnings.value.join("、"),
      alertType: "warning",
      to: "/system-status",
      linkText: "查看 readiness 详情",
    });
  }
  if (stageFailedCount.value > 0) {
    items.push({
      key: "stage-failed",
      title: `Failed stage messages: ${stageFailedCount.value}`,
      description: "failed stage message 不会自动 replay，需结合任务详情事件和既有 retry 流程判断下一步。",
      alertType: "error",
      to: failedJobsRoute,
      linkText: "查看失败任务",
    });
  }
  if (staleRunningCount.value > 0) {
    items.push({
      key: "stale-running",
      title: `Stale running messages: ${staleRunningCount.value}`,
      description: staleRunningGuidance.value,
      alertType: "error",
      to: runningJobsRoute,
      linkText: "查看运行中任务",
    });
  }
  if (replayableCount.value > 0) {
    items.push({
      key: "replayable",
      title: `Replayable messages: ${replayableCount.value}`,
      description: "pending/running stage message 属于可恢复观察项；外部 worker 或服务重启可能继续处理，仍需结合任务事件确认进展。",
      alertType: "warning",
      to: runningJobsRoute,
      linkText: "查看运行中任务",
    });
  }
  if (failedJobsTotal.value > 0) {
    items.push({
      key: "failed-jobs",
      title: `Failed document jobs: ${failedJobsTotal.value}`,
      description: "失败任务应从任务详情查看错误阶段、事件流和文件区，再决定是否按既有任务流程重试。",
      alertType: "warning",
      to: failedJobsRoute,
      linkText: "查看失败任务",
    });
  }
  if (runningJobsTotal.value > 0) {
    items.push({
      key: "running-jobs",
      title: `Running document jobs: ${runningJobsTotal.value}`,
      description: "运行中任务样例只用于观察，不代表需要人工干预。",
      alertType: "info",
      to: runningJobsRoute,
      linkText: "查看运行中任务",
    });
  }
  return items;
});

const queueMetricItems = computed<MetricItem[]>(() => [
  { label: "stage pending", value: stagePendingCount.value },
  { label: "stage running", value: stageRunningCount.value },
  { label: "stage failed", value: stageFailedCount.value },
  { label: "stale running", value: staleRunningCount.value },
  { label: "replayable", value: replayableCount.value },
  { label: "oldest running age", value: secondsLabel(numberCheck("stage_spool_oldest_running_age_seconds")) },
  { label: "observation", value: stringCheck("stage_spool_observation_status") },
]);

const runtimeItems = computed<DetailItem[]>(() => [
  { label: "app_name", value: ready.value?.app_name || metrics.value?.app_name || "not reported" },
  { label: "metadata_store", value: metrics.value?.metadata_store || stringCheck("effective_repository_backend") },
  { label: "configured_repository", value: stringCheck("configured_repository_backend") },
  { label: "artifact_storage", value: metrics.value?.artifact_storage || stringCheck("artifact_storage") },
  { label: "artifact_root_writable", value: booleanLabel(booleanCheck("artifact_root_writable")) },
  { label: "artifact_disk_free", value: formatOptionalBytes(numberCheck("artifact_disk_free_bytes")) },
  { label: "stage_message_store", value: stringCheck("stage_message_store") },
  { label: "last_refreshed", value: formatDateTime(refreshedAt.value) },
]);

const resourceItems = computed<DetailItem[]>(() => [
  { label: "default_template_version", value: resourceValue("default_template_version") },
  { label: "default_term_rule_version", value: resourceValue("default_term_rule_version") },
  { label: "default_translation_profile_version", value: resourceValue("default_translation_profile_version") },
  { label: "template_versions", value: resourceValue("template_versions") },
  { label: "term_rule_set_versions", value: resourceValue("term_rule_set_versions") },
  { label: "translation_profile_versions", value: resourceValue("translation_profile_versions") },
]);

// 读取看板需要的所有只读数据。
async function loadDashboard(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [readyResponse, metricsResponse, failedResponse, runningResponse] = await Promise.all([
      healthApi.getReady(),
      healthApi.getMetrics(),
      documentJobsApi.list({
        page: 1,
        page_size: 5,
        status: "failed",
        sort: "updated_at_desc",
        include_archived: false,
      }),
      documentJobsApi.list({
        page: 1,
        page_size: 5,
        status: "running",
        sort: "updated_at_desc",
        include_archived: false,
      }),
    ]);
    ready.value = readyResponse;
    metrics.value = metricsResponse;
    failedJobs.value = failedResponse.items;
    failedJobsTotal.value = failedResponse.total;
    runningJobs.value = runningResponse.items;
    runningJobsTotal.value = runningResponse.total;
    refreshedAt.value = new Date().toISOString();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

// 从 readiness dependency_checks 中读取原始字段。
function checkValue(key: string): unknown {
  return checks.value[key];
}

// 将可选字段统一转成界面可读字符串。
function stringCheck(key: string): string {
  return displayValue(checkValue(key));
}

// 读取 readiness 中的字符串列表字段。
function stringListCheck(key: string): string[] {
  const value = checkValue(key);
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
  }
  if (typeof value === "string" && value.trim()) {
    return [value];
  }
  return [];
}

// 读取 readiness 中的布尔字段。
function booleanCheck(key: string): boolean | null {
  const value = checkValue(key);
  return typeof value === "boolean" ? value : null;
}

// 读取 readiness 中的数字字段。
function numberCheck(key: string): number | null {
  const value = checkValue(key);
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

// 将布尔值转成运维界面短标签。
function booleanLabel(value: boolean | null): string {
  if (value === null) {
    return "not reported";
  }
  return value ? "yes" : "no";
}

// 将未知类型的 health 字段转成稳定展示文本。
function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "not reported";
  }
  if (typeof value === "boolean") {
    return booleanLabel(value);
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

// 格式化可选字节数，缺失时保持 not reported。
function formatOptionalBytes(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return formatBytes(value);
}

// 格式化秒数，避免缺失字段显示为 0。
function secondsLabel(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return `${value}s`;
}

// 从 metrics 读取 stage message 状态计数。
function stageCount(status: string): number {
  return metrics.value?.stage_messages[status] ?? 0;
}

// 读取资源字段，优先使用 metrics.resources，缺失再回退到 readiness。
function resourceValue(key: string): string {
  const metricValue = metrics.value?.resources[key];
  if (metricValue !== undefined) {
    return displayValue(metricValue);
  }
  return displayValue(checkValue(key));
}

// 将任务阶段转成中文标签。
function stageLabel(stage: DocumentJobStage): string {
  return jobStageText[stage] || stage;
}

// 汇总失败任务的错误码和错误信息。
function jobErrorSummary(job: DocumentJobResponse): string {
  if (job.error_code && job.error_message) {
    return `${job.error_code}: ${job.error_message}`;
  }
  return job.error_message || job.error_code || "-";
}

onMounted(() => {
  void loadDashboard();
});
</script>

<style scoped lang="scss">
.ops-dashboard-page {
  display: grid;
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 0 2px;
}

.page-kicker {
  margin: 0 0 4px;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  color: #111827;
  font-size: 28px;
  line-height: 1.2;
}

.page-heading p:last-child {
  margin: 8px 0 0;
  color: #667085;
}

.heading-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.summary-grid,
.dashboard-panels,
.job-panels {
  display: grid;
  gap: 14px;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-panels {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.job-panels {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.summary-card {
  display: grid;
  gap: 6px;
  min-height: 118px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.summary-card span,
.summary-card strong,
.summary-card small {
  display: block;
}

.summary-card span {
  color: #667085;
  font-size: 13px;
}

.summary-card strong {
  color: #111827;
  font-size: 22px;
  line-height: 1.2;
}

.summary-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.status-card {
  grid-template-columns: 12px minmax(0, 1fr);
  align-items: start;
}

.status-card strong {
  font-size: 24px;
}

.status-dot {
  width: 10px;
  height: 10px;
  margin-top: 8px;
  border-radius: 999px;
  background: #94a3b8;
}

.status-card.is-ok .status-dot {
  background: #16a34a;
}

.status-card.is-watch .status-dot {
  background: #d97706;
}

.status-card.is-needs-attention .status-dot {
  background: #dc2626;
}

.alert-grid {
  display: grid;
  gap: 12px;
}

.alert-description {
  margin: 0 0 6px;
}

.dashboard-panel,
.job-panel {
  border: 1px solid #d9e2ec;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.section-title {
  margin: 0;
  color: #111827;
  font-size: 18px;
}

.section-subtitle {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.metric-table {
  display: grid;
  gap: 8px;
}

.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.metric-row span {
  color: #475467;
  font-size: 13px;
}

.metric-row strong {
  color: #111827;
  font-size: 15px;
}

.mono {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}

.job-table {
  width: 100%;
}

.reference-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

@media (max-width: 1100px) {
  .summary-grid,
  .dashboard-panels,
  .job-panels {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading,
  .heading-actions,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .dashboard-panels,
  .job-panels {
    grid-template-columns: 1fr;
  }
}
</style>
