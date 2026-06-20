// File: frontend/src/utils/batchResults.ts
// Purpose: Normalize backend batch operation responses for compact operation result strips.
import type {
  DocumentJobBulkItemResponse,
  DocumentJobBulkResponse,
  DocumentJobIncidentBulkItemResponse,
  DocumentJobIncidentBulkResponse,
} from "@/api/types";

export type NormalizedBatchResultDetail = {
  id: string;
  state: "failed" | "skipped";
  statusCode: number;
  code: string;
  detail: string;
};

export type NormalizedBatchResult = {
  title: string;
  succeeded: number;
  failed: number;
  skipped: number | null;
  total: number;
  details: NormalizedBatchResultDetail[];
};

export function normalizeJobsBatchResult(label: string, result: DocumentJobBulkResponse): NormalizedBatchResult {
  return {
    title: `${label}完成`,
    succeeded: result.succeeded,
    failed: result.failed,
    skipped: null,
    total: result.total,
    details: result.items.filter((item) => !item.ok).map(normalizeJobBatchDetail),
  };
}

export function normalizeIncidentBatchResult(label: string, result: DocumentJobIncidentBulkResponse): NormalizedBatchResult {
  return {
    title: `${label}完成`,
    succeeded: result.succeeded,
    failed: result.failed,
    skipped: result.skipped,
    total: result.total,
    details: result.items.filter((item) => !item.ok || item.skipped).map(normalizeIncidentBatchDetail),
  };
}

function normalizeJobBatchDetail(item: DocumentJobBulkItemResponse): NormalizedBatchResultDetail {
  return {
    id: item.job_id,
    state: "failed",
    statusCode: item.status_code,
    code: item.error_code || String(item.status_code),
    detail: item.detail || "后端未返回失败详情。",
  };
}

function normalizeIncidentBatchDetail(item: DocumentJobIncidentBulkItemResponse): NormalizedBatchResultDetail {
  return {
    id: item.job_id,
    state: item.skipped ? "skipped" : "failed",
    statusCode: item.status_code,
    code: item.error_code || String(item.status_code),
    detail: item.detail || "后端未返回详情。",
  };
}

