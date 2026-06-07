// File: frontend/src/api/opsAlertDeliveries.ts
// Purpose: Wrap Admin-only fake Ops alert delivery outbox APIs.
import { apiRequest } from "@/api/client";
import type {
  OpsAlertDeliveryFakeSendRequest,
  OpsAlertDeliveryPreviewRequest,
  OpsAlertDeliveryResponse,
} from "@/api/types";

export const opsAlertDeliveriesApi = {
  // 预览当前活跃 alert codes 的 local outbox fake delivery，不写审计。
  preview(payload: OpsAlertDeliveryPreviewRequest): Promise<OpsAlertDeliveryResponse> {
    return apiRequest<OpsAlertDeliveryResponse>({
      url: "/api/v1/ops/alert-deliveries/preview",
      method: "POST",
      data: payload,
    });
  },

  // 记录 local outbox fake delivery audit，不发送 Slack/email/webhook。
  fakeSend(payload: OpsAlertDeliveryFakeSendRequest): Promise<OpsAlertDeliveryResponse> {
    return apiRequest<OpsAlertDeliveryResponse>({
      url: "/api/v1/ops/alert-deliveries/fake-send",
      method: "POST",
      data: payload,
    });
  },
};
