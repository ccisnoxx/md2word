// frontend/src/api/termProposals.ts: Term Rule and Translation Term Proposal API wrappers.
import { apiRequest } from "@/api/client";
import type {
  TranslationTermProposalApproveAndPublishRequest,
  TranslationTermProposalBulkRejectRequest,
  TranslationTermProposalBulkResponse,
  TranslationTermProposalBulkReviewRequest,
  TranslationTermProposalCreateRequest,
  TranslationTermProposalListResponse,
  TranslationTermProposalResponse,
  TranslationTermProposalStatus,
  TermRuleProposalApproveAndPublishRequest,
  TermRuleProposalBulkRejectRequest,
  TermRuleProposalBulkResponse,
  TermRuleProposalBulkReviewRequest,
  TermRuleProposalCreateRequest,
  TermRuleProposalListResponse,
  TermRuleProposalResponse,
  TermRuleProposalStatus,
} from "@/api/types";

export type TermProposalScope = "my" | "all" | "pending_review" | "approved_unpublished";
export type TranslationTermProposalScope = "my" | "all" | "pending";

export type TermProposalListParams = {
  scope: TermProposalScope;
  status?: TermRuleProposalStatus;
};

export type TranslationTermProposalListParams = {
  scope: TranslationTermProposalScope;
  status?: TranslationTermProposalStatus;
};

export const termProposalsApi = {
  create(payload: TermRuleProposalCreateRequest): Promise<TermRuleProposalResponse> {
    return apiRequest<TermRuleProposalResponse>({
      url: "/api/v1/term-rule-proposals",
      method: "POST",
      data: payload,
    });
  },

  list(params: TermProposalListParams): Promise<TermRuleProposalListResponse> {
    return apiRequest<TermRuleProposalListResponse>({
      url: "/api/v1/term-rule-proposals",
      method: "GET",
      params,
    });
  },

  get(proposalId: string): Promise<TermRuleProposalResponse> {
    return apiRequest<TermRuleProposalResponse>({
      url: `/api/v1/term-rule-proposals/${proposalId}`,
      method: "GET",
    });
  },

  approve(proposalId: string, reviewComment?: string | null): Promise<TermRuleProposalResponse> {
    return apiRequest<TermRuleProposalResponse>({
      url: `/api/v1/term-rule-proposals/${proposalId}/approve`,
      method: "POST",
      data: { review_comment: reviewComment || null },
    });
  },

  approveAndPublish(proposalId: string, payload: TermRuleProposalApproveAndPublishRequest): Promise<TermRuleProposalResponse> {
    return apiRequest<TermRuleProposalResponse>({
      url: `/api/v1/term-rule-proposals/${proposalId}/approve-and-publish`,
      method: "POST",
      data: payload,
    });
  },

  reject(proposalId: string, reviewComment: string): Promise<TermRuleProposalResponse> {
    return apiRequest<TermRuleProposalResponse>({
      url: `/api/v1/term-rule-proposals/${proposalId}/reject`,
      method: "POST",
      data: { review_comment: reviewComment },
    });
  },

  bulkApprove(payload: TermRuleProposalBulkReviewRequest): Promise<TermRuleProposalBulkResponse> {
    return apiRequest<TermRuleProposalBulkResponse>({
      url: "/api/v1/term-rule-proposals/bulk-approve",
      method: "POST",
      data: payload,
    });
  },

  bulkReject(payload: TermRuleProposalBulkRejectRequest): Promise<TermRuleProposalBulkResponse> {
    return apiRequest<TermRuleProposalBulkResponse>({
      url: "/api/v1/term-rule-proposals/bulk-reject",
      method: "POST",
      data: payload,
    });
  },
};

export const translationTermProposalsApi = {
  create(payload: TranslationTermProposalCreateRequest): Promise<TranslationTermProposalResponse> {
    return apiRequest<TranslationTermProposalResponse>({
      url: "/api/v1/translation-term-proposals",
      method: "POST",
      data: payload,
    });
  },

  list(params: TranslationTermProposalListParams): Promise<TranslationTermProposalListResponse> {
    return apiRequest<TranslationTermProposalListResponse>({
      url: "/api/v1/translation-term-proposals",
      method: "GET",
      params,
    });
  },

  get(proposalId: string): Promise<TranslationTermProposalResponse> {
    return apiRequest<TranslationTermProposalResponse>({
      url: `/api/v1/translation-term-proposals/${proposalId}`,
      method: "GET",
    });
  },

  approve(proposalId: string, reviewNote?: string | null): Promise<TranslationTermProposalResponse> {
    return apiRequest<TranslationTermProposalResponse>({
      url: `/api/v1/translation-term-proposals/${proposalId}/approve`,
      method: "POST",
      data: { review_note: reviewNote || null },
    });
  },

  approveAndPublish(
    proposalId: string,
    payload: TranslationTermProposalApproveAndPublishRequest,
  ): Promise<TranslationTermProposalResponse> {
    return apiRequest<TranslationTermProposalResponse>({
      url: `/api/v1/translation-term-proposals/${proposalId}/approve-and-publish`,
      method: "POST",
      data: payload,
    });
  },

  reject(proposalId: string, reviewNote: string): Promise<TranslationTermProposalResponse> {
    return apiRequest<TranslationTermProposalResponse>({
      url: `/api/v1/translation-term-proposals/${proposalId}/reject`,
      method: "POST",
      data: { review_note: reviewNote },
    });
  },

  bulkApprove(payload: TranslationTermProposalBulkReviewRequest): Promise<TranslationTermProposalBulkResponse> {
    return apiRequest<TranslationTermProposalBulkResponse>({
      url: "/api/v1/translation-term-proposals/bulk-approve",
      method: "POST",
      data: payload,
    });
  },

  bulkReject(payload: TranslationTermProposalBulkRejectRequest): Promise<TranslationTermProposalBulkResponse> {
    return apiRequest<TranslationTermProposalBulkResponse>({
      url: "/api/v1/translation-term-proposals/bulk-reject",
      method: "POST",
      data: payload,
    });
  },
};
