// frontend/src/api/aiProviderConfig.ts: Admin-only AI provider runtime configuration API wrapper.
import { apiRequest } from "@/api/client";
import type {
  AiProviderBackend,
  AiProviderConfigResponse,
  AiProviderConfigUpdateRequest,
} from "@/api/types";

export type {
  AiProviderBackend,
  AiProviderConfigResponse,
  AiProviderConfigUpdateRequest,
};

export const aiProviderConfigApi = {
  get(): Promise<AiProviderConfigResponse> {
    return apiRequest<AiProviderConfigResponse>({
      url: "/api/v1/ai-provider-config",
      method: "GET",
    });
  },

  update(payload: AiProviderConfigUpdateRequest): Promise<AiProviderConfigResponse> {
    return apiRequest<AiProviderConfigResponse>({
      url: "/api/v1/ai-provider-config",
      method: "PUT",
      data: payload,
    });
  },
};
