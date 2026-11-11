// 运维看板的只读派生视图：摘要指标、整体状态、告警卡片、队列/运行时/资源明细与 S3 delete 合同展示项。
import { computed } from "vue";

import type { WorkbenchMetricItem } from "@/components/WorkbenchMetricStrip.vue";
import { formatDateTime } from "@/utils/format";
import {
  type DetailItem,
  type MetricItem,
  type OpsStatusView,
  type OpsAlert,
  failedJobsRoute,
  runningJobsRoute,
  booleanLabel,
  opsStatusFromBackend,
  buildBackendOpsAlert,
  displayValue,
  formatOptionalBytes,
  secondsLabel,
} from "./opsDashboardFormat";
import type { OpsDashboardData } from "./useOpsDashboardData";

export function useOpsHealthView(
  data: Pick<OpsDashboardData, "ready" | "metrics" | "opsAlerts" | "recoveryActionsGeneratedAt" | "recoveryActionsReadOnly" | "failedJobsTotal" | "runningJobsTotal" | "error" | "refreshedAt" | "s3DeleteContract" | "blockers" | "warnings" | "workerMode" | "documentJobsWorkerBackend" | "p0DocumentJobsRequired" | "p0DocumentJobsReady" | "p0DocumentJobsLabel" | "stageDispatcher" | "stageFailedCount" | "stageRunningCount" | "stagePendingCount" | "staleRunningCount" | "replayableCount" | "callbackPendingCount" | "callbackRunningCount" | "callbackFailedCount" | "callbackReplayableCount" | "callbackOldestReplayableAge" | "stringCheck" | "booleanCheck" | "numberCheck" | "resourceValue">,
) {
  const { ready, metrics, opsAlerts, recoveryActionsGeneratedAt, recoveryActionsReadOnly, failedJobsTotal, runningJobsTotal, error, refreshedAt, s3DeleteContract, blockers, warnings, workerMode, documentJobsWorkerBackend, p0DocumentJobsRequired, p0DocumentJobsReady, p0DocumentJobsLabel, stageDispatcher, stageFailedCount, stageRunningCount, stagePendingCount, staleRunningCount, replayableCount, callbackPendingCount, callbackRunningCount, callbackFailedCount, callbackReplayableCount, callbackOldestReplayableAge, stringCheck, booleanCheck, numberCheck, resourceValue } = data;
  const queuePressureLabel = computed(() => {
    const total = stagePendingCount.value + stageRunningCount.value + stageFailedCount.value;
    if (total === 0 && staleRunningCount.value === 0 && replayableCount.value === 0) {
      return "clear";
    }
    return `${total} messages`;
  });

  const callbackPressureLabel = computed(() => {
    if (callbackReplayableCount.value > 0) {
      return `${callbackReplayableCount.value} replayable`;
    }
    if (callbackFailedCount.value > 0) {
      return `${callbackFailedCount.value} failed`;
    }
    return "clear";
  });

  const overviewItems = computed<WorkbenchMetricItem[]>(() => [
    {
      id: "overall_status",
      label: "整体状态",
      value: opsStatus.value.label,
      helper: opsStatus.value.description,
      statusKey:
        opsStatus.value.key === "needs-attention"
          ? "danger"
          : opsStatus.value.key === "watch"
            ? "warning"
            : opsStatus.value.key === "ok"
              ? "success"
              : opsStatus.value.key,
    },
    {
      id: "worker",
      label: "Worker",
      value: workerMode.value,
      helper: `dispatcher: ${stageDispatcher.value}`,
    },
    {
      id: "p0_jobs",
      label: "P0 jobs",
      value: p0DocumentJobsLabel.value,
      helper: `backend: ${documentJobsWorkerBackend.value} · required ${booleanLabel(p0DocumentJobsRequired.value)}`,
    },
    {
      id: "stage_queue",
      label: "Stage queue",
      value: queuePressureLabel.value,
      helper: `failed ${stageFailedCount.value} · stale ${staleRunningCount.value} · replayable ${replayableCount.value}`,
    },
    {
      id: "callbacks",
      label: "Callbacks",
      value: callbackPressureLabel.value,
      helper: `failed ${callbackFailedCount.value} · replayable ${callbackReplayableCount.value}`,
    },
    {
      id: "document_jobs",
      label: "Document jobs",
      value: `${failedJobsTotal.value} / ${runningJobsTotal.value}`,
      helper: "失败 / 运行中样例来自 document-jobs 只读列表",
    },
  ]);

  const opsStatus = computed<OpsStatusView>(() => {
    if (opsAlerts.value) {
      return opsStatusFromBackend(opsAlerts.value.status);
    }
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
    if (
      warnings.value.length > 0
      || replayableCount.value > 0
      || callbackReplayableCount.value > 0
      || callbackFailedCount.value > 0
      || failedJobsTotal.value > 0
      || runningJobsTotal.value > 0
    ) {
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
    if (opsAlerts.value) {
      return opsAlerts.value.alerts.map(buildBackendOpsAlert);
    }
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
    if (callbackFailedCount.value > 0) {
      items.push({
        key: "callback-failed",
        title: `Failed callback messages: ${callbackFailedCount.value}`,
        description: "失败的 callback message 需要结合任务详情和 replay preview 判断下一步。",
        alertType: "error",
        to: "/system-status/ops-dashboard",
        linkText: "查看运维看板",
      });
    }
    if (callbackReplayableCount.value > 0) {
      items.push({
        key: "callback-replayable",
        title: `Replayable callback messages: ${callbackReplayableCount.value}`,
        description: "pending/running callback message 可随 Worker 恢复或手动 replay 继续处理。",
        alertType: "warning",
        to: "/system-status/ops-dashboard",
        linkText: "查看运维看板",
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
    { label: "callback pending", value: callbackPendingCount.value },
    { label: "callback running", value: callbackRunningCount.value },
    { label: "callback failed", value: callbackFailedCount.value },
    { label: "callback replayable", value: callbackReplayableCount.value },
    { label: "oldest callback age", value: secondsLabel(callbackOldestReplayableAge.value) },
  ]);

  const runtimeItems = computed<DetailItem[]>(() => [
    { label: "app_name", value: ready.value?.app_name || metrics.value?.app_name || "not reported" },
    { label: "metadata_store", value: metrics.value?.metadata_store || stringCheck("effective_repository_backend") },
    { label: "configured_repository", value: stringCheck("configured_repository_backend") },
    { label: "document_jobs_worker_backend", value: documentJobsWorkerBackend.value },
    { label: "document_jobs_auto_execution", value: booleanLabel(booleanCheck("document_jobs_automatic_execution_enabled")) },
    { label: "p0_document_jobs_required", value: booleanLabel(p0DocumentJobsRequired.value) },
    { label: "p0_document_jobs_ready", value: booleanLabel(p0DocumentJobsReady.value) },
    { label: "document_jobs_stale", value: String(numberCheck("document_jobs_running_stale_count") ?? 0) },
    { label: "document_jobs_timed_out", value: String(numberCheck("document_jobs_timed_out_count") ?? 0) },
    { label: "callback_replayable", value: String(callbackReplayableCount.value) },
    { label: "callback_failed", value: String(callbackFailedCount.value) },
    { label: "artifact_storage", value: metrics.value?.artifact_storage || stringCheck("artifact_storage") },
    { label: "artifact_root_writable", value: booleanLabel(booleanCheck("artifact_root_writable")) },
    { label: "artifact_disk_free", value: formatOptionalBytes(numberCheck("artifact_disk_free_bytes")) },
    { label: "stage_message_store", value: stringCheck("stage_message_store") },
    { label: "ops_alerts_generated_at", value: formatDateTime(opsAlerts.value?.generated_at) },
    { label: "ops_alerts_read_only", value: booleanLabel(opsAlerts.value?.safety.read_only ?? null) },
    { label: "recovery_actions_generated_at", value: formatDateTime(recoveryActionsGeneratedAt.value) },
    { label: "recovery_actions_read_only", value: booleanLabel(recoveryActionsReadOnly.value) },
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

  const s3DeleteContractSafetyItems = computed<DetailItem[]>(() => {
    const safety = s3DeleteContract.value?.safety;
    return [
      { label: "read_only", value: booleanLabel(safety?.read_only ?? null) },
      { label: "provider_calls", value: booleanLabel(safety?.provider_calls_executed ?? null) },
      { label: "real_s3_delete", value: booleanLabel(safety?.real_s3_delete_executed ?? null) },
      { label: "localstack_calls", value: booleanLabel(safety?.localstack_calls_executed ?? null) },
      { label: "cleanup", value: booleanLabel(safety?.cleanup_executed ?? null) },
      { label: "scheduler_loop", value: booleanLabel(safety?.scheduler_loop_executed ?? null) },
      { label: "delete", value: booleanLabel(safety?.delete_executed ?? null) },
      { label: "metadata_mutated", value: booleanLabel(safety?.metadata_mutated ?? null) },
      { label: "audit_events", value: booleanLabel(safety?.audit_events_written ?? null) },
      { label: "conversion_workflow", value: booleanLabel(safety?.conversion_workflow_executed ?? null) },
      { label: "secret_values", value: booleanLabel(safety?.secret_values_exposed ?? null) },
    ];
  });

  const s3DeleteLocalStackItems = computed<DetailItem[]>(() => {
    const profile = s3DeleteContract.value?.localstack_profile;
    if (!profile) {
      return [];
    }
    return [
      { label: "harness", value: profile.harness },
      { label: "endpoint_required", value: booleanLabel(profile.endpoint_required) },
      { label: "versioned_bucket_required", value: booleanLabel(profile.versioned_bucket_required) },
      { label: "exact_bucket_key_required", value: booleanLabel(profile.exact_bucket_key_required) },
      { label: "version_id_supported", value: booleanLabel(profile.version_id_supported) },
      { label: "etag_precondition_supported", value: booleanLabel(profile.etag_precondition_supported) },
      { label: "runtime_executed", value: booleanLabel(profile.runtime_executed) },
      { label: "provider_payload_persisted", value: booleanLabel(profile.provider_payload_persisted) },
      { label: "secrets_required", value: booleanLabel(profile.secrets_required_for_contract_report) },
    ];
  });

  const s3DeleteStorageItems = computed<DetailItem[]>(() => (
    Object.entries(s3DeleteContract.value?.storage_config_summary ?? {}).map(([label, value]) => ({
      label,
      value: displayValue(value),
    }))
  ));

  const s3DeleteContractParityItems = computed<DetailItem[]>(() => (
    Object.entries(s3DeleteContract.value?.parity_checks ?? {}).map(([label, value]) => ({
      label,
      value: String(value),
    }))
  ));

  return {
    queuePressureLabel,
    callbackPressureLabel,
    overviewItems,
    opsStatus,
    staleRunningGuidance,
    alertItems,
    queueMetricItems,
    runtimeItems,
    resourceItems,
    s3DeleteContractSafetyItems,
    s3DeleteLocalStackItems,
    s3DeleteStorageItems,
    s3DeleteContractParityItems,
  };
}

export type OpsHealthView = ReturnType<typeof useOpsHealthView>;
