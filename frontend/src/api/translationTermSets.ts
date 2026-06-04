// File: frontend/src/api/translationTermSets.ts
// Purpose: Provide Translation Term Set management and governance API wrappers.
import { apiRequest } from "@/api/client";
import type {
  TranslationTermProposalCompatibilityResponse,
  TranslationTermSetDetailResponse,
  TranslationTermSetDiffResponse,
  TranslationTermSetDraftResponse,
  TranslationTermSetExportResponse,
  TranslationTermSetImportRequest,
  TranslationTermSetImportResponse,
  TranslationTermSetListResponse,
  TranslationTermSetPreflightResponse,
  TranslationTermSetPublishRequest,
  TranslationTermSetRollbackRequest,
  TranslationTermSetVersionResponse,
} from "@/api/types";

export const translationTermSetsApi = {
  // 列出可管理的 Translation Term Set。
  list(): Promise<TranslationTermSetListResponse> {
    return apiRequest<TranslationTermSetListResponse>({
      url: "/api/v1/translation-term-sets",
      method: "GET",
    });
  },

  // 读取指定 set 的版本指针和 published versions。
  get(setId: string): Promise<TranslationTermSetDetailResponse> {
    return apiRequest<TranslationTermSetDetailResponse>({
      url: `/api/v1/translation-term-sets/${setId}`,
      method: "GET",
    });
  },

  // 读取当前 draft 和 validation。
  getDraft(setId: string): Promise<TranslationTermSetDraftResponse> {
    return apiRequest<TranslationTermSetDraftResponse>({
      url: `/api/v1/translation-term-sets/${setId}/draft`,
      method: "GET",
    });
  },

  // 读取 default-vs-draft 或指定版本的只读 diff。
  getDiff(setId: string, params?: { base_version?: string | null; target_version?: string | null }): Promise<TranslationTermSetDiffResponse> {
    return apiRequest<TranslationTermSetDiffResponse>({
      url: `/api/v1/translation-term-sets/${setId}/diff`,
      method: "GET",
      params: {
        ...(params?.base_version ? { base_version: params.base_version } : {}),
        ...(params?.target_version ? { target_version: params.target_version } : {}),
      },
    });
  },

  // 读取发布前只读预检报告。
  getPreflight(setId: string, params?: { base_version?: string | null; target_version?: string | null }): Promise<TranslationTermSetPreflightResponse> {
    return apiRequest<TranslationTermSetPreflightResponse>({
      url: `/api/v1/translation-term-sets/${setId}/preflight`,
      method: "GET",
      params: {
        ...(params?.base_version ? { base_version: params.base_version } : {}),
        ...(params?.target_version ? { target_version: params.target_version } : {}),
      },
    });
  },

  // 预览 pending Translation Term Proposal 与当前 draft 的兼容性。
  getProposalCompatibility(setId: string, status: "pending" = "pending"): Promise<TranslationTermProposalCompatibilityResponse> {
    return apiRequest<TranslationTermProposalCompatibilityResponse>({
      url: `/api/v1/translation-term-sets/${setId}/proposal-compatibility`,
      method: "GET",
      params: { status },
    });
  },

  // 将 CSV 导入 draft 或 seed。
  importCsv(setId: string, payload: TranslationTermSetImportRequest): Promise<TranslationTermSetImportResponse> {
    return apiRequest<TranslationTermSetImportResponse>({
      url: `/api/v1/translation-term-sets/${setId}/import`,
      method: "POST",
      data: payload,
    });
  },

  // 导出默认版本或指定 published version 的 CSV。
  exportCsv(setId: string, version?: string | null): Promise<TranslationTermSetExportResponse> {
    return apiRequest<TranslationTermSetExportResponse>({
      url: `/api/v1/translation-term-sets/${setId}/export`,
      method: "GET",
      params: version ? { version } : undefined,
    });
  },

  // 发布当前 draft。
  publish(setId: string, payload: TranslationTermSetPublishRequest): Promise<TranslationTermSetVersionResponse> {
    return apiRequest<TranslationTermSetVersionResponse>({
      url: `/api/v1/translation-term-sets/${setId}/publish`,
      method: "POST",
      data: payload,
    });
  },

  // 切换默认版本指针。
  setDefault(setId: string, version: string): Promise<TranslationTermSetVersionResponse> {
    return apiRequest<TranslationTermSetVersionResponse>({
      url: `/api/v1/translation-term-sets/${setId}/versions/${version}/set-default`,
      method: "POST",
    });
  },

  // Rollback 默认版本指针到指定 published version。
  rollback(setId: string, payload: TranslationTermSetRollbackRequest): Promise<TranslationTermSetVersionResponse> {
    return apiRequest<TranslationTermSetVersionResponse>({
      url: `/api/v1/translation-term-sets/${setId}/rollback`,
      method: "POST",
      data: payload,
    });
  },
};
