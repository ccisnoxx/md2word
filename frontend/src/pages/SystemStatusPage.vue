<!-- File: frontend/src/pages/SystemStatusPage.vue -->
<!-- Purpose: Render the Admin-only overview for backend health, metrics, and storage operations. -->
<template>
  <main class="system-status-page" aria-labelledby="system-status-title">
    <section class="page-heading">
      <div>
        <p class="page-kicker">System Status</p>
        <h1 id="system-status-title">系统状态</h1>
        <p>只读查看后端 readiness、worker、存储、队列和默认资源状态。</p>
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
        <small>ready: {{ ready?.status || "not reported" }} · metrics: {{ metrics?.status || "not reported" }}</small>
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

    <section v-if="blockers.length || warnings.length" class="status-alerts" aria-label="readiness 阻断和警告">
      <el-alert v-if="blockers.length" type="error" title="Readiness blockers" :closable="false" show-icon>
        <ul class="status-list">
          <li v-for="blocker in blockers" :key="blocker">{{ blocker }}</li>
        </ul>
      </el-alert>
      <el-alert v-if="warnings.length" type="warning" title="Readiness warnings" :closable="false" show-icon>
        <ul class="status-list">
          <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
        </ul>
      </el-alert>
    </section>

    <section class="status-panels" aria-label="系统状态详情">
      <el-card class="card-flat status-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Backend</h2>
            <p class="section-subtitle">后端运行态和 metadata store。</p>
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
            <h2 class="section-title">Worker</h2>
            <p class="section-subtitle">worker mode、stage dispatcher 和队列存储。</p>
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
            <h2 class="section-title">Storage</h2>
            <p class="section-subtitle">artifact storage、本地可写性和剩余空间。</p>
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
            <h2 class="section-title">Jobs / Queue</h2>
            <p class="section-subtitle">任务状态和 stage message 计数。</p>
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
      </el-card>

      <el-card class="card-flat status-panel" shadow="never">
        <div class="section-header">
          <div>
            <h2 class="section-title">Resources</h2>
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
const appName = computed(() => ready.value?.app_name || metrics.value?.app_name || "not reported");
const auditEventsTotal = computed(() => metrics.value?.audit_events.total ?? 0);

const readiness = computed<ReadinessView>(() => {
  const deploymentReady = booleanCheck("deployment_init_ready");
  const needsAttention = booleanCheck("stage_spool_needs_attention");

  if (!ready.value && !metrics.value) {
    return {
      key: "unknown",
      label: "unknown",
      description: "尚未取得 health 响应。",
      tagType: "info",
    };
  }
  if (deploymentReady === false || blockers.value.length > 0) {
    return {
      key: "blocked",
      label: "blocked",
      description: "存在阻断项，默认处理链路不满足最小运行条件。",
      tagType: "danger",
    };
  }
  if (warnings.value.length > 0 || needsAttention === true) {
    return {
      key: "degraded",
      label: "degraded",
      description: "核心 readiness 可用，但存在需要关注的非阻断警告。",
      tagType: "warning",
    };
  }
  if (deploymentReady === true) {
    return {
      key: "ready",
      label: "ready",
      description: "后端报告已满足最小运行条件。",
      tagType: "success",
    };
  }
  return {
    key: "unknown",
    label: "unknown",
    description: "health 响应缺少 deployment readiness 结论。",
    tagType: "info",
  };
});

const backendItems = computed<DetailItem[]>(() => [
  { label: "app_name", value: appName.value },
  { label: "jobs_dir", value: ready.value?.jobs_dir || "not reported" },
  { label: "metadata_store", value: metrics.value?.metadata_store || stringCheck("effective_repository_backend") },
  { label: "configured_repository", value: stringCheck("configured_repository_backend") },
  { label: "public_deployment_mode", value: stringCheck("public_deployment_mode") },
]);

