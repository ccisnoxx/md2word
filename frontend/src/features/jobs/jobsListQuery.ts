// 任务列表筛选与 URL query 之间的纯映射；状态读写由 useJobsList 负责。
import type { LocationQuery } from "vue-router";

import type { DocumentJobListSort, DocumentJobStatus, DocumentJobStatusGroup, TranslationQaStatus } from "@/api/types";
import { jobStatusText, translationQaStatusText } from "@/utils/format";
import type { SavedViewState } from "@/utils/savedViews";

export type FilterChipKey = "status" | "status_group" | "translation_qa_status" | "q" | "sort" | "include_archived" | "created_range";
export type WorkQueueKind = "failed" | "stale" | "pending_qa" | "blocked_qa";

export type JobsListFilters = {
  status: DocumentJobStatus | "";
  statusGroup: DocumentJobStatusGroup | "";
  qaStatus: TranslationQaStatus | "";
  q: string;
  sort: DocumentJobListSort;
  includeArchived: boolean;
  createdRange: [string, string] | null;
};

export const statuses: DocumentJobStatus[] = ["pending", "queued", "running", "succeeded", "failed", "canceled"];
export const qaStatuses: TranslationQaStatus[] = ["unreviewed", "approved", "needs_fix", "blocked"];
export const sortOptions: Array<{ label: string; value: DocumentJobListSort }> = [
  { label: "创建时间新到旧", value: "created_at_desc" },
  { label: "创建时间旧到新", value: "created_at_asc" },
  { label: "更新时间新到旧", value: "updated_at_desc" },
  { label: "更新时间旧到新", value: "updated_at_asc" },
];

const JOBS_ROUTE_QUERY_KEYS = [
  "status",
  "status_group",
  "translation_qa_status",
  "sort",
  "include_archived",
  "q",
  "created_from",
  "created_to",
  "page",
];

export function statusLabel(status: string): string {
  return jobStatusText[status as DocumentJobStatus] || status;
}

export function firstQueryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}

function isDocumentJobStatus(value: string): value is DocumentJobStatus {
  return statuses.includes(value as DocumentJobStatus);
}

function isDocumentJobSort(value: string): value is DocumentJobListSort {
  return sortOptions.some((option) => option.value === value);
}

function isDocumentJobStatusGroup(value: string): value is DocumentJobStatusGroup {
  return value === "active";
}

// 校验路由中的 QA 状态筛选值，避免把非法 query 传给后端。
function isTranslationQaStatus(value: string): value is TranslationQaStatus {
  return qaStatuses.includes(value as TranslationQaStatus);
}

// 非法或缺失的 query 值统一回落到默认筛选；status 优先于 status_group。
export function parseJobsRouteQuery(query: LocationQuery): JobsListFilters & { page: number } {
  const nextStatus = firstQueryValue(query.status);
  const nextStatusGroup = firstQueryValue(query.status_group);
  const nextSort = firstQueryValue(query.sort);
  const nextQaStatus = firstQueryValue(query.translation_qa_status);
  const nextPage = Number(firstQueryValue(query.page));
  const createdFrom = firstQueryValue(query.created_from);
  const createdTo = firstQueryValue(query.created_to);
  const status = isDocumentJobStatus(nextStatus) ? nextStatus : "";
  return {
    status,
    statusGroup: status ? "" : isDocumentJobStatusGroup(nextStatusGroup) ? nextStatusGroup : "",
    qaStatus: isTranslationQaStatus(nextQaStatus) ? nextQaStatus : "",
    sort: isDocumentJobSort(nextSort) ? nextSort : "created_at_desc",
    q: firstQueryValue(query.q),
    page: Number.isInteger(nextPage) && nextPage > 0 ? nextPage : 1,
    includeArchived: firstQueryValue(query.include_archived) === "true",
    createdRange: createdFrom && createdTo ? [createdFrom, createdTo] as [string, string] : null,
  };
}

