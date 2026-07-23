// Translation Profile、命名 Prompt 与版本管理 API 封装。
import { apiRequest } from "@/api/client";
import type {
  TranslationProfileDetailResponse,
  TranslationProfileDraftResponse,
  TranslationProfileDraftUpdateRequest,
  TranslationProfileListResponse,
  TranslationProfilePromptCreateRequest,
  TranslationProfilePromptMutationRequest,
  TranslationProfilePromptUpdateRequest,
  TranslationProfilePublishRequest,
  TranslationProfileRollbackRequest,
  TranslationProfileVersionResponse,
} from "@/api/types";

export const translationProfilesApi = {
  list(): Promise<TranslationProfileListResponse> {
    return apiRequest<TranslationProfileListResponse>({
      url: "/api/v1/translation-profiles",
      method: "GET",
    });
  },

  get(profileId: string): Promise<TranslationProfileDetailResponse> {
    return apiRequest<TranslationProfileDetailResponse>({
      url: `/api/v1/translation-profiles/${profileId}`,
      method: "GET",
    });
  },

  getDraft(profileId: string): Promise<TranslationProfileDraftResponse> {
    return apiRequest<TranslationProfileDraftResponse>({
      url: `/api/v1/translation-profiles/${profileId}/draft`,
      method: "GET",
    });
  },

  updateDraft(
    profileId: string,
    payload: TranslationProfileDraftUpdateRequest,
  ): Promise<TranslationProfileDraftResponse> {
    return apiRequest<TranslationProfileDraftResponse>({
      url: `/api/v1/translation-profiles/${profileId}/draft`,
      method: "PUT",
      data: payload,
    });
  },

  createPrompt(
    profileId: string,
    payload: TranslationProfilePromptCreateRequest,
  ): Promise<TranslationProfileDraftResponse> {
    return apiRequest<TranslationProfileDraftResponse>({
      url: `/api/v1/translation-profiles/${profileId}/draft/prompts`,
      method: "POST",
      data: payload,
    });
  },

  updatePrompt(
    profileId: string,
    promptId: string,
    payload: TranslationProfilePromptUpdateRequest,
  ): Promise<TranslationProfileDraftResponse> {
    return apiRequest<TranslationProfileDraftResponse>({
      url: `/api/v1/translation-profiles/${profileId}/draft/prompts/${promptId}`,
      method: "PUT",
      data: payload,
    });
  },

  activatePrompt(
    profileId: string,
    promptId: string,
    payload: TranslationProfilePromptMutationRequest,
  ): Promise<TranslationProfileDraftResponse> {
    return apiRequest<TranslationProfileDraftResponse>({
      url: `/api/v1/translation-profiles/${profileId}/draft/prompts/${promptId}/activate`,
      method: "POST",
      data: payload,
    });
  },

  deletePrompt(
    profileId: string,
    promptId: string,
    payload: TranslationProfilePromptMutationRequest,
  ): Promise<TranslationProfileDraftResponse> {
    return apiRequest<TranslationProfileDraftResponse>({
      url: `/api/v1/translation-profiles/${profileId}/draft/prompts/${promptId}`,
      method: "DELETE",
      data: payload,
    });
  },

  publish(profileId: string, payload: TranslationProfilePublishRequest): Promise<TranslationProfileVersionResponse> {
    return apiRequest<TranslationProfileVersionResponse>({
      url: `/api/v1/translation-profiles/${profileId}/publish`,
      method: "POST",
      data: payload,
    });
  },

  setDefault(profileId: string, version: string): Promise<TranslationProfileVersionResponse> {
    return apiRequest<TranslationProfileVersionResponse>({
      url: `/api/v1/translation-profiles/${profileId}/versions/${version}/set-default`,
      method: "POST",
    });
  },

  rollback(profileId: string, payload: TranslationProfileRollbackRequest): Promise<TranslationProfileVersionResponse> {
    return apiRequest<TranslationProfileVersionResponse>({
      url: `/api/v1/translation-profiles/${profileId}/rollback`,
      method: "POST",
      data: payload,
    });
  },
};
