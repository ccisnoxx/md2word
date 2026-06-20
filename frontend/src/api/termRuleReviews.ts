// frontend/src/api/termRuleReviews.ts: Term rule review batch/item API wrappers.
import { apiRequest } from "@/api/client";
import type {
  TermRuleReviewBatchCreateRequest,
  TermRuleReviewBatchListResponse,
  TermRuleReviewBatchResponse,
  TermRuleReviewBulkRequest,
  TermRuleReviewBulkResponse,
  TermRuleReviewItemResponse,
  TermRuleReviewItemStatus,
  TermRuleVersionResponse,
} from "@/api/types";

export type TermRuleReviewBatchListParams = {
  page?: number;
  page_size?: number;
  mine?: boolean;
  submitted_by?: string;
};

export type TermRuleReviewItemListParams = {
  status?: TermRuleReviewItemStatus;
};

export const termRuleReviewsApi = {
  createBatch(payload: TermRuleReviewBatchCreateRequest): Promise<TermRuleReviewBatchResponse> {
    return apiRequest<TermRuleReviewBatchResponse>({
      url: "/api/v1/term-rule-reviews/batches",
      method: "POST",
      data: payload,
    });
  },

  listBatches(params: TermRuleReviewBatchListParams = {}): Promise<TermRuleReviewBatchListResponse> {
    return apiRequest<TermRuleReviewBatchListResponse>({
      url: "/api/v1/term-rule-reviews/batches",
      method: "GET",
      params: {
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
        mine: params.mine,
        submitted_by: params.submitted_by,
      },
    });
  },

  getBatch(batchId: string): Promise<TermRuleReviewBatchResponse> {
    return apiRequest<TermRuleReviewBatchResponse>({
      url: `/api/v1/term-rule-reviews/batches/${batchId}`,
      method: "GET",
    });
  },

  listItems(params: TermRuleReviewItemListParams = {}): Promise<TermRuleReviewItemResponse[]> {
    return apiRequest<TermRuleReviewItemResponse[]>({
      url: "/api/v1/term-rule-reviews/items",
      method: "GET",
      params,
    });
  },

  approveItem(itemId: string, reason?: string | null): Promise<TermRuleReviewItemResponse> {
    return apiRequest<TermRuleReviewItemResponse>({
      url: `/api/v1/term-rule-reviews/items/${itemId}/approve`,
      method: "POST",
      data: { reason: reason || null },
    });
  },

  rejectItem(itemId: string, reason: string): Promise<TermRuleReviewItemResponse> {
    return apiRequest<TermRuleReviewItemResponse>({
      url: `/api/v1/term-rule-reviews/items/${itemId}/reject`,
      method: "POST",
      data: { reason },
    });
  },

  bulkApprove(payload: TermRuleReviewBulkRequest): Promise<TermRuleReviewBulkResponse> {
    return apiRequest<TermRuleReviewBulkResponse>({
      url: "/api/v1/term-rule-reviews/items/bulk-approve",
      method: "POST",
      data: payload,
    });
  },

  bulkReject(payload: TermRuleReviewBulkRequest): Promise<TermRuleReviewBulkResponse> {
    return apiRequest<TermRuleReviewBulkResponse>({
      url: "/api/v1/term-rule-reviews/items/bulk-reject",
      method: "POST",
      data: payload,
    });
  },

  listHistory(ruleId?: string): Promise<TermRuleVersionResponse[]> {
    return apiRequest<TermRuleVersionResponse[]>({
      url: "/api/v1/term-rule-reviews/history",
      method: "GET",
      params: { rule_id: ruleId },
    });
  },
};
