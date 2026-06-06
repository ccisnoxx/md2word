// File: frontend/src/api/health.ts
// Purpose: Wrap read-only health and operations alert readiness APIs.
import { apiRequest } from "@/api/client";
import type { HealthMetricsResponse, HealthOpsAlertsResponse, HealthReadyResponse } from "@/api/types";

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

  // 读取后端只读运维告警 readiness。
  getOpsAlerts(): Promise<HealthOpsAlertsResponse> {
    return apiRequest<HealthOpsAlertsResponse>({
      url: "/api/v1/health/ops-alerts",
      method: "GET",
    });
  },
};
