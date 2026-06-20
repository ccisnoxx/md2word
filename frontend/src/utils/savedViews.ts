// File: frontend/src/utils/savedViews.ts
// Purpose: Shared saved-view state helpers, route builders, and system presets for operations workbenches.
import type { LocationQuery, RouteLocationRaw } from "vue-router";

import type { SavedViewFilters, SavedViewPageKey, SavedViewResponse } from "@/api/types";

export type SavedViewState = {
  filters: SavedViewFilters;
  sort: string;
};

export type SavedViewStripItem = SavedViewState & {
  id: string;
  name: string;
  page_key: SavedViewPageKey;
  source: "system" | "personal";
  is_default?: boolean;
  position?: number;
};

export const JOBS_DEFAULT_SORT = "created_at_desc";
export const TRANSLATION_QA_DEFAULT_SORT = "updated_at_desc";
export const INCIDENTS_DEFAULT_SORT = "priority";
export const DEFAULT_STALLED_MINUTES = 10;

export const SAVED_VIEW_PAGE_LABELS: Record<SavedViewPageKey, string> = {
  jobs: "任务工作台",
  translation_qa: "翻译 QA",
  incidents: "异常处理",
};

const DURABLE_QUERY_KEYS: Record<SavedViewPageKey, string[]> = {
  jobs: ["status", "status_group", "translation_qa_status", "q", "include_archived", "created_from", "created_to", "sort"],
  translation_qa: ["translation_qa_status", "status", "q", "include_archived", "sort"],
  incidents: ["status", "stage", "failure_type", "retryable", "retry_count", "stalled_minutes", "q", "sort"],
};

export const systemSavedViews: Record<SavedViewPageKey, SavedViewStripItem[]> = {
  jobs: [
    {
      id: "system:jobs:active",
      source: "system",
      page_key: "jobs",
      name: "处理中任务",
      filters: { status_group: "active" },
      sort: "updated_at_desc",
    },
    {
      id: "system:jobs:failed",
      source: "system",
      page_key: "jobs",
      name: "失败任务",
      filters: { status: "failed" },
      sort: "updated_at_desc",
    },
    {
      id: "system:jobs:pending-qa",
      source: "system",
      page_key: "jobs",
      name: "待 QA",
      filters: { translation_qa_status: "unreviewed" },
      sort: "updated_at_desc",
    },
    {
      id: "system:jobs:blocked-qa",
      source: "system",
      page_key: "jobs",
      name: "QA 阻塞",
      filters: { translation_qa_status: "blocked" },
      sort: "updated_at_desc",
    },
  ],
  translation_qa: [
    {
      id: "system:translation_qa:unreviewed",
      source: "system",
      page_key: "translation_qa",
      name: "待复核",
      filters: { translation_qa_status: "unreviewed" },
      sort: TRANSLATION_QA_DEFAULT_SORT,
    },
    {
      id: "system:translation_qa:needs-fix",
      source: "system",
      page_key: "translation_qa",
      name: "需修正",
      filters: { translation_qa_status: "needs_fix" },
      sort: TRANSLATION_QA_DEFAULT_SORT,
    },
    {
      id: "system:translation_qa:blocked",
      source: "system",
      page_key: "translation_qa",
      name: "阻塞",
      filters: { translation_qa_status: "blocked" },
      sort: TRANSLATION_QA_DEFAULT_SORT,
    },
    {
      id: "system:translation_qa:approved",
      source: "system",
      page_key: "translation_qa",
      name: "已通过",
      filters: { translation_qa_status: "approved" },
      sort: TRANSLATION_QA_DEFAULT_SORT,
    },
  ],
  incidents: [
    {
      id: "system:incidents:retryable",
      source: "system",
      page_key: "incidents",
      name: "可重试异常",
      filters: { retryable: true },
      sort: INCIDENTS_DEFAULT_SORT,
    },
    {
      id: "system:incidents:stalled",
      source: "system",
      page_key: "incidents",
      name: "停滞优先",
      filters: { stalled_minutes: DEFAULT_STALLED_MINUTES },
      sort: INCIDENTS_DEFAULT_SORT,
    },
    {
      id: "system:incidents:artifact",
      source: "system",
      page_key: "incidents",
      name: "产物缺失",
      filters: { failure_type: "artifact_missing" },
      sort: INCIDENTS_DEFAULT_SORT,
    },
    {
      id: "system:incidents:multiple-retries",
      source: "system",
      page_key: "incidents",
      name: "多次重试",
      filters: { retry_count: "3_plus" },
      sort: "retry_count_desc",
    },
  ],
};

