// 运维看板快照 owner：并行读取 readiness、metrics、ops alerts、集成能力、恢复动作、合同与任务样例，并提供 readiness 字段读取与派生计数。
import { computed, ref } from "vue";

import { documentJobsApi } from "@/api/documentJobs";
import { healthApi } from "@/api/health";
import { opsAlertDeliveriesApi } from "@/api/opsAlertDeliveries";
import { opsIntegrationCapabilitiesApi } from "@/api/opsIntegrationCapabilities";
import { opsProviderCancellationsApi } from "@/api/opsProviderCancellations";
import { opsRecoveryActionsApi } from "@/api/opsRecoveryActions";
import { opsS3DeletionsApi } from "@/api/opsS3Deletions";
import type {
  DocumentJobResponse,
  HealthMetricsResponse,
  HealthOpsAlertsResponse,
  HealthReadyResponse,
  OpsAlertDeliveryAdapterContractResponse,
  OpsIntegrationControlPlaneResponse,
  OpsProviderCancellationSemanticsResponse,
  OpsRecoveryActionResponse,
  OpsS3DeleteAdapterContractResponse,
} from "@/api/types";
import { normalizeApiError, type ApiClientError } from "@/utils/errors";
import {
  type TagType,
  type DetailItem,
  booleanLabel,
  displayValue,
} from "./opsDashboardFormat";

