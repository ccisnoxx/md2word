// frontend/src/api/termRuleSets.ts: Term Rule Set version-management API wrappers.
import { apiRequest } from "@/api/client";
import type {
  TermRuleSetDetailResponse,
  TermRuleSetDraftResponse,
  TermRuleSetDraftUpdateRequest,
  TermRuleSetListResponse,
  TermRuleSetPublishRequest,
  TermRuleSetRollbackRequest,
  TermRuleSetVersionResponse,
} from "@/api/types";

export const termRuleSetsApi = {
  list(): Promise<TermRuleSetListResponse> {
    return apiRequest<TermRuleSetListResponse>({
      url: "/api/v1/term-rule-sets",
      method: "GET",
    });
  },

  get(setId: string): Promise<TermRuleSetDetailResponse> {
    return apiRequest<TermRuleSetDetailResponse>({
      url: `/api/v1/term-rule-sets/${setId}`,
      method: "GET",
    });
  },

  getDraft(setId: string): Promise<TermRuleSetDraftResponse> {
    return apiRequest<TermRuleSetDraftResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft`,
      method: "GET",
    });
  },

  updateDraft(setId: string, payload: TermRuleSetDraftUpdateRequest): Promise<TermRuleSetDraftResponse> {
    return apiRequest<TermRuleSetDraftResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft/rules`,
      method: "PUT",
      data: payload,
    });
  },

  publish(setId: string, payload: TermRuleSetPublishRequest): Promise<TermRuleSetVersionResponse> {
    return apiRequest<TermRuleSetVersionResponse>({
      url: `/api/v1/term-rule-sets/${setId}/publish`,
      method: "POST",
      data: payload,
    });
  },

  setDefault(setId: string, version: string): Promise<TermRuleSetVersionResponse> {
    return apiRequest<TermRuleSetVersionResponse>({
      url: `/api/v1/term-rule-sets/${setId}/versions/${version}/set-default`,
      method: "POST",
    });
  },

  rollback(setId: string, payload: TermRuleSetRollbackRequest): Promise<TermRuleSetVersionResponse> {
    return apiRequest<TermRuleSetVersionResponse>({
      url: `/api/v1/term-rule-sets/${setId}/rollback`,
      method: "POST",
      data: payload,
    });
  },
};
