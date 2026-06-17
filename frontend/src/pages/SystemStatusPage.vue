<!-- File: frontend/src/pages/SystemStatusPage.vue -->
<!-- Purpose: Render the Admin-only overview for backend health, metrics, and storage operations. -->
<template>
  <main class="system-status-page" aria-labelledby="system-status-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">系统状态</p>
        <h1 id="system-status-title">系统状态</h1>
        <p>只读查看后端就绪检查、任务工作进程、存储、队列和默认资源状态。</p>
      </div>
      <div class="heading-actions">
        <el-tag :type="readiness.tagType" effect="plain">{{ readiness.label }}</el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="loadStatus">刷新状态</el-button>
      </div>
    </section>

    <ApiErrorAlert :error="error" />

    <section v-loading="loading" class="overview-grid" aria-label="系统状态概览">
      <article class="overview-card readiness-card" :class="`is-${readiness.key}`">
        <span class="status-dot" aria-hidden="true"></span>
        <div>
          <strong>{{ readiness.label }}</strong>
          <small>{{ readiness.description }}</small>
        </div>
      </article>

      <article class="overview-card">
        <span>应用</span>
        <strong>{{ appName }}</strong>
        <small>版本: {{ deploymentVersion }} · 就绪接口: {{ endpointStatus(ready?.status) }}</small>
      </article>

      <article class="overview-card">
        <span>部署</span>
        <strong>{{ deploymentId }}</strong>
        <small>{{ deploymentRuntimeLabel }}</small>
      </article>

      <article class="overview-card">
        <span>指标时间</span>
        <strong>{{ formatDateTime(metrics?.generated_at) }}</strong>
        <small>页面刷新：{{ formatDateTime(refreshedAt) }}</small>
      </article>

      <article class="overview-card">
        <span>审计事件</span>
        <strong>{{ auditEventsTotal }}</strong>
        <small>
          来自 `/api/v1/health/metrics`
          <router-link class="metric-link" to="/system-status/audit-events">查看日志</router-link>
        </small>
      </article>
    </section>

    <section v-if="blockers.length || warnings.length" class="status-alerts" aria-label="就绪检查阻断和告警">
      <el-alert v-if="blockers.length" type="error" title="就绪检查阻断" :closable="false" show-icon>
        <ul class="status-list">
          <li v-for="blocker in blockers" :key="blocker">{{ formatReadinessItem(blocker) }}</li>
        </ul>
      </el-alert>
      <el-alert v-if="warnings.length" type="warning" title="就绪检查告警" :closable="false" show-icon>
        <ul class="status-list">
          <li v-for="warning in warnings" :key="warning">{{ formatReadinessItem(warning) }}</li>
        </ul>
      </el-alert>
    </section>

    <section class="status-panels" aria-label="系统状态详情">
      <el-card class="card-flat status-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">后端</h2>
            <p class="section-subtitle">后端运行态和元数据存储。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in backendItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="card-flat status-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">工作进程</h2>
            <p class="section-subtitle">任务执行模式、阶段调度器和队列存储。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in workerItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card class="card-flat status-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">存储</h2>
            <p class="section-subtitle">产物存储、本地可写性和剩余空间。</p>
          </div>
          <div class="toolbar">
            <router-link to="/system-status/file-retention">文件管理与清理</router-link>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in storageItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>

    <section class="status-panels status-panels-wide" aria-label="任务和资源状态">
      <el-card class="card-flat status-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">任务与队列</h2>
            <p class="section-subtitle">任务状态和阶段消息计数。</p>
          </div>
          <div class="toolbar">
            <router-link to="/system-status/ops-dashboard">运维看板</router-link>
            <router-link :to="{ path: '/jobs', query: { status: 'failed', sort: 'updated_at_desc' } }">
              失败任务
            </router-link>
            <router-link :to="{ path: '/jobs', query: { status: 'running', sort: 'updated_at_desc' } }">
              运行中任务
            </router-link>
          </div>
        </div>
        <div class="metric-table">
          <div v-for="item in jobMetricItems" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <el-divider />
        <div class="metric-table">
          <div v-for="item in stageMetricItems" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
        <el-divider />
        <div class="metric-table">
          <div v-for="item in callbackMetricItems" :key="item.label" class="metric-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-card>

      <el-card class="card-flat status-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">资源版本</h2>
            <p class="section-subtitle">当前默认资源版本；未上报字段会明确标记。</p>
          </div>
        </div>
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item v-for="item in resourceItems" :key="item.label" :label="item.label">
            <span class="mono">{{ item.value }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";

import { healthApi } from "@/api/health";
import type { HealthMetricsResponse, HealthReadyResponse } from "@/api/types";
import ApiErrorAlert from "@/components/ApiErrorAlert.vue";
import { booleanText, commonValueText, healthLabelText, missingText, readinessCodeText } from "@/utils/displayText";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import { formatBytes, formatDateTime, jobStatusText } from "@/utils/format";

type DetailItem = {
  label: string;
  value: string;
};

type MetricItem = {
  label: string;
  value: number | string;
};

type ReadinessView = {
  key: "ready" | "blocked" | "degraded" | "unknown";
  label: string;
  description: string;
  tagType: "success" | "warning" | "danger" | "info";
};

const ready = ref<HealthReadyResponse | null>(null);
const metrics = ref<HealthMetricsResponse | null>(null);
const loading = ref(false);
const error = ref<ApiClientError | null>(null);
const refreshedAt = ref<string | null>(null);

const checks = computed(() => ready.value?.dependency_checks ?? {});
const blockers = computed(() => stringListCheck("readiness_blockers"));
const warnings = computed(() => stringListCheck("readiness_warnings"));
const appName = computed(() => ready.value?.app_name || metrics.value?.app_name || missingText());
const deploymentInfo = computed(() => ready.value?.deployment || metrics.value?.deployment || null);
const deploymentId = computed(() => deploymentInfo.value?.deployment_id || missingText());
const deploymentVersion = computed(() => deploymentInfo.value?.version || missingText());
const deploymentRuntimeLabel = computed(() => {
  const info = deploymentInfo.value;
  if (!info) {
    return missingText();
  }
  return `${commonValueText(info.environment)} · ${commonValueText(info.public_deployment_mode)} · ${formatDateTime(info.started_at)}`;
});
const auditEventsTotal = computed(() => metrics.value?.audit_events.total ?? 0);

const readiness = computed<ReadinessView>(() => {
  const deploymentReady = booleanCheck("deployment_init_ready");
  const needsAttention = booleanCheck("stage_spool_needs_attention");

  if (!ready.value && !metrics.value) {
    return {
      key: "unknown",
      label: "未知",
      description: "尚未取得 health 响应。",
      tagType: "info",
    };
  }
  if (deploymentReady === false || blockers.value.length > 0) {
    return {
      key: "blocked",
      label: "已阻断",
      description: "存在阻断项，默认处理链路不满足最小运行条件。",
      tagType: "danger",
    };
  }
  if (warnings.value.length > 0 || needsAttention === true) {
    return {
      key: "degraded",
      label: "有告警",
      description: "核心 readiness 可用，但存在需要关注的非阻断警告。",
      tagType: "warning",
    };
  }
  if (deploymentReady === true) {
    return {
      key: "ready",
      label: "就绪",
      description: "后端报告已满足最小运行条件。",
      tagType: "success",
    };
  }
  return {
    key: "unknown",
    label: "未知",
    description: "health 响应缺少 deployment readiness 结论。",
    tagType: "info",
  };
});

const backendItems = computed<DetailItem[]>(() => [
  detailItem("app_name", appName.value),
  detailItem("app_version", deploymentInfo.value?.version),
  detailItem("deployment_id", deploymentInfo.value?.deployment_id),
  detailItem("app_env", deploymentInfo.value?.environment),
  detailItem("deployment_started_at", formatDateTime(deploymentInfo.value?.started_at)),
  detailItem("jobs_dir", ready.value?.jobs_dir),
  detailItem("metadata_store", metrics.value?.metadata_store || checkValue("effective_repository_backend")),
  detailItem("configured_repository", checkValue("configured_repository_backend")),
  detailItem("public_deployment_mode", checkValue("public_deployment_mode")),
]);

const workerItems = computed<DetailItem[]>(() => [
  detailItem("worker_mode", metrics.value?.worker_mode || checkValue("worker_mode")),
  detailItem("document_jobs_worker_backend", checkValue("document_jobs_worker_backend")),
  detailItem("document_jobs_celery_queue", checkValue("document_jobs_celery_queue")),
  detailItem("document_jobs_auto_execution", booleanCheck("document_jobs_automatic_execution_enabled")),
  detailItem("p0_document_jobs_required", booleanCheck("p0_document_jobs_required")),
  detailItem("p0_document_jobs_ready", booleanCheck("p0_document_jobs_ready")),
  detailItem("stage_dispatcher", metrics.value?.stage_dispatcher || checkValue("stage_dispatcher")),
  detailItem("stage_message_store", checkValue("stage_message_store")),
  detailItem("stage_spool_available", booleanCheck("stage_spool_dir_exists")),
  detailItem("stage_spool_needs_attention", booleanCheck("stage_spool_needs_attention")),
  detailItem("stage_spool_observation", checkValue("stage_spool_observation_status")),
]);

const storageItems = computed<DetailItem[]>(() => [
  detailItem("artifact_storage", metrics.value?.artifact_storage || checkValue("artifact_storage")),
  detailItem("jobs_dir_writable", booleanCheck("jobs_dir_writable")),
  detailItem("artifact_root_writable", booleanCheck("artifact_root_writable")),
  detailItem("artifact_disk_free", formatOptionalBytes(numberCheck("artifact_disk_free_bytes"))),
  detailItem("tmp_dir_exists", booleanCheck("tmp_dir_exists")),
]);

const jobMetricItems = computed<MetricItem[]>(() => [
  { label: jobStatusText.pending, value: jobCount("pending") },
  { label: jobStatusText.queued, value: jobCount("queued") },
  { label: jobStatusText.running, value: jobCount("running") },
  { label: jobStatusText.succeeded, value: jobCount("succeeded") },
  { label: jobStatusText.failed, value: jobCount("failed") },
  { label: jobStatusText.canceled, value: jobCount("canceled") },
]);

const stageMetricItems = computed<MetricItem[]>(() => [
  { label: healthLabelText("stage_pending"), value: stageCount("pending") },
  { label: healthLabelText("stage_running"), value: stageCount("running") },
  { label: healthLabelText("stage_failed"), value: stageCount("failed") },
  { label: healthLabelText("stale_running"), value: numberCheck("stage_spool_running_stale_messages") ?? 0 },
  { label: healthLabelText("stage_replayable"), value: numberCheck("stage_spool_replayable_messages") ?? 0 },
  { label: healthLabelText("stage_spool_oldest_running_age_seconds"), value: secondsLabel(numberCheck("stage_spool_oldest_running_age_seconds")) },
  { label: healthLabelText("document_jobs_stale"), value: numberCheck("document_jobs_running_stale_count") ?? 0 },
  { label: healthLabelText("document_jobs_timed_out"), value: numberCheck("document_jobs_timed_out_count") ?? 0 },
  { label: healthLabelText("document_jobs_oldest_age"), value: secondsLabel(numberCheck("document_jobs_running_oldest_age_seconds")) },
]);

const callbackMetricItems = computed<MetricItem[]>(() => [
  { label: healthLabelText("document_job_callback_pending_messages"), value: callbackCount("pending") },
  { label: healthLabelText("document_job_callback_running_messages"), value: callbackCount("running") },
  { label: healthLabelText("document_job_callback_failed_messages"), value: callbackCount("failed") },
  { label: healthLabelText("document_job_callback_ignored_messages"), value: callbackCount("ignored") },
  { label: healthLabelText("document_job_callback_replayable_messages"), value: numberCheck("document_job_callback_replayable_messages") ?? 0 },
  {
    label: healthLabelText("document_job_callback_oldest_replayable_age_seconds"),
    value: secondsLabel(numberCheck("document_job_callback_oldest_replayable_age_seconds")),
  },
]);

const resourceItems = computed<DetailItem[]>(() => [
  detailItem("default_template_version", resourceValue("default_template_version")),
  detailItem("default_term_rule_version", resourceValue("default_term_rule_version")),
  detailItem("default_translation_term_version", resourceValue("default_translation_term_version")),
  detailItem("default_translation_profile_version", resourceValue("default_translation_profile_version")),
  detailItem("template_versions", resourceValue("template_versions")),
  detailItem("term_rule_set_versions", resourceValue("term_rule_set_versions")),
  detailItem("translation_profile_versions", resourceValue("translation_profile_versions")),
]);

async function loadStatus(): Promise<void> {
  loading.value = true;
  error.value = null;
  try {
    const [readyResponse, metricsResponse] = await Promise.all([healthApi.getReady(), healthApi.getMetrics()]);
    ready.value = readyResponse;
    metrics.value = metricsResponse;
    refreshedAt.value = new Date().toISOString();
  } catch (caught) {
    error.value = normalizeApiError(caught);
  } finally {
    loading.value = false;
  }
}

function checkValue(key: string): unknown {
  return checks.value[key];
}

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

function booleanCheck(key: string): boolean | null {
  const value = checkValue(key);
  return typeof value === "boolean" ? value : null;
}

function numberCheck(key: string): number | null {
  const value = checkValue(key);
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function detailItem(key: string, value: unknown): DetailItem {
  return {
    label: healthLabelText(key),
    value: displayValue(value),
  };
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return missingText();
  }
  if (typeof value === "boolean") {
    return booleanText(value);
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (typeof value === "string") {
    return commonValueText(value);
  }
  return JSON.stringify(value);
}

function formatOptionalBytes(value: number | null): string {
  if (value === null) {
    return missingText();
  }
  return formatBytes(value);
}

function secondsLabel(value: number | null): string {
  if (value === null) {
    return missingText();
  }
  return `${value} 秒`;
}

function jobCount(status: string): number {
  return metrics.value?.document_jobs?.[status] ?? metrics.value?.jobs[status] ?? 0;
}

function stageCount(status: string): number {
  return metrics.value?.stage_messages[status] ?? 0;
}

function callbackCount(status: string): number {
  return metrics.value?.document_job_callback_messages?.[status] ?? 0;
}

function resourceValue(key: string): string {
  const metricValue = metrics.value?.resources[key];
  if (metricValue !== undefined) {
    return displayValue(metricValue);
  }
  return displayValue(checkValue(key));
}

function endpointStatus(status: string | undefined): string {
  return displayValue(status);
}

function formatReadinessItem(code: string): string {
  return readinessCodeText(code);
}

onMounted(() => {
  void loadStatus();
});
</script>

<style scoped lang="scss">
.system-status-page {
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

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.overview-card {
  display: grid;
  gap: 6px;
  min-height: 118px;
  padding: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
}

.overview-card span,
.overview-card strong,
.overview-card small {
  display: block;
}

.overview-card span {
  color: #667085;
  font-size: 13px;
}

.overview-card strong {
  color: #111827;
  font-size: 22px;
  line-height: 1.2;
}

.overview-card small {
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.metric-link {
  display: inline-block;
  margin-left: 8px;
}

.readiness-card {
  grid-template-columns: 12px minmax(0, 1fr);
  align-items: start;
}

.readiness-card strong {
  font-size: 24px;
}

.status-dot {
  width: 10px;
  height: 10px;
  margin-top: 8px;
  border-radius: 999px;
  background: #94a3b8;
}

.readiness-card.is-ready .status-dot {
  background: #16a34a;
}

.readiness-card.is-degraded .status-dot {
  background: #d97706;
}

.readiness-card.is-blocked .status-dot {
  background: #dc2626;
}

.status-alerts {
  display: grid;
  gap: 12px;
}

.status-list {
  margin: 6px 0 0;
  padding-left: 18px;
}

.status-panels {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.status-panels-wide {
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
}

.status-panel {
  border: 1px solid #d9e2ec;
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

@media (max-width: 920px) {
  .overview-grid,
  .status-panels,
  .status-panels-wide {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .overview-grid,
  .status-panels,
  .status-panels-wide {
    grid-template-columns: 1fr;
  }
}
</style>
