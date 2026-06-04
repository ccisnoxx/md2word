// frontend/src/api/translationTermSets.ts: Translation Term Set management API wrappers.
import { apiRequest } from "@/api/client";
import type {
  TranslationTermSetDetailResponse,
  TranslationTermSetDraftResponse,
  TranslationTermSetExportResponse,
  TranslationTermSetImportRequest,
  TranslationTermSetImportResponse,
  TranslationTermSetListResponse,
  TranslationTermSetPublishRequest,
  TranslationTermSetRollbackRequest,
  TranslationTermSetVersionResponse,
} from "@/api/types";

export const translationTermSetsApi = {
  list(): Promise<TranslationTermSetListResponse> {
    return apiRequest<TranslationTermSetListResponse>({
      url: "/api/v1/translation-term-sets",
      method: "GET",
    });
  },

  get(setId: string): Promise<TranslationTermSetDetailResponse> {
    return apiRequest<TranslationTermSetDetailResponse>({
      url: `/api/v1/translation-term-sets/${setId}`,
      method: "GET",
    });
  },

  getDraft(setId: string): Promise<TranslationTermSetDraftResponse> {
    return apiRequest<TranslationTermSetDraftResponse>({
      url: `/api/v1/translation-term-sets/${setId}/draft`,
      method: "GET",
    });
  },

  importCsv(setId: string, payload: TranslationTermSetImportRequest): Promise<TranslationTermSetImportResponse> {
    return apiRequest<TranslationTermSetImportResponse>({
      url: `/api/v1/translation-term-sets/${setId}/import`,
      method: "POST",
      data: payload,
    });
  },

  exportCsv(setId: string, version?: string | null): Promise<TranslationTermSetExportResponse> {
    return apiRequest<TranslationTermSetExportResponse>({
      url: `/api/v1/translation-term-sets/${setId}/export`,
      method: "GET",
      params: version ? { version } : undefined,
    });
  },

  publish(setId: string, payload: TranslationTermSetPublishRequest): Promise<TranslationTermSetVersionResponse> {
    return apiRequest<TranslationTermSetVersionResponse>({
      url: `/api/v1/translation-term-sets/${setId}/publish`,
      method: "POST",
      data: payload,
    });
  },

  setDefault(setId: string, version: string): Promise<TranslationTermSetVersionResponse> {
    return apiRequest<TranslationTermSetVersionResponse>({
      url: `/api/v1/translation-term-sets/${setId}/versions/${version}/set-default`,
      method: "POST",
    });
  },

  rollback(setId: string, payload: TranslationTermSetRollbackRequest): Promise<TranslationTermSetVersionResponse> {
    return apiRequest<TranslationTermSetVersionResponse>({
      url: `/api/v1/translation-term-sets/${setId}/rollback`,
      method: "POST",
      data: payload,
    });
  },
};
