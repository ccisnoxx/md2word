// frontend/src/api/termRules.ts: Term rule and category API wrappers for proposal workflows.
import { apiRequest } from "@/api/client";
import type {
  RuleSimulationRequest,
  RuleSimulationResponse,
  TermRuleCategoryListResponse,
  TermRuleListResponse,
  TermRuleResponse,
} from "@/api/types";

export type TermRuleListParams = {
  page?: number;
  page_size?: number;
  category_id?: string;
  enabled?: boolean;
  q?: string;
};

export const termRulesApi = {
  listCategories(): Promise<TermRuleCategoryListResponse> {
    return apiRequest<TermRuleCategoryListResponse>({
      url: "/api/v1/term-rule-categories",
      method: "GET",
    });
  },

  listRules(params: TermRuleListParams = {}): Promise<TermRuleListResponse> {
    return apiRequest<TermRuleListResponse>({
      url: "/api/v1/term-rules",
      method: "GET",
      params: {
        page: params.page ?? 1,
        page_size: params.page_size ?? 200,
        category_id: params.category_id,
        enabled: params.enabled,
        q: params.q,
      },
    });
  },

  getRule(ruleId: string): Promise<TermRuleResponse> {
    return apiRequest<TermRuleResponse>({
      url: `/api/v1/term-rules/${ruleId}`,
      method: "GET",
    });
  },

  simulate(payload: RuleSimulationRequest): Promise<RuleSimulationResponse> {
    return apiRequest<RuleSimulationResponse>({
      url: "/api/v1/term-rules/simulate",
      method: "POST",
      data: payload,
    });
  },
};
