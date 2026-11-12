// 运维看板的无状态映射：类型、Phase 7 pilot 常量、标签映射与展示格式化。
import type {
  DocumentJobResponse,
  DocumentJobStage,
  HealthOpsAlertItem,
  HealthOpsStatus,
  OpsAlertDestinationStatus,
  OpsAlertDeliveryAdapterResultResponse,
  OpsAlertDeliveryOutcome,
  OpsIntegrationCapabilityStatus,
  OpsProviderCancellationOutcome,
  OpsRecoveryActionResponse,
} from "@/api/types";
import { formatBytes, jobStageText } from "@/utils/format";

export type TagType = "success" | "warning" | "danger" | "info";

export type AlertType = "success" | "warning" | "info" | "error";

export type DetailItem = {
  label: string;
  value: string;
};

export type MetricItem = {
  label: string;
  value: number | string;
};

export type OpsJobRecoveryAction = "retry" | "cancel" | "archive" | "replay";

export type OpsStatusView = {
  key: "ok" | "watch" | "needs-attention" | "unknown";
  label: string;
  description: string;
  tagType: TagType;
};

export type OpsAlert = {
  key: string;
  title: string;
  description: string;
  alertType: AlertType;
  to?: string | { path: string; query: Record<string, string> };
  linkText?: string;
};

export const REAL_ALERT_DELIVERY_DESTINATION_ID = "ops-slack-primary";

export const REAL_ALERT_DELIVERY_SECRET_REF = "OPS_SLACK_WEBHOOK_URL";

export const REAL_ALERT_DELIVERY_TARGET_LABEL = "#ops-alerts-phase7-pilot";

export const REAL_ALERT_DELIVERY_ALERT_CODE = "stage_spool_failed_messages_present";

export const REAL_ALERT_DELIVERY_CONFIRMATION_PHRASE = "SEND REAL OPS ALERTS";

export const REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES = 60;

export const REAL_ALERT_DELIVERY_RATE_LIMIT_PER_HOUR = 3;

export const REAL_ALERT_DELIVERY_TIMEOUT_SECONDS = 10;

export const failedJobsRoute = { path: "/jobs", query: { status: "failed", sort: "updated_at_desc" } };

export const runningJobsRoute = { path: "/jobs", query: { status: "running", sort: "updated_at_desc" } };

export function jobRecoveryActionId(action: OpsJobRecoveryAction): string {
  if (action === "replay") {
    return "document_job.replay_execution";
  }
  return `document_job.${action}`;
}

export function jobRecoveryActionLabel(action: OpsJobRecoveryAction | null): string {
  if (action === "retry") {
    return "重试";
  }
  if (action === "cancel") {
    return "取消";
  }
  if (action === "archive") {
    return "归档";
  }
  if (action === "replay") {
    return "重放执行";
  }
  return "任务动作";
}

export function jobRecoveryActionKey(jobId: string, action: OpsJobRecoveryAction): string {
  return `${jobId}:${action}`;
}

// 构建 Phase 7 Slack webhook pilot 请求，固定 exact destination 和 alert code。
export function buildRealAlertDeliveryPayload(): { alert_codes: string[]; destination_ids: string[]; dedupe_window_minutes: number } {
  return {
    alert_codes: [REAL_ALERT_DELIVERY_ALERT_CODE],
    destination_ids: [REAL_ALERT_DELIVERY_DESTINATION_ID],
    dedupe_window_minutes: REAL_ALERT_DELIVERY_DEDUPE_WINDOW_MINUTES,
  };
}

// 展示 fake adapter contract 版本和执行模式。
export function adapterResultLabel(adapterResult: OpsAlertDeliveryAdapterResultResponse | null): string {
  if (!adapterResult) {
    return "-";
  }
  return `${adapterResult.contract_version}/${adapterResult.adapter_mode}`;
}

// 将 fake delivery outcome 映射为 Element Plus 标签样式。
export function alertDeliveryOutcomeTag(outcome: OpsAlertDeliveryOutcome): TagType {
  if (outcome === "fake_delivered" || outcome === "deliverable" || outcome === "sent") {
    return "success";
  }
  if (outcome === "deduped" || outcome === "blocked" || outcome === "rate_limited" || outcome.startsWith("skipped_")) {
    return "warning";
  }
  if (outcome === "failed" || outcome === "timed_out") {
    return "danger";
  }
  return "info";
}

// 解析可选 destination IDs，支持逗号和换行分隔并去重。
export function parseAlertDestinationIds(rawValue: string): string[] {
  const values = rawValue
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
  return Array.from(new Set(values));
}

// 将 alert destination dry-run status 映射为 Element Plus 标签样式。
export function alertDestinationStatusTag(status: OpsAlertDestinationStatus): TagType {
  if (status === "dry_run_passed" || status === "config_valid") {
    return "success";
  }
  if (status === "disabled" || status === "blocked") {
    return "warning";
  }
  if (status === "missing_config") {
    return "danger";
  }
  return "info";
}

// 将 integration capability status 映射为 Element Plus 标签样式。
export function integrationCapabilityStatusTag(status: OpsIntegrationCapabilityStatus): TagType {
  if (status === "ready") {
    return "success";
  }
  if (status === "dry_run_only") {
    return "warning";
  }
  return "danger";
}

