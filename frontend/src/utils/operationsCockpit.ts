// File: frontend/src/utils/operationsCockpit.ts
// Purpose: Derive personal operations cockpit access, launch links, and preview rows from existing workbench contracts.
import type { RouteLocationRaw } from "vue-router";

import type {
  DocumentJobIncidentQueueItemResponse,
  DocumentJobIncidentSummaryResponse,
  DocumentJobResponse,
  SavedViewPageKey,
  SavedViewResponse,
  TranslationQaStatus,
} from "@/api/types";
import type { AppAccessContext } from "@/navigation/appShell";
import { getJobSourceFilename, isActiveJobStatus } from "@/utils/format";
import {
  DEFAULT_STALLED_MINUTES,
  INCIDENTS_DEFAULT_SORT,
  TRANSLATION_QA_DEFAULT_SORT,
  jobsSavedViewStateToQuery,
  incidentsSavedViewStateToQuery,
  personalSavedViewToStripItem,
  systemSavedViews,
  translationQaSavedViewStateToQuery,
  type SavedViewState,
  type SavedViewStripItem,
} from "@/utils/savedViews";

export type CockpitSourceKey = SavedViewPageKey;

export type CockpitSourceAccess = Record<CockpitSourceKey, boolean>;

export type OperationsPriorityTone = "danger" | "warning" | "info" | "success";

export type OperationsPriorityItem = {
  id: string;
  source: CockpitSourceKey;
  label: string;
  helper: string;
  count: number | null;
  tone: OperationsPriorityTone;
  to: RouteLocationRaw;
};

export type SavedViewLauncherEntry = {
  pageKey: SavedViewPageKey;
  pageLabel: string;
  view: SavedViewStripItem;
  fallback: boolean;
  to: RouteLocationRaw;
};

export type OperationsPreviewSource = "incident" | "translation_qa" | "job";

export type OperationsPreviewRow = {
  id: string;
  source: OperationsPreviewSource;
  sourceLabel: string;
  tone: OperationsPriorityTone;
  jobId: string;
  jobName: string;
  status: string;
  updatedAt: string;
  suggestedAction: string;
  to: RouteLocationRaw;
  priority: number;
};

export type OperationsPriorityInput = {
  access: CockpitSourceAccess;
  jobSummary?: Record<string, number> | null;
  qaSummary?: Partial<Record<TranslationQaStatus, number>> | null;
  incidentSummary?: DocumentJobIncidentSummaryResponse | null;
  staleActiveCount?: number;
};

export type OperationsPreviewInput = {
  incidentItems?: DocumentJobIncidentQueueItemResponse[];
  qaJobs?: DocumentJobResponse[];
  jobItems?: DocumentJobResponse[];
  nowMs?: number;
  limit?: number;
};

export const COCKPIT_PAGE_LABELS: Record<SavedViewPageKey, string> = {
  jobs: "任务列表",
  translation_qa: "翻译 QA",
  incidents: "异常处理",
};

const QA_STATUS_PRIORITY: Record<TranslationQaStatus, number> = {
  blocked: 2,
  needs_fix: 3,
  unreviewed: 4,
  approved: 9,
};

const ACTIVE_JOB_STATUSES = ["pending", "queued", "running"];
const STALE_ACTIVE_MS = DEFAULT_STALLED_MINUTES * 60 * 1000;

export function cockpitSourceAccess(access: AppAccessContext): CockpitSourceAccess {
  const canReadJobs = access.permissions.includes("document_jobs:read");
  return {
    jobs: canReadJobs,
    incidents: canReadJobs,
    translation_qa: access.permissions.includes("translation_qa:read"),
  };
}

