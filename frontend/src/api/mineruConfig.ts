// frontend/src/api/mineruConfig.ts: 管理员专用 MinerU 账号与密钥配置 API。
import { apiRequest } from "@/api/client";
import type { MinerUConfigResponse, MinerUConfigUpdateRequest } from "@/api/types";

export type { MinerUConfigResponse, MinerUConfigUpdateRequest };

export const mineruConfigApi = {
  get(): Promise<MinerUConfigResponse> {
    return apiRequest<MinerUConfigResponse>({
      url: "/api/v1/mineru-config",
      method: "GET",
    });
  },

  update(payload: MinerUConfigUpdateRequest): Promise<MinerUConfigResponse> {
    return apiRequest<MinerUConfigResponse>({
      url: "/api/v1/mineru-config",
      method: "PUT",
      data: payload,
    });
  },
};