// 将 provider cancellation outcome 映射为 Element Plus 标签样式。
export function providerCancellationOutcomeTag(outcome: OpsProviderCancellationOutcome): TagType {
  if (outcome === "cancelable" || outcome === "fake_canceled") {
    return "success";
  }
  if (outcome === "deduped" || outcome === "ineligible") {
    return "warning";
  }
  if (outcome === "failed") {
    return "danger";
  }
  return "info";
}

export function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function readBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

// 将布尔值转成运维界面短标签。
export function booleanLabel(value: boolean | null): string {
  if (value === null) {
    return "not reported";
  }
  return value ? "yes" : "no";
}

// 汇总 action 执行 gate，供只读 registry 表格展示。
export function recoveryActionGateSummary(action: OpsRecoveryActionResponse): string {
  const gates = [
    action.requires_admin ? "admin" : null,
    action.requires_reason ? "reason" : null,
    action.requires_confirmation ? "confirmation" : null,
    action.dry_run_supported ? "dry-run" : null,
  ].filter((item): item is string => item !== null);
  return gates.length > 0 ? gates.join(" / ") : "none";
}

// 汇总 action 风险 flags，不代表本页面实际执行这些副作用。
export function recoveryActionRiskSummary(action: OpsRecoveryActionResponse): string {
  const risks = [
    action.mutates_metadata ? "metadata" : null,
    action.mutates_queue ? "queue" : null,
    action.calls_provider ? "provider" : null,
    action.sends_notification ? "notification" : null,
    action.deletes_data ? "delete" : null,
  ].filter((item): item is string => item !== null);
  return risks.length > 0 ? risks.join(" / ") : "none";
}

// 返回 action 可用性标签，候选执行动作必须显示为 unavailable。
export function recoveryActionAvailabilityTag(action: OpsRecoveryActionResponse): { label: string; type: TagType } {
  if (action.available) {
    return { label: "available", type: "success" };
  }
  return { label: "candidate", type: "warning" };
}

// 展示第一条 gap 或建议路由，避免在表格中展开长列表。
export function recoveryActionGapSummary(action: OpsRecoveryActionResponse): string {
  if (action.known_gaps.length > 0) {
    return action.known_gaps[0];
  }
  return action.suggested_route || "no known gap";
}

// 将后端 ops-alerts 状态映射为页面摘要状态。
export function opsStatusFromBackend(status: HealthOpsStatus): OpsStatusView {
  if (status === "needs_attention") {
    return {
      key: "needs-attention",
      label: "needs attention",
      description: "后端只读告警合同发现需要人工关注的阻断或队列风险。",
      tagType: "danger",
    };
  }
  if (status === "watch") {
    return {
      key: "watch",
      label: "watch",
      description: "后端只读告警合同发现需要持续观察的运行信号。",
      tagType: "warning",
    };
  }
  return {
    key: "ok",
    label: "ok",
    description: "后端只读告警合同未发现当前运维风险信号。",
    tagType: "success",
  };
}

// 将后端告警项映射为 Element Plus 可渲染的告警卡片。
export function buildBackendOpsAlert(alert: HealthOpsAlertItem): OpsAlert {
  const route = alert.suggested_route || undefined;
  return {
    key: alert.code,
    title: `${alert.title}: ${alert.count}`,
    description: `${alert.description} 建议：${alert.suggested_action}`,
    alertType: opsAlertType(alert.severity),
    to: route,
    linkText: route ? "查看建议位置" : undefined,
  };
}

// 将后端严重级别映射为前端 alert 类型。
export function opsAlertType(severity: HealthOpsAlertItem["severity"]): AlertType {
  if (severity === "critical") {
    return "error";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
}

// 将后端严重级别映射为 Element Plus 标签类型。
export function opsAlertSeverityTagType(severity: HealthOpsAlertItem["severity"]): TagType {
  if (severity === "critical") {
    return "danger";
  }
  if (severity === "warning") {
    return "warning";
  }
  return "info";
}

// 将未知类型的 health 字段转成稳定展示文本。
export function displayValue(value: unknown): string {
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

// 将安全摘要对象转换为稳定 descriptions 展示项。
export function recordDetailItems(record: Record<string, string | number | boolean | null>): DetailItem[] {
  return Object.entries(record).map(([label, value]) => ({
    label,
    value: displayValue(value),
  }));
}

// 格式化可选字节数，缺失时保持 not reported。
export function formatOptionalBytes(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return formatBytes(value);
}

// 格式化秒数，避免缺失字段显示为 0。
export function secondsLabel(value: number | null): string {
  if (value === null) {
    return "not reported";
  }
  return `${value}s`;
}

// 将任务阶段转成中文标签。
export function stageLabel(stage: DocumentJobStage): string {
  return jobStageText[stage] || stage;
}

// 汇总失败任务的错误码和错误信息。
export function jobErrorSummary(job: DocumentJobResponse): string {
  if (job.error_code && job.error_message) {
    return `${job.error_code}: ${job.error_message}`;
  }
  return job.error_message || job.error_code || "-";
}
