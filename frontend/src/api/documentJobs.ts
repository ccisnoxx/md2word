// frontend/src/api/documentJobs.ts: document_jobs API wrappers used by workbench pages.
import { apiRequest } from "@/api/client";
import type {
  DocumentJobCreateRequest,
  DocumentJobCreateResponse,
  DocumentJobArchiveResponse,
  DocumentJobCancelResponse,
  DocumentJobDownloadUrlResponse,
  DocumentJobEventListResponse,
  DocumentJobListResponse,
  DocumentJobListSort,
  DocumentJobRetryRequest,
  DocumentJobResponse,
  DocumentJobRetryResponse,
} from "@/api/types";

export type DocumentJobListParams = {
  page: number;
  page_size: number;
  status?: string;
  q?: string;
  sort?: DocumentJobListSort;
  include_archived?: boolean;
  created_from?: string;
  created_to?: string;
};

export const documentJobsApi = {
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

  retry(jobId: string, payload?: string | DocumentJobRetryRequest): Promise<DocumentJobRetryResponse> {
    const data = typeof payload === "string" ? { reason: payload || null } : { reason: null, ...(payload || {}) };
    return apiRequest<DocumentJobRetryResponse>({
      url: `/api/v1/document-jobs/${jobId}/retry`,
      method: "POST",
      data,
    });
  },

  archive(jobId: string): Promise<DocumentJobArchiveResponse> {
    return apiRequest<DocumentJobArchiveResponse>({
      url: `/api/v1/document-jobs/${jobId}`,
      method: "DELETE",
    });
  },

  cancel(jobId: string): Promise<DocumentJobCancelResponse> {
    return apiRequest<DocumentJobCancelResponse>({
      url: `/api/v1/document-jobs/${jobId}/cancel`,
      method: "POST",
    });
  },

  createDownloadUrl(jobId: string): Promise<DocumentJobDownloadUrlResponse> {
    return apiRequest<DocumentJobDownloadUrlResponse>({
      url: `/api/v1/document-jobs/${jobId}/download-url`,
      method: "GET",
    });
  },
};
