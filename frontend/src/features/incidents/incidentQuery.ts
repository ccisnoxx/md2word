// 异常队列筛选与 URL query 之间的纯映射及展示标签；状态读写由 useIncidentQueue 负责。
import type { LocationQuery } from "vue-router";

import type {
  DocumentJobIncidentDiagnosticResponse,
  DocumentJobIncidentFailureType,
  DocumentJobIncidentQueueItemResponse,
  DocumentJobIncidentRetryCountBucket,
  DocumentJobIncidentSort,
  DocumentJobStage,
  DocumentJobStatus,
} from "@/api/types";
import { jobStageText, jobStatusText } from "@/utils/format";
import {
  incidentFailureTagType,
  incidentFailureTypeText,
  incidentRetryCountBucketText,
  incidentSortText,
  isDocumentJobIncidentStage,
  isDocumentJobIncidentStatus,
  isIncidentFailureType,
  isIncidentRetryCountBucket,
  isIncidentSort,
} from "@/utils/incidents";
import type { SavedViewState } from "@/utils/savedViews";

export type FilterChipKey = "status" | "stage" | "failure_type" | "retryable" | "retry_count" | "stalled_minutes" | "q" | "sort";
export type SummaryFilter = "stalled" | "failed" | "retryable" | "artifact";

export type IncidentFilters = {
  status: DocumentJobStatus | "";
  stage: DocumentJobStage | "";
  failureType: DocumentJobIncidentFailureType | "";
  retryable: "" | "true" | "false";
  retryCount: DocumentJobIncidentRetryCountBucket | "";
  stalledMinutes: number | null;
  q: string;
  sort: DocumentJobIncidentSort;
};

export const DEFAULT_STALLED_FILTER = 10;
export const statuses: DocumentJobStatus[] = ["pending", "queued", "running", "succeeded", "failed", "canceled"];

const FILTER_QUERY_KEYS = ["status", "stage", "failure_type", "retryable", "retry_count", "stalled_minutes", "q", "sort", "page"];
const ROUTE_QUERY_KEYS = [...FILTER_QUERY_KEYS, "incident_job_id"];

export function firstQueryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

function positivePage(value: string): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

