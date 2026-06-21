// File: frontend/src/api/termRuleSets.ts
// Purpose: Provide Term Rule Set version, draft rule, diff, and preflight API wrappers.
import { apiRequest } from "@/api/client";
import type {
  TermRuleCreateRequest,
  TermRuleDraftRuleDeleteResponse,
  TermRuleDraftRuleMutationResponse,
  TermRuleListResponse,
  TermRuleResponse,
  TermRuleSetDiffResponse,
  TermRuleSetDetailResponse,
  TermRuleSetDraftResponse,
  TermRuleSetDraftUpdateRequest,
  TermRuleSetListResponse,
  TermRuleSetPreflightResponse,
  TermRuleSetPublishRequest,
  TermRuleSetRollbackRequest,
  TermRuleSetVersionResponse,
  TermRuleUpdateRequest,
} from "@/api/types";

export type TermRuleSetDraftRuleListParams = {
  page?: number;
  page_size?: number;
  category_id?: string;
  enabled?: boolean;
  q?: string;
};

export type TermRuleSetDiffParams = {
  from?: string;
  to?: string;
  include_unchanged?: boolean;
};

export type TermRuleSetPreflightParams = {
  base?: string;
};

export const termRuleSetsApi = {
  // 列出当前支持的 Term Rule Set。
  list(): Promise<TermRuleSetListResponse> {
    return apiRequest<TermRuleSetListResponse>({
      url: "/api/v1/term-rule-sets",
      method: "GET",
    });
  },

  // 读取 Term Rule Set 详情和 published versions。
  get(setId: string): Promise<TermRuleSetDetailResponse> {
    return apiRequest<TermRuleSetDetailResponse>({
      url: `/api/v1/term-rule-sets/${setId}`,
      method: "GET",
    });
  },

  // 读取当前 draft 摘要和 YAML 文本。
  getDraft(setId: string): Promise<TermRuleSetDraftResponse> {
    return apiRequest<TermRuleSetDraftResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft`,
      method: "GET",
    });
  },

  // 查询当前 draft 中的结构化规则列表。
  listDraftRules(setId: string, params: TermRuleSetDraftRuleListParams): Promise<TermRuleListResponse> {
    return apiRequest<TermRuleListResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft/rules`,
      method: "GET",
      params,
    });
  },

  // 读取当前 draft 中的一条结构化规则。
  getDraftRule(setId: string, ruleId: string): Promise<TermRuleResponse> {
    return apiRequest<TermRuleResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft/rules/${ruleId}`,
      method: "GET",
    });
  },

  // 在当前 draft 中新增一条结构化规则。
  createDraftRule(
    setId: string,
    payload: TermRuleCreateRequest,
  ): Promise<TermRuleDraftRuleMutationResponse> {
    return apiRequest<TermRuleDraftRuleMutationResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft/rules`,
      method: "POST",
      data: payload,
    });
  },

  // 更新当前 draft 中的一条结构化规则。
  updateDraftRule(
    setId: string,
    ruleId: string,
    payload: TermRuleUpdateRequest,
  ): Promise<TermRuleDraftRuleMutationResponse> {
    return apiRequest<TermRuleDraftRuleMutationResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft/rules/${ruleId}`,
      method: "PATCH",
      data: payload,
    });
  },

  // 从当前 draft 移除一条结构化规则。
  deleteDraftRule(
    setId: string,
    ruleId: string,
    expectedSnapshotHash?: string | null,
  ): Promise<TermRuleDraftRuleDeleteResponse> {
    return apiRequest<TermRuleDraftRuleDeleteResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft/rules/${ruleId}`,
      method: "DELETE",
      params: expectedSnapshotHash ? { expected_snapshot_hash: expectedSnapshotHash } : undefined,
    });
  },

  // 计算当前 draft 相对默认或指定 published version 的 diff。
  diff(setId: string, params: TermRuleSetDiffParams = {}): Promise<TermRuleSetDiffResponse> {
    return apiRequest<TermRuleSetDiffResponse>({
      url: `/api/v1/term-rule-sets/${setId}/diff`,
      method: "GET",
      params,
    });
  },

  // 读取当前 draft 的发布前校验报告。
  preflight(
    setId: string,
    params: TermRuleSetPreflightParams = {},
  ): Promise<TermRuleSetPreflightResponse> {
    return apiRequest<TermRuleSetPreflightResponse>({
      url: `/api/v1/term-rule-sets/${setId}/preflight`,
      method: "GET",
      params,
    });
  },

  // 用完整 v2 YAML 覆盖当前 draft，保留高级兜底入口。
  updateDraft(setId: string, payload: TermRuleSetDraftUpdateRequest): Promise<TermRuleSetDraftResponse> {
    return apiRequest<TermRuleSetDraftResponse>({
      url: `/api/v1/term-rule-sets/${setId}/draft/rules`,
      method: "PUT",
      data: payload,
    });
  },

  // 发布当前 draft。
  publish(setId: string, payload: TermRuleSetPublishRequest): Promise<TermRuleSetVersionResponse> {
    return apiRequest<TermRuleSetVersionResponse>({
      url: `/api/v1/term-rule-sets/${setId}/publish`,
      method: "POST",
      data: payload,
    });
  },

  // 将指定 published version 设为默认版本。
  setDefault(setId: string, version: string): Promise<TermRuleSetVersionResponse> {
    return apiRequest<TermRuleSetVersionResponse>({
      url: `/api/v1/term-rule-sets/${setId}/versions/${version}/set-default`,
      method: "POST",
    });
  },

  // 将默认指针 rollback 到指定 published version。
  rollback(setId: string, payload: TermRuleSetRollbackRequest): Promise<TermRuleSetVersionResponse> {
    return apiRequest<TermRuleSetVersionResponse>({
      url: `/api/v1/term-rule-sets/${setId}/rollback`,
      method: "POST",
      data: payload,
    });
  },
};
