// File: frontend/src/api/opsIntegrationCapabilities.ts
// Purpose: Wrap Admin-only read-only real integration capability control-plane API.
import { apiRequest } from "@/api/client";
import type { OpsIntegrationControlPlaneResponse } from "@/api/types";

export const opsIntegrationCapabilitiesApi = {
  // 读取真实外部/破坏性能力控制面状态，不执行任何能力。
  get(): Promise<OpsIntegrationControlPlaneResponse> {
    return apiRequest<OpsIntegrationControlPlaneResponse>({
      url: "/api/v1/ops/integration-capabilities",
      method: "GET",
    });
  },
};