const workerItems = computed<DetailItem[]>(() => [
  { label: "worker_mode", value: metrics.value?.worker_mode || stringCheck("worker_mode") },
  { label: "document_jobs_worker_backend", value: stringCheck("document_jobs_worker_backend") },
  { label: "document_jobs_celery_queue", value: stringCheck("document_jobs_celery_queue") },
  { label: "document_jobs_auto_execution", value: booleanLabel(booleanCheck("document_jobs_automatic_execution_enabled")) },
  { label: "p0_document_jobs_required", value: booleanLabel(booleanCheck("p0_document_jobs_required")) },
  { label: "p0_document_jobs_ready", value: booleanLabel(booleanCheck("p0_document_jobs_ready")) },
  { label: "stage_dispatcher", value: metrics.value?.stage_dispatcher || stringCheck("stage_dispatcher") },
  { label: "stage_message_store", value: stringCheck("stage_message_store") },
  { label: "stage_spool_available", value: booleanLabel(booleanCheck("stage_spool_dir_exists")) },
  { label: "stage_spool_needs_attention", value: booleanLabel(booleanCheck("stage_spool_needs_attention")) },
  { label: "stage_spool_observation", value: stringCheck("stage_spool_observation_status") },
]);

const storageItems = computed<DetailItem[]>(() => [
  { label: "artifact_storage", value: metrics.value?.artifact_storage || stringCheck("artifact_storage") },
  { label: "jobs_dir_writable", value: booleanLabel(booleanCheck("jobs_dir_writable")) },
  { label: "artifact_root_writable", value: booleanLabel(booleanCheck("artifact_root_writable")) },
  { label: "artifact_disk_free", value: formatOptionalBytes(numberCheck("artifact_disk_free_bytes")) },
  { label: "tmp_dir_exists", value: booleanLabel(booleanCheck("tmp_dir_exists")) },
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
  { label: "stage pending", value: stageCount("pending") },
  { label: "stage running", value: stageCount("running") },
  { label: "stage failed", value: stageCount("failed") },
  { label: "stale running", value: numberCheck("stage_spool_running_stale_messages") ?? 0 },
  { label: "replayable", value: numberCheck("stage_spool_replayable_messages") ?? 0 },
  { label: "oldest running age", value: secondsLabel(numberCheck("stage_spool_oldest_running_age_seconds")) },
  { label: "document jobs stale", value: numberCheck("document_jobs_running_stale_count") ?? 0 },
  { label: "document jobs timed out", value: numberCheck("document_jobs_timed_out_count") ?? 0 },
  { label: "document jobs oldest age", value: secondsLabel(numberCheck("document_jobs_running_oldest_age_seconds")) },
]);

const resourceItems = computed<DetailItem[]>(() => [
  { label: "default_template_version", value: resourceValue("default_template_version") },
  { label: "default_term_rule_version", value: resourceValue("default_term_rule_version") },
  { label: "default_translation_term_version", value: resourceValue("default_translation_term_version") },
  { label: "default_translation_profile_version", value: resourceValue("default_translation_profile_version") },
  { label: "template_versions", value: resourceValue("template_versions") },
  { label: "term_rule_set_versions", value: resourceValue("term_rule_set_versions") },
  { label: "translation_profile_versions", value: resourceValue("translation_profile_versions") },
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

function stringCheck(key: string): string {
  return displayValue(checkValue(key));
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

function booleanLabel(value: boolean | null): string {
  if (value === null) {
    return "not reported";
  }
  return value ? "yes" : "no";
}

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

function formatOptionalBytes(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return formatBytes(value);
}

function secondsLabel(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return `${value}s`;
}

function jobCount(status: string): number {
  return metrics.value?.jobs[status] ?? 0;
}

function stageCount(status: string): number {
  return metrics.value?.stage_messages[status] ?? 0;
}

function resourceValue(key: string): string {
  const metricValue = metrics.value?.resources[key];
  if (metricValue !== undefined) {
    return displayValue(metricValue);
  }
  return displayValue(checkValue(key));
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