function positiveNumber(value: string): number | null {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

// 非法或缺失的 query 值统一回落到默认筛选；incident_job_id 由诊断抽屉单独读取。
export function parseIncidentRouteQuery(query: LocationQuery): IncidentFilters & { page: number } {
  const routeStatus = firstQueryValue(query.status);
  const routeStage = firstQueryValue(query.stage);
  const routeFailureType = firstQueryValue(query.failure_type);
  const routeRetryable = firstQueryValue(query.retryable);
  const routeRetryCount = firstQueryValue(query.retry_count);
  const routeSort = firstQueryValue(query.sort);
  const routePage = firstQueryValue(query.page);
  return {
    status: isDocumentJobIncidentStatus(routeStatus) ? routeStatus : "",
    stage: isDocumentJobIncidentStage(routeStage) ? routeStage : "",
    failureType: isIncidentFailureType(routeFailureType) ? routeFailureType : "",
    retryable: routeRetryable === "true" || routeRetryable === "false" ? routeRetryable : "",
    retryCount: isIncidentRetryCountBucket(routeRetryCount) ? routeRetryCount : "",
    stalledMinutes: positiveNumber(firstQueryValue(query.stalled_minutes)),
    q: firstQueryValue(query.q),
    sort: isIncidentSort(routeSort) ? routeSort : "priority",
    page: routePage ? positivePage(routePage) : 1,
  };
}

export function buildIncidentRouteQuery(filters: IncidentFilters, page: number, incidentJobId: string | null): Record<string, string> {
  const query: Record<string, string> = {
    page: String(page),
    sort: filters.sort,
  };
  if (filters.status) {
    query.status = filters.status;
  }
  if (filters.stage) {
    query.stage = filters.stage;
  }
  if (filters.failureType) {
    query.failure_type = filters.failureType;
  }
  if (filters.retryable) {
    query.retryable = filters.retryable;
  }
  if (filters.retryCount) {
    query.retry_count = filters.retryCount;
  }
  if (filters.stalledMinutes !== null) {
    query.stalled_minutes = String(filters.stalledMinutes);
  }
  if (filters.q.trim()) {
    query.q = filters.q.trim();
  }
  if (incidentJobId) {
    query.incident_job_id = incidentJobId;
  }
  return query;
}

export function isSameIncidentRouteQuery(candidate: LocationQuery, expected: Record<string, string>): boolean {
  return ROUTE_QUERY_KEYS.every((key) => firstQueryValue(candidate[key]) === (expected[key] ?? ""));
}

// 只比较列表筛选部分；仅 incident_job_id 变化时不重新加载队列。
export function isSameIncidentFilterRouteQuery(left: LocationQuery, right: LocationQuery): boolean {
  return FILTER_QUERY_KEYS.every((key) => firstQueryValue(left[key]) === firstQueryValue(right[key]));
}

export function hasActiveIncidentFilters(filters: IncidentFilters): boolean {
  return Boolean(
    filters.status ||
      filters.stage ||
      filters.failureType ||
      filters.retryable ||
      filters.retryCount ||
      filters.stalledMinutes !== null ||
      filters.q.trim() ||
      filters.sort !== "priority",
  );
}

export function countAdvancedIncidentFilters(filters: IncidentFilters): number {
  let count = 0;
  if (filters.retryCount) {
    count += 1;
  }
  if (filters.stalledMinutes !== null) {
    count += 1;
  }
  if (filters.sort !== "priority") {
    count += 1;
  }
  return count;
}

export function describeIncidentFilters(filters: IncidentFilters): string {
  const statusText = filters.status ? jobStatusText[filters.status] : "全部状态";
  const failureText = filters.failureType ? incidentFailureTypeText[filters.failureType] : "全部失败类型";
  const retryText = filters.retryable === "true" ? "可重试" : filters.retryable === "false" ? "不可重试" : "全部重试性";
  return `${statusText} · ${failureText} · ${retryText}`;
}

export function buildIncidentFilterChips(filters: IncidentFilters): Array<{ key: FilterChipKey; label: string }> {
  const chips: Array<{ key: FilterChipKey; label: string }> = [];
  if (filters.status) {
    chips.push({ key: "status", label: `状态：${jobStatusText[filters.status]}` });
  }
  if (filters.stage) {
    chips.push({ key: "stage", label: `阶段：${jobStageText[filters.stage] || filters.stage}` });
  }
  if (filters.failureType) {
    chips.push({ key: "failure_type", label: `类型：${incidentFailureTypeText[filters.failureType]}` });
  }
  if (filters.retryable) {
    chips.push({ key: "retryable", label: filters.retryable === "true" ? "可重试" : "不可重试" });
  }
  if (filters.retryCount) {
    chips.push({ key: "retry_count", label: `重试：${incidentRetryCountBucketText[filters.retryCount]}` });
  }
  if (filters.stalledMinutes !== null) {
    chips.push({ key: "stalled_minutes", label: `停滞 ≥ ${filters.stalledMinutes} 分钟` });
  }
  if (filters.q.trim()) {
    chips.push({ key: "q", label: `搜索：${filters.q.trim()}` });
  }
  if (filters.sort !== "priority") {
    chips.push({ key: "sort", label: `排序：${incidentSortText[filters.sort]}` });
  }
  return chips;
}

export function incidentSavedViewState(filters: IncidentFilters): SavedViewState {
  const savedFilters: SavedViewState["filters"] = {};
  if (filters.status) {
    savedFilters.status = filters.status;
  }
  if (filters.stage) {
    savedFilters.stage = filters.stage;
  }
  if (filters.failureType) {
    savedFilters.failure_type = filters.failureType;
  }
  if (filters.retryable) {
    savedFilters.retryable = filters.retryable === "true";
  }
  if (filters.retryCount) {
    savedFilters.retry_count = filters.retryCount;
  }
  if (filters.stalledMinutes !== null) {
    savedFilters.stalled_minutes = filters.stalledMinutes;
  }
  if (filters.q.trim()) {
    savedFilters.q = filters.q.trim();
  }
  return {
    filters: savedFilters,
    sort: filters.sort,
  };
}

export function stageLabel(item: DocumentJobIncidentQueueItemResponse): string {
  const stage = item.job.failed_stage || item.job.stage;
  return jobStageText[stage] || stage;
}

export function eventStageLabel(stage: string): string {
  return jobStageText[stage as DocumentJobStage] || stage;
}

export function evidenceLinkTitle(link: DocumentJobIncidentDiagnosticResponse["evidence_links"][number]): string {
  return link.kind === "events" ? "完整事件流" : link.title;
}

export function failureTypeLabel(item: DocumentJobIncidentQueueItemResponse): string {
  return incidentFailureTypeText[item.failure_type];
}

export function failureTypeTagType(item: DocumentJobIncidentQueueItemResponse): "danger" | "warning" | "info" {
  return incidentFailureTagType(item.failure_type);
}