export function hasCockpitSourceAccess(access: CockpitSourceAccess): boolean {
  return access.jobs || access.incidents || access.translation_qa;
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

export function buildSavedViewLauncherEntries(
  pageKey: SavedViewPageKey,
  personalViews: SavedViewResponse[] = [],
): SavedViewLauncherEntry[] {
  const defaultView = personalViews.find((view) => view.is_default && view.page_key === pageKey);
  const views = defaultView ? [personalSavedViewToStripItem(defaultView)] : systemSavedViews[pageKey];
  return views.map((view) => ({
    pageKey,
    pageLabel: COCKPIT_PAGE_LABELS[pageKey],
    view,
    fallback: view.source === "system",
    to: routeForSavedView(view),
  }));
}

export function buildOperationsPriorityItems(input: OperationsPriorityInput): OperationsPriorityItem[] {
  const items: OperationsPriorityItem[] = [];
  if (input.access.incidents) {
    items.push({
      id: "incidents-retryable",
      source: "incidents",
      label: "可重试异常",
      helper: "进入异常队列处理",
      count: input.incidentSummary?.retryable ?? null,
      tone: "danger",
      to: routeForSavedView({
        page_key: "incidents",
        filters: { retryable: true },
        sort: INCIDENTS_DEFAULT_SORT,
      }),
    });
    items.push({
      id: "incidents-stalled",
      source: "incidents",
      label: "停滞异常",
      helper: "按处理优先级定位",
      count: input.incidentSummary?.stalled ?? null,
      tone: "warning",
      to: routeForSavedView({
        page_key: "incidents",
        filters: { stalled_minutes: DEFAULT_STALLED_MINUTES },
        sort: INCIDENTS_DEFAULT_SORT,
      }),
    });
  }
  if (input.access.translation_qa) {
    items.push({
      id: "qa-blocked",
      source: "translation_qa",
      label: "QA 阻塞",
      helper: "先解除证据问题",
      count: input.qaSummary?.blocked ?? null,
      tone: "danger",
      to: routeForSavedView({
        page_key: "translation_qa",
        filters: { translation_qa_status: "blocked" },
        sort: TRANSLATION_QA_DEFAULT_SORT,
      }),
    });
    items.push({
      id: "qa-needs-fix",
      source: "translation_qa",
      label: "QA 需修正",
      helper: "交付前处理",
      count: input.qaSummary?.needs_fix ?? null,
      tone: "warning",
      to: routeForSavedView({
        page_key: "translation_qa",
        filters: { translation_qa_status: "needs_fix" },
        sort: TRANSLATION_QA_DEFAULT_SORT,
      }),
    });
    items.push({
      id: "qa-unreviewed",
      source: "translation_qa",
      label: "QA 待复核",
      helper: "进入下一批复核",
      count: input.qaSummary?.unreviewed ?? null,
      tone: "info",
      to: routeForSavedView({
        page_key: "translation_qa",
        filters: { translation_qa_status: "unreviewed" },
        sort: TRANSLATION_QA_DEFAULT_SORT,
      }),
    });
  }
  if (input.access.jobs) {
    const activeCount = ACTIVE_JOB_STATUSES.reduce((total, status) => total + (input.jobSummary?.[status] ?? 0), 0);
    const staleCount = input.staleActiveCount ?? 0;
    items.push({
      id: "jobs-failed",
      source: "jobs",
      label: "失败任务",
      helper: "打开失败任务队列",
      count: input.jobSummary?.failed ?? null,
      tone: "danger",
      to: routeForSavedView({
        page_key: "jobs",
        filters: { status: "failed" },
        sort: "updated_at_desc",
      }),
    });
    items.push({
      id: "jobs-active",
      source: "jobs",
      label: staleCount > 0 ? "停滞任务" : "处理中任务",
      helper: staleCount > 0 ? "按最久未更新查看" : "查看进行中任务",
      count: staleCount > 0 ? staleCount : activeCount,
      tone: staleCount > 0 ? "warning" : "success",
      to: routeForSavedView({
        page_key: "jobs",
        filters: { status_group: "active" },
        sort: staleCount > 0 ? "updated_at_asc" : "updated_at_desc",
      }),
    });
  }
  return items;
}

export function buildOperationsPreviewRows(input: OperationsPreviewInput): OperationsPreviewRow[] {
  const nowMs = input.nowMs ?? Date.now();
  const rows = [
    ...(input.incidentItems || []).map((item) => incidentPreviewRow(item)),
    ...(input.qaJobs || []).filter((job) => job.translation_qa_status !== "approved").map((job) => qaPreviewRow(job)),
    ...(input.jobItems || []).filter((job) => job.status === "failed" || isActiveJobStatus(job.status)).map((job) => jobPreviewRow(job, nowMs)),
  ];
  const byJobId = new Map<string, OperationsPreviewRow>();
  for (const row of rows) {
    const current = byJobId.get(row.jobId);
    if (!current || row.priority < current.priority) {
      byJobId.set(row.jobId, row);
    }
  }
  return [...byJobId.values()]
    .sort((left, right) => left.priority - right.priority || timestamp(left.updatedAt) - timestamp(right.updatedAt))
    .slice(0, input.limit ?? 8);
}

export function countStaleActiveJobs(jobs: DocumentJobResponse[], nowMs = Date.now()): number {
  return jobs.filter((job) => isStaleActiveJob(job, nowMs)).length;
}

function incidentPreviewRow(item: DocumentJobIncidentQueueItemResponse): OperationsPreviewRow {
  const filters: SavedViewState["filters"] = {};
  if (item.stalled) {
    filters.stalled_minutes = DEFAULT_STALLED_MINUTES;
  } else if (item.retryable) {
    filters.retryable = true;
  } else if (item.failure_type) {
    filters.failure_type = item.failure_type;
  }
  return {
    id: `incident:${item.job.id}`,
    source: "incident",
    sourceLabel: "异常",
    tone: item.blocked || item.job.status === "failed" ? "danger" : "warning",
    jobId: item.job.id,
    jobName: getJobSourceFilename(item.job),
    status: item.failure_type,
    updatedAt: item.job.updated_at,
    suggestedAction: item.suggested_action || "打开异常诊断",
    to: routeForSavedView({ page_key: "incidents", filters, sort: INCIDENTS_DEFAULT_SORT }, item.job.id),
    priority: item.blocked || item.stalled ? 0 : item.retryable ? 1 : 2,
  };
}

function qaPreviewRow(job: DocumentJobResponse): OperationsPreviewRow {
  return {
    id: `translation_qa:${job.id}`,
    source: "translation_qa",
    sourceLabel: "QA",
    tone: job.translation_qa_status === "blocked" ? "danger" : job.translation_qa_status === "needs_fix" ? "warning" : "info",
    jobId: job.id,
    jobName: getJobSourceFilename(job),
    status: job.translation_qa_status,
    updatedAt: job.updated_at,
    suggestedAction: job.translation_qa_status === "blocked" ? "打开 QA 抽屉解除阻塞" : "打开 QA 抽屉复核",
    to: routeForSavedView(
      {
        page_key: "translation_qa",
        filters: { translation_qa_status: job.translation_qa_status },
        sort: TRANSLATION_QA_DEFAULT_SORT,
      },
      job.id,
    ),
    priority: QA_STATUS_PRIORITY[job.translation_qa_status],
  };
}

function jobPreviewRow(job: DocumentJobResponse, nowMs: number): OperationsPreviewRow {
  const stale = isStaleActiveJob(job, nowMs);
  const failed = job.status === "failed";
  return {
    id: `job:${job.id}`,
    source: "job",
    sourceLabel: "任务",
    tone: failed ? "danger" : stale ? "warning" : "success",
    jobId: job.id,
    jobName: getJobSourceFilename(job),
    status: job.status,
    updatedAt: job.updated_at,
    suggestedAction: failed ? "打开失败任务队列" : stale ? "查看停滞任务" : "查看进行中任务",
    to: routeForSavedView({
      page_key: "jobs",
      filters: failed ? { status: "failed" } : { status_group: "active" },
      sort: stale ? "updated_at_asc" : "updated_at_desc",
    }),
    priority: failed ? 5 : stale ? 6 : 7,
  };
}

function isStaleActiveJob(job: DocumentJobResponse, nowMs: number): boolean {
  if (!isActiveJobStatus(job.status)) {
    return false;
  }
  const updatedAt = timestamp(job.updated_at);
  return Number.isFinite(updatedAt) && nowMs - updatedAt > STALE_ACTIVE_MS;
}

function timestamp(value: string): number {
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
}
