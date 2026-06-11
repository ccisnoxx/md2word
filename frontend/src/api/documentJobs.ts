// File: frontend/src/api/documentJobs.ts
// Purpose: Provide document_jobs API wrappers used by workbench pages.
import { apiRequest } from "@/api/client";
import type {
  DocumentJobBulkJobIdsRequest,
  DocumentJobBulkResponse,
  DocumentJobCallbackMessageSummaryResponse,
  DocumentJobBulkRetryRequest,
  DocumentJobCloneRequest,
  DocumentJobCloneResponse,
  DocumentJobCreateRequest,
  DocumentJobCreateResponse,
  DocumentJobArchiveResponse,
  DocumentJobCancelResponse,
  DocumentJobConfigSummaryResponse,
  DocumentJobDownloadUrlResponse,
  DocumentJobEventListResponse,
  DocumentJobFileListResponse,
  DocumentJobListResponse,
  DocumentJobListSort,
  DocumentJobRetryRequest,
  DocumentJobResponse,
  DocumentJobRetryResponse,
  DocumentJobUnarchiveResponse,
  DocumentJobTranslationQaResponse,
  DocumentJobTranslationQaUpdateRequest,
  DocumentJobTranslationQaUpdateResponse,
  TranslationQaStatus,
} from "@/api/types";

export type DocumentJobListParams = {
  page: number;
  page_size: number;
  status?: string;
  translation_qa_status?: TranslationQaStatus;
  q?: string;
  sort?: DocumentJobListSort;
  include_archived?: boolean;
  created_from?: string;
  created_to?: string;
};

export const documentJobsApi = {
  getConfigSummary(): Promise<DocumentJobConfigSummaryResponse> {
    return apiRequest<DocumentJobConfigSummaryResponse>({
      url: "/api/v1/document-jobs/config-summary",
      method: "GET",
    });
  },

  create(payload: DocumentJobCreateRequest): Promise<DocumentJobCreateResponse> {
    return apiRequest<DocumentJobCreateResponse>({
      url: "/api/v1/document-jobs",
      method: "POST",
      data: payload,
    });
  },

  list(params: DocumentJobListParams): Promise<DocumentJobListResponse> {
    return apiRequest<DocumentJobListResponse>({
      url: "/api/v1/document-jobs",
      method: "GET",
      params,
    });
  },

  get(jobId: string): Promise<DocumentJobResponse> {
    return apiRequest<DocumentJobResponse>({
      url: `/api/v1/document-jobs/${jobId}`,
      method: "GET",
    });
  },

  listEvents(jobId: string): Promise<DocumentJobEventListResponse> {
    return apiRequest<DocumentJobEventListResponse>({
      url: `/api/v1/document-jobs/${jobId}/events`,
      method: "GET",
    });
  },

  listFiles(jobId: string): Promise<DocumentJobFileListResponse> {
    return apiRequest<DocumentJobFileListResponse>({
      url: `/api/v1/document-jobs/${jobId}/files`,
      method: "GET",
    });
  },

  getCallbackMessageSummary(jobId: string): Promise<DocumentJobCallbackMessageSummaryResponse> {
    return apiRequest<DocumentJobCallbackMessageSummaryResponse>({
      url: `/api/v1/document-jobs/${jobId}/callback-messages/summary`,
      method: "GET",
    });
  },

  getTranslationQa(jobId: string, limit = 200): Promise<DocumentJobTranslationQaResponse> {
    return apiRequest<DocumentJobTranslationQaResponse>({
      url: `/api/v1/document-jobs/${jobId}/translation-qa`,
      method: "GET",
      params: { limit },
    });
  },

  updateTranslationQa(
    jobId: string,
    payload: DocumentJobTranslationQaUpdateRequest,
  ): Promise<DocumentJobTranslationQaUpdateResponse> {
    return apiRequest<DocumentJobTranslationQaUpdateResponse>({
      url: `/api/v1/document-jobs/${jobId}/translation-qa`,
      method: "PATCH",
      data: payload,
    });
  },

  retry(jobId: string, payload?: string | DocumentJobRetryRequest): Promise<DocumentJobRetryResponse> {
    const data = typeof payload === "string" ? { reason: payload || null } : { reason: null, ...(payload || {}) };
    return apiRequest<DocumentJobRetryResponse>({
      url: `/api/v1/document-jobs/${jobId}/retry`,
      method: "POST",
      data,
    });
  },

  // 批量重试失败任务，后端逐项返回成功和失败结果。
  bulkRetry(payload: DocumentJobBulkRetryRequest): Promise<DocumentJobBulkResponse> {
    return apiRequest<DocumentJobBulkResponse>({
      url: "/api/v1/document-jobs/bulk-retry",
      method: "POST",
      data: payload,
    });
  },

  archive(jobId: string): Promise<DocumentJobArchiveResponse> {
    return apiRequest<DocumentJobArchiveResponse>({
      url: `/api/v1/document-jobs/${jobId}`,
      method: "DELETE",
    });
  },

  // 批量归档终态任务；归档不会删除文件或事件。
  bulkArchive(payload: DocumentJobBulkJobIdsRequest): Promise<DocumentJobBulkResponse> {
    return apiRequest<DocumentJobBulkResponse>({
      url: "/api/v1/document-jobs/bulk-archive",
      method: "POST",
      data: payload,
    });
  },

  cancel(jobId: string): Promise<DocumentJobCancelResponse> {
    return apiRequest<DocumentJobCancelResponse>({
      url: `/api/v1/document-jobs/${jobId}/cancel`,
      method: "POST",
    });
  },

  unarchive(jobId: string): Promise<DocumentJobUnarchiveResponse> {
    return apiRequest<DocumentJobUnarchiveResponse>({
      url: `/api/v1/document-jobs/${jobId}/unarchive`,
      method: "POST",
    });
  },

  clone(jobId: string, payload?: DocumentJobCloneRequest): Promise<DocumentJobCloneResponse> {
    return apiRequest<DocumentJobCloneResponse>({
      url: `/api/v1/document-jobs/${jobId}/clone`,
      method: "POST",
      data: payload || {},
    });
  },

  // 批量取消未终态任务，语义与单任务取消一致。
  bulkCancel(payload: DocumentJobBulkJobIdsRequest): Promise<DocumentJobBulkResponse> {
    return apiRequest<DocumentJobBulkResponse>({
      url: "/api/v1/document-jobs/bulk-cancel",
      method: "POST",
      data: payload,
    });
  },

  createDownloadUrl(jobId: string, fileId?: string): Promise<DocumentJobDownloadUrlResponse> {
    return apiRequest<DocumentJobDownloadUrlResponse>({
      url: `/api/v1/document-jobs/${jobId}/download-url`,
      method: "GET",
      params: fileId ? { file_id: fileId } : undefined,
    });
  },
};
