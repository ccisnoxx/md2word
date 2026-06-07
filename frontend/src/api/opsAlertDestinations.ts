// File: frontend/src/api/opsAlertDestinations.ts
// Purpose: Wrap Admin-only alert destination configuration dry-run APIs.
import { apiRequest } from "@/api/client";
import type {
  OpsAlertDestinationDryRunRequest,
  OpsAlertDestinationDryRunResponse,
} from "@/api/types";

export const opsAlertDestinationsApi = {
  // 只读 dry-run staged Slack/email/webhook destination 配置，不发送外部通知。
  dryRun(payload: OpsAlertDestinationDryRunRequest): Promise<OpsAlertDestinationDryRunResponse> {
    return apiRequest<OpsAlertDestinationDryRunResponse>({
      url: "/api/v1/ops/alert-destinations/dry-run",
      method: "POST",
      data: payload,
    });
  },
};
