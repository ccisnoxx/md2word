// File: frontend/src/api/documentJobIncidents.ts
// Purpose: Provide lightweight document_job incident queue API wrappers.
import { apiRequest } from "@/api/client";
import type {
  DocumentJobIncidentBulkRequest,
  DocumentJobIncidentBulkResponse,
  DocumentJobIncidentDiagnosticResponse,
  DocumentJobIncidentFailureType,
  DocumentJobIncidentListResponse,
  DocumentJobIncidentRetryCountBucket,
  DocumentJobIncidentSort,
  DocumentJobStage,
  DocumentJobStatus,
} from "@/api/types";

export type DocumentJobIncidentListParams = {
  page: number;
  page_size: number;
  status?: DocumentJobStatus;
  stage?: DocumentJobStage;
  failure_type?: DocumentJobIncidentFailureType;
  retryable?: boolean;
  retry_count?: DocumentJobIncidentRetryCountBucket;
  stalled_minutes?: number;
  q?: string;
  sort?: DocumentJobIncidentSort;
};

export const documentJobIncidentsApi = {
  list(params: DocumentJobIncidentListParams): Promise<DocumentJobIncidentListResponse> {
    return apiRequest<DocumentJobIncidentListResponse>({
      url: "/api/v1/document-job-incidents",
      method: "GET",
      params,
    });
  },

  getDiagnostics(jobId: string): Promise<DocumentJobIncidentDiagnosticResponse> {
    return apiRequest<DocumentJobIncidentDiagnosticResponse>({
      url: `/api/v1/document-job-incidents/${jobId}/diagnostics`,
      method: "GET",
    });
  },

  bulkRetry(payload: DocumentJobIncidentBulkRequest): Promise<DocumentJobIncidentBulkResponse> {
    return apiRequest<DocumentJobIncidentBulkResponse>({
      url: "/api/v1/document-job-incidents/bulk-retry",
      method: "POST",
      data: payload,
    });
  },

  bulkRefresh(payload: DocumentJobIncidentBulkRequest): Promise<DocumentJobIncidentBulkResponse> {
    return apiRequest<DocumentJobIncidentBulkResponse>({
      url: "/api/v1/document-job-incidents/bulk-refresh",
      method: "POST",
      data: payload,
    });
  },
};
