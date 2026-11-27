// 文件：frontend/src/api/documentJobs.ts
// 用途：提供工作台使用的 document_jobs API 调用。
import { apiRequest } from "@/api/client";
import type {
  DocumentCurrentReviewResponse,
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
  DocumentJobDeleteExecuteRequest,
  DocumentJobDeleteExecuteResponse,
  DocumentJobDeletePreviewResponse,
  DocumentJobDownloadUrlResponse,
  DocumentJobEventListResponse,
  DocumentJobFileListResponse,
  DocumentJobListResponse,
  DocumentJobListSort,
  DocumentJobNewGenerationRequest,
  DocumentJobNewGenerationResponse,
  DocumentJobStatusGroup,
  DocumentJobTableReferenceListResponse,
  DocumentJobRetryRequest,
  DocumentJobResponse,
  DocumentJobRetryResponse,
  DocumentJobUnarchiveResponse,
  DocumentJobTranslationBatchListResponse,
  DocumentJobTranslationQaResponse,
  DocumentJobTranslationQaUpdateRequest,
  DocumentJobTranslationQaUpdateResponse,
  DocumentPreviewResponse,
  DocumentPublicationDownloadUrlResponse,
  DocumentPublicationsResponse,
  DocumentPublishRequest,
  DocumentPublishResponse,
  DocumentQualityPagesResponse,
  DocumentQualityResponse,
  DocumentQualityTablesResponse,
  DocumentReviewBlockDetailResponse,
  DocumentReviewBlockItemResponse,
  DocumentReviewBlockFlagResponse,
  DocumentReviewBlocksResponse,
  DocumentReviewHistoryResponse,
  DocumentReviewUpdateRequest,
  DocumentReviewUpdateResponse,
  TranslationQaStatus,
} from "@/api/types";

export type DocumentJobListParams = {
  page: number;
  page_size: number;
  status?: string;
  status_group?: DocumentJobStatusGroup;
  translation_qa_status?: TranslationQaStatus | "all";
  q?: string;
  sort?: DocumentJobListSort;
  include_archived?: boolean;
  created_from?: string;
  created_to?: string;
};

export type DocumentReviewBlocksParams = {
  limit?: number;
  cursor?: string;
  source_page_index?: number;
  block_type?: DocumentReviewBlockItemResponse["block_type"];
  problem?: "all" | "flagged";
  severity?: "all" | DocumentReviewBlockFlagResponse["severity"];
};

export type CursorPaginationParams = {
  limit?: number;
  cursor?: string;
};

export type DocumentReviewBlockDetailParams = CursorPaginationParams & {
  snapshot_id: string;
};

export type DocumentTableReferenceListParams = {
  block_id?: string;
};