export function useOpsDashboardData(
  // 快照加载后让告警投递 owner 修剪已不再 active 的选择。
  options: { onActiveAlertCodesLoaded: (codes: string[]) => void },
) {
  const ready = ref<HealthReadyResponse | null>(null);
  const metrics = ref<HealthMetricsResponse | null>(null);
  const opsAlerts = ref<HealthOpsAlertsResponse | null>(null);
  const integrationCapabilities = ref<OpsIntegrationControlPlaneResponse | null>(null);
  const recoveryActions = ref<OpsRecoveryActionResponse[]>([]);
  const recoveryActionsGeneratedAt = ref<string | null>(null);
  const recoveryActionsReadOnly = ref<boolean | null>(null);
  const failedJobs = ref<DocumentJobResponse[]>([]);
  const runningJobs = ref<DocumentJobResponse[]>([]);
  const failedJobsTotal = ref(0);
  const runningJobsTotal = ref(0);
  const loading = ref(false);
  const error = ref<ApiClientError | null>(null);
  const refreshedAt = ref<string | null>(null);
  const alertDeliveryContract = ref<OpsAlertDeliveryAdapterContractResponse | null>(null);
  const s3DeleteContract = ref<OpsS3DeleteAdapterContractResponse | null>(null);
  const providerCancellationSemantics = ref<OpsProviderCancellationSemanticsResponse | null>(null);
  const checks = computed<Record<string, unknown>>(() => ready.value?.dependency_checks ?? {});
  const blockers = computed(() => stringListCheck("readiness_blockers"));
  const warnings = computed(() => stringListCheck("readiness_warnings"));
  const workerMode = computed(() => metrics.value?.worker_mode || stringCheck("worker_mode"));
  const documentJobsWorkerBackend = computed(() => stringCheck("document_jobs_worker_backend"));
  const p0DocumentJobsRequired = computed(() => booleanCheck("p0_document_jobs_required"));
  const p0DocumentJobsReady = computed(() => booleanCheck("p0_document_jobs_ready"));

  const p0DocumentJobsLabel = computed(() => {
    if (p0DocumentJobsReady.value === null) {
      return "not reported";
    }
    return p0DocumentJobsReady.value ? "ready" : "blocked";
  });

  const stageDispatcher = computed(() => metrics.value?.stage_dispatcher || stringCheck("stage_dispatcher"));
  const stageFailedCount = computed(() => stageCount("failed"));
  const stageRunningCount = computed(() => stageCount("running"));
  const stagePendingCount = computed(() => stageCount("pending"));
  const staleRunningCount = computed(() => numberCheck("stage_spool_running_stale_messages") ?? 0);
  const replayableCount = computed(() => numberCheck("stage_spool_replayable_messages") ?? 0);
  const callbackPendingCount = computed(() => callbackCount("pending"));
  const callbackRunningCount = computed(() => callbackCount("running"));
  const callbackFailedCount = computed(() => callbackCount("failed"));

  const callbackReplayableCount = computed(() => (
    numberCheck("document_job_callback_replayable_messages")
    ?? callbackPendingCount.value + callbackRunningCount.value
  ));

  const callbackOldestReplayableAge = computed(() => numberCheck("document_job_callback_oldest_replayable_age_seconds"));
  const activeOpsAlerts = computed(() => opsAlerts.value?.alerts ?? []);
  const activeOpsAlertCodes = computed(() => activeOpsAlerts.value.map((alert) => alert.code));
  const integrationCapabilityRows = computed(() => integrationCapabilities.value?.capabilities ?? []);

  const readyIntegrationCapabilityCount = computed(() => (
    integrationCapabilityRows.value.filter((capability) => capability.ready).length
  ));

  const blockedIntegrationCapabilityCount = computed(() => (
    integrationCapabilityRows.value.filter((capability) => capability.status === "blocked").length
  ));

  const integrationOverallStatusTag = computed<TagType>(() => {
    if (integrationCapabilities.value?.overall_status === "ready") {
      return "success";
    }
    if (integrationCapabilities.value?.overall_status === "partial") {
      return "warning";
    }
    return "danger";
  });

  const integrationSafetyItems = computed<DetailItem[]>(() => {
    const safety = integrationCapabilities.value?.safety;
    if (!safety) {
      return [];
    }
    return [
      { label: "read_only", value: booleanLabel(safety.read_only) },
      { label: "provider_calls", value: booleanLabel(safety.provider_calls_executed) },
      { label: "external_delivery", value: booleanLabel(safety.external_delivery_executed) },
      { label: "s3_delete", value: booleanLabel(safety.s3_delete_executed) },
      { label: "scheduler", value: booleanLabel(safety.cleanup_scheduler_executed) },
      { label: "quota_enforcement", value: booleanLabel(safety.quota_enforcement_executed) },
      { label: "audit_events", value: booleanLabel(safety.audit_events_written) },
      { label: "secret_values", value: booleanLabel(safety.secret_values_exposed) },
    ];
  });

  const recoveryActionSummary = computed(() => {
    const available = recoveryActions.value.filter((item) => item.available).length;
    const unavailable = recoveryActions.value.length - available;
    return `${available} available · ${unavailable} candidate`;
  });

  // 读取看板需要的所有只读数据。
  async function loadDashboard(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [
        readyResponse,
        metricsResponse,
        opsAlertsResponse,
        integrationCapabilitiesResponse,
        recoveryActionsResponse,
        alertDeliveryContractResponse,
        s3DeleteContractResponse,
        providerCancellationSemanticsResponse,
        failedResponse,
        runningResponse,
      ] = await Promise.all([
        healthApi.getReady(),
        healthApi.getMetrics(),
        healthApi.getOpsAlerts(),
        opsIntegrationCapabilitiesApi.get(),
        opsRecoveryActionsApi.list(),
        opsAlertDeliveriesApi.getAdapterContract(),
        opsS3DeletionsApi.getAdapterContract(),
        opsProviderCancellationsApi.getSemanticsVerification(),
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
      opsAlerts.value = opsAlertsResponse;
      integrationCapabilities.value = integrationCapabilitiesResponse;
      alertDeliveryContract.value = alertDeliveryContractResponse;
      s3DeleteContract.value = s3DeleteContractResponse;
      providerCancellationSemantics.value = providerCancellationSemanticsResponse;
      options.onActiveAlertCodesLoaded(opsAlertsResponse.alerts.map((alert) => alert.code));
      recoveryActions.value = recoveryActionsResponse.actions;
      recoveryActionsGeneratedAt.value = recoveryActionsResponse.generated_at;
      recoveryActionsReadOnly.value = recoveryActionsResponse.safety.read_only;
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

  function callbackCount(status: string): number {
    return metrics.value?.document_job_callback_messages?.[status]
      ?? numberCheck(`document_job_callback_${status}_messages`)
      ?? 0;
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

  return {
    ready,
    metrics,
    opsAlerts,
    integrationCapabilities,
    recoveryActions,
    recoveryActionsGeneratedAt,
    recoveryActionsReadOnly,
    failedJobs,
    runningJobs,
    failedJobsTotal,
    runningJobsTotal,
    loading,
    error,
    refreshedAt,
    alertDeliveryContract,
    s3DeleteContract,
    providerCancellationSemantics,
    checks,
    blockers,
    warnings,
    workerMode,
    documentJobsWorkerBackend,
    p0DocumentJobsRequired,
    p0DocumentJobsReady,
    p0DocumentJobsLabel,
    stageDispatcher,
    stageFailedCount,
    stageRunningCount,
    stagePendingCount,
    staleRunningCount,
    replayableCount,
    callbackPendingCount,
    callbackRunningCount,
    callbackFailedCount,
    callbackReplayableCount,
    callbackOldestReplayableAge,
    activeOpsAlerts,
    activeOpsAlertCodes,
    integrationCapabilityRows,
    readyIntegrationCapabilityCount,
    blockedIntegrationCapabilityCount,
    integrationOverallStatusTag,
    integrationSafetyItems,
    recoveryActionSummary,
    loadDashboard,
    checkValue,
    stringCheck,
    stringListCheck,
    booleanCheck,
    numberCheck,
    callbackCount,
    stageCount,
    resourceValue,
  };
}

export type OpsDashboardData = ReturnType<typeof useOpsDashboardData>;
