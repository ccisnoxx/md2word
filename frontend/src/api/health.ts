// frontend/src/api/health.ts: Read-only health API wrappers for the admin system status page.
import { apiRequest } from "@/api/client";
import type { HealthMetricsResponse, HealthReadyResponse } from "@/api/types";

export const healthApi = {
  getReady(): Promise<HealthReadyResponse> {
    return apiRequest<HealthReadyResponse>({
      url: "/api/v1/health/ready",
      method: "GET",
    });
  },

  getMetrics(): Promise<HealthMetricsResponse> {
    return apiRequest<HealthMetricsResponse>({
      url: "/api/v1/health/metrics",
      method: "GET",
    });
  },
};