export type DocumentTableReferenceContentParams = {
  generation: number;
  ir_file_id: string;
  disposition?: "inline" | "attachment";
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

  listReviewBlocks(jobId: string, params: DocumentReviewBlocksParams = {}): Promise<DocumentReviewBlocksResponse> {
    return apiRequest<DocumentReviewBlocksResponse>({
      url: `/api/v1/document-jobs/${jobId}/review/blocks`,
      method: "GET",
      params,
    });
  },

  getQuality(jobId: string): Promise<DocumentQualityResponse> {
    return apiRequest<DocumentQualityResponse>({
      url: `/api/v1/document-jobs/${jobId}/quality`,
      method: "GET",
    });
  },

  listQualityTables(jobId: string, params: CursorPaginationParams = {}): Promise<DocumentQualityTablesResponse> {
    return apiRequest<DocumentQualityTablesResponse>({
      url: `/api/v1/document-jobs/${jobId}/quality/tables`,
      method: "GET",
      params,
    });
  },

  listQualityPages(jobId: string, params: CursorPaginationParams = {}): Promise<DocumentQualityPagesResponse> {
    return apiRequest<DocumentQualityPagesResponse>({
      url: `/api/v1/document-jobs/${jobId}/quality/pages`,
      method: "GET",
      params,
    });
  },

  getPreview(jobId: string, params: CursorPaginationParams = {}): Promise<DocumentPreviewResponse> {
    return apiRequest<DocumentPreviewResponse>({
      url: `/api/v1/document-jobs/${jobId}/preview`,
      method: "GET",
      params,
    });
  },

  getReview(jobId: string): Promise<DocumentCurrentReviewResponse> {
    return apiRequest<DocumentCurrentReviewResponse>({
      url: `/api/v1/document-jobs/${jobId}/review`,
      method: "GET",
    });
  },

  listReviewHistory(jobId: string, params: CursorPaginationParams = {}): Promise<DocumentReviewHistoryResponse> {
    return apiRequest<DocumentReviewHistoryResponse>({
      url: `/api/v1/document-jobs/${jobId}/review/history`,
      method: "GET",
      params,
    });
  },

  submitReview(jobId: string, payload: DocumentReviewUpdateRequest): Promise<DocumentReviewUpdateResponse> {
    return apiRequest<DocumentReviewUpdateResponse>({
      url: `/api/v1/document-jobs/${jobId}/review`,
      method: "PATCH",
      data: payload,
    });
  },

  getReviewBlockDetail(
    jobId: string,
    blockId: string,
    params: DocumentReviewBlockDetailParams,
  ): Promise<DocumentReviewBlockDetailResponse> {
    return apiRequest<DocumentReviewBlockDetailResponse>({
      url: `/api/v1/document-jobs/${jobId}/review/blocks/${encodeURIComponent(blockId)}`,
      method: "GET",
      params,
    });
  },

  listTableReferences(
    jobId: string,
    params: DocumentTableReferenceListParams = {},
  ): Promise<DocumentJobTableReferenceListResponse> {
    return apiRequest<DocumentJobTableReferenceListResponse>({
      url: `/api/v1/document-jobs/${jobId}/table-references`,
      method: "GET",
      params,
    });
  },

  // 通过后端返回的受鉴权相对路径拉取表格参考图二进制流，由调用方负责 revokeObjectURL。
  getTableReferenceContentBlob(contentPath: string): Promise<Blob> {
    return apiRequest<Blob>({
      url: contentPath,
      method: "GET",
      responseType: "blob",
    });
  },

  getTableReferenceContent(
    jobId: string,
    assetId: string,
    params: DocumentTableReferenceContentParams,
  ): Promise<Blob> {
    return apiRequest<Blob>({
      url: `/api/v1/document-jobs/${jobId}/table-references/${encodeURIComponent(assetId)}/content`,
      method: "GET",
      params,
      responseType: "blob",
    });
  },

  requestNewGeneration(
    jobId: string,
    payload: DocumentJobNewGenerationRequest,
  ): Promise<DocumentJobNewGenerationResponse> {
    return apiRequest<DocumentJobNewGenerationResponse>({
      url: `/api/v1/document-jobs/${jobId}/new-generation`,
      method: "POST",
      data: payload,
    });
  },

  getGenerationRequest(jobId: string, requestId: string): Promise<DocumentJobNewGenerationResponse> {
    return apiRequest<DocumentJobNewGenerationResponse>({
      url: `/api/v1/document-jobs/${jobId}/generation-requests/${encodeURIComponent(requestId)}`,
      method: "GET",
    });
  },

  listPublications(jobId: string): Promise<DocumentPublicationsResponse> {
    return apiRequest<DocumentPublicationsResponse>({
      url: `/api/v1/document-jobs/${jobId}/publications`,
      method: "GET",
    });
  },

  publish(jobId: string, payload: DocumentPublishRequest): Promise<DocumentPublishResponse> {
    return apiRequest<DocumentPublishResponse>({
      url: `/api/v1/document-jobs/${jobId}/publish`,
      method: "POST",
      data: payload,
    });
  },

  createPublicationDownloadUrl(
    jobId: string,
    publicationId: string,
  ): Promise<DocumentPublicationDownloadUrlResponse> {
    return apiRequest<DocumentPublicationDownloadUrlResponse>({
      url: `/api/v1/document-jobs/${jobId}/publications/${encodeURIComponent(publicationId)}/download-url`,
      method: "GET",
    });
  },

  getCallbackMessageSummary(jobId: string): Promise<DocumentJobCallbackMessageSummaryResponse> {
    return apiRequest<DocumentJobCallbackMessageSummaryResponse>({
      url: `/api/v1/document-jobs/${jobId}/callback-messages/summary`,
      method: "GET",
    });
  },

  listTranslationBatches(jobId: string): Promise<DocumentJobTranslationBatchListResponse> {
    return apiRequest<DocumentJobTranslationBatchListResponse>({
      url: `/api/v1/document-jobs/${jobId}/translation-batches`,
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

  previewDelete(jobId: string): Promise<DocumentJobDeletePreviewResponse> {
    return apiRequest<DocumentJobDeletePreviewResponse>({
      url: `/api/v1/document-jobs/${jobId}/delete-preview`,
      method: "POST",
    });
  },

  delete(jobId: string, payload: DocumentJobDeleteExecuteRequest): Promise<DocumentJobDeleteExecuteResponse> {
    return apiRequest<DocumentJobDeleteExecuteResponse>({
      url: `/api/v1/document-jobs/${jobId}/delete`,
      method: "POST",
      data: payload,
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