export function buildJobsRouteQuery(filters: JobsListFilters, page: number): Record<string, string> {
  const query: Record<string, string> = {
    sort: filters.sort,
    include_archived: filters.includeArchived ? "true" : "false",
    page: String(page),
  };
  if (filters.status) {
    query.status = filters.status;
  } else if (filters.statusGroup) {
    query.status_group = filters.statusGroup;
  }
  if (filters.qaStatus) {
    query.translation_qa_status = filters.qaStatus;
  }
  if (filters.q.trim()) {
    query.q = filters.q.trim();
  }
  if (filters.createdRange) {
    query.created_from = filters.createdRange[0];
    query.created_to = filters.createdRange[1];
  }
  return query;
}

export function isSameJobsRouteQuery(candidate: LocationQuery, expected: Record<string, string>): boolean {
  return JOBS_ROUTE_QUERY_KEYS.every((key) => firstQueryValue(candidate[key]) === (expected[key] ?? ""));
}

export function hasActiveJobsFilters(filters: JobsListFilters): boolean {
  return Boolean(
    filters.status ||
      filters.statusGroup ||
      filters.qaStatus ||
      filters.q.trim() ||
      filters.includeArchived ||
      filters.createdRange ||
      filters.sort !== "created_at_desc",
  );
}

export function countAdvancedFilters(filters: JobsListFilters): number {
  let count = 0;
  if (filters.sort !== "created_at_desc") {
    count += 1;
  }
  if (filters.includeArchived) {
    count += 1;
  }
  if (filters.createdRange) {
    count += 1;
  }
  return count;
}

export function describeActiveFilters(filters: JobsListFilters): string {
  const statusText = filters.status
    ? statusLabel(filters.status)
    : filters.statusGroup === "active"
      ? "处理中"
      : "全部状态";
  const qaText = filters.qaStatus ? `QA ${translationQaStatusText[filters.qaStatus]}` : "全部 QA";
  const archiveText = filters.includeArchived ? "含归档" : "默认";
  const dateText = filters.createdRange ? `${filters.createdRange[0]} ~ ${filters.createdRange[1]}` : "不限日期";
  return `${statusText} · ${qaText} · ${archiveText} · ${dateText}`;
}

export function buildActiveFilterChips(filters: JobsListFilters): Array<{ key: FilterChipKey; label: string }> {
  const chips: Array<{ key: FilterChipKey; label: string }> = [];
  if (filters.status) {
    chips.push({ key: "status", label: `状态：${statusLabel(filters.status)}` });
  } else if (filters.statusGroup === "active") {
    chips.push({ key: "status_group", label: "状态组：处理中" });
  }
  if (filters.qaStatus) {
    chips.push({ key: "translation_qa_status", label: `QA：${translationQaStatusText[filters.qaStatus]}` });
  }
  if (filters.q.trim()) {
    chips.push({ key: "q", label: `搜索：${filters.q.trim()}` });
  }
  if (filters.includeArchived) {
    chips.push({ key: "include_archived", label: "含归档" });
  }
  if (filters.createdRange) {
    chips.push({ key: "created_range", label: "创建时间已筛选" });
  }
  if (filters.sort !== "created_at_desc") {
    const sortOption = sortOptions.find((option) => option.value === filters.sort);
    chips.push({ key: "sort", label: `排序：${sortOption?.label || filters.sort}` });
  }
  return chips;
}

export function jobsSavedViewState(filters: JobsListFilters): SavedViewState {
  const savedFilters: SavedViewState["filters"] = {};
  if (filters.status) {
    savedFilters.status = filters.status;
  } else if (filters.statusGroup) {
    savedFilters.status_group = filters.statusGroup;
  }
  if (filters.qaStatus) {
    savedFilters.translation_qa_status = filters.qaStatus;
  }
  if (filters.q.trim()) {
    savedFilters.q = filters.q.trim();
  }
  if (filters.includeArchived) {
    savedFilters.include_archived = true;
  }
  if (filters.createdRange) {
    savedFilters.created_from = filters.createdRange[0];
    savedFilters.created_to = filters.createdRange[1];
  }
  return {
    filters: savedFilters,
    sort: filters.sort,
  };
}
