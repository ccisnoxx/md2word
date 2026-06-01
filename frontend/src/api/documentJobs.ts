// frontend/src/api/documentJobs.ts: document_jobs API wrappers used by workbench pages.
import { apiRequest } from "@/api/client";
import type {
  DocumentJobCreateRequest,
  DocumentJobCreateResponse,
  DocumentJobDownloadUrlResponse,
  DocumentJobEventListResponse,
  DocumentJobListResponse,
  DocumentJobResponse,
  DocumentJobRetryResponse,
} from "@/api/types";

export type DocumentJobListParams = {
  page: number;
  page_size: number;
  status?: string;
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

  retry(jobId: string, reason?: string): Promise<DocumentJobRetryResponse> {
    return apiRequest<DocumentJobRetryResponse>({
      url: `/api/v1/document-jobs/${jobId}/retry`,
      method: "POST",
      data: { reason: reason || null },
    });
  },

  createDownloadUrl(jobId: string): Promise<DocumentJobDownloadUrlResponse> {
    return apiRequest<DocumentJobDownloadUrlResponse>({
      url: `/api/v1/document-jobs/${jobId}/download-url`,
      method: "GET",
    });
  },
};