export function personalSavedViewToStripItem(view: SavedViewResponse): SavedViewStripItem {
  return {
    id: view.view_id,
    source: "personal",
    page_key: view.page_key,
    name: view.name,
    filters: canonicalSavedViewFilters(view.filters),
    sort: view.sort,
    is_default: view.is_default,
    position: view.position,
  };
}

export function canonicalSavedViewState(state: SavedViewState): SavedViewState {
  return {
    filters: canonicalSavedViewFilters(state.filters),
    sort: state.sort,
  };
}

export function canonicalSavedViewFilters(filters: SavedViewFilters): SavedViewFilters {
  const entries = Object.entries(filters)
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .sort(([left], [right]) => left.localeCompare(right));
  return Object.fromEntries(entries) as SavedViewFilters;
}

export function areSavedViewStatesEqual(left: SavedViewState, right: SavedViewState): boolean {
  const canonicalLeft = canonicalSavedViewState(left);
  const canonicalRight = canonicalSavedViewState(right);
  return canonicalLeft.sort === canonicalRight.sort && JSON.stringify(canonicalLeft.filters) === JSON.stringify(canonicalRight.filters);
}

export function activeSavedViewId(current: SavedViewState, views: SavedViewStripItem[]): string | null {
  const match = views.find((view) => areSavedViewStatesEqual(current, view));
  return match?.id ?? null;
}

export function hasMeaningfulSavedViewQuery(query: LocationQuery, pageKey: SavedViewPageKey): boolean {
  return DURABLE_QUERY_KEYS[pageKey].some((key) => firstQueryValue(query[key]) !== "");
}

export function jobsSavedViewStateToQuery(state: SavedViewState, page = 1): Record<string, string> {
  const filters = canonicalSavedViewFilters(state.filters);
  const query: Record<string, string> = {
    sort: state.sort,
    include_archived: filters.include_archived === true ? "true" : "false",
    page: String(page),
  };
  copyStringFilter(query, filters, "status");
  copyStringFilter(query, filters, "status_group");
  copyStringFilter(query, filters, "translation_qa_status");
  copyStringFilter(query, filters, "q");
  copyStringFilter(query, filters, "created_from");
  copyStringFilter(query, filters, "created_to");
  return query;
}

export function translationQaSavedViewStateToQuery(
  state: SavedViewState,
  page = 1,
  qaJobId = "",
): Record<string, string> {
  const filters = canonicalSavedViewFilters(state.filters);
  const query: Record<string, string> = {
    translation_qa_status: typeof filters.translation_qa_status === "string" ? filters.translation_qa_status : "all",
    sort: state.sort,
    include_archived: filters.include_archived === true ? "true" : "false",
    page: String(page),
  };
  copyStringFilter(query, filters, "status");
  copyStringFilter(query, filters, "q");
  if (qaJobId) {
    query.qa_job_id = qaJobId;
  }
  return query;
}

export function incidentsSavedViewStateToQuery(
  state: SavedViewState,
  page = 1,
  incidentJobId = "",
): Record<string, string> {
  const filters = canonicalSavedViewFilters(state.filters);
  const query: Record<string, string> = {
    page: String(page),
    sort: state.sort,
  };
  copyStringFilter(query, filters, "status");
  copyStringFilter(query, filters, "stage");
  copyStringFilter(query, filters, "failure_type");
  copyStringFilter(query, filters, "retry_count");
  copyStringFilter(query, filters, "q");
  if (typeof filters.retryable === "boolean") {
    query.retryable = filters.retryable ? "true" : "false";
  }
  if (typeof filters.stalled_minutes === "number") {
    query.stalled_minutes = String(filters.stalled_minutes);
  }
  if (incidentJobId) {
    query.incident_job_id = incidentJobId;
  }
  return query;
}

export function routeForSavedView(view: SavedViewState & { page_key: SavedViewPageKey }, selectedJobId = ""): RouteLocationRaw {
  if (view.page_key === "translation_qa") {
    return {
      name: "translation-qa",
      query: translationQaSavedViewStateToQuery(view, 1, selectedJobId),
    };
  }
  if (view.page_key === "incidents") {
    return {
      name: "incidents",
      query: incidentsSavedViewStateToQuery(view, 1, selectedJobId),
    };
  }
  return {
    name: "jobs",
    query: jobsSavedViewStateToQuery(view, 1),
  };
}

function copyStringFilter(query: Record<string, string>, filters: SavedViewFilters, key: string): void {
  const value = filters[key];
  if (typeof value === "string" && value.trim()) {
    query[key] = value.trim();
  }
}

function firstQueryValue(value: unknown): string {
  if (Array.isArray(value)) {
    return typeof value[0] === "string" ? value[0] : "";
  }
  return typeof value === "string" ? value : "";
}
