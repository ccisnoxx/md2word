// File: frontend/src/api/opsAlertDeliveries.ts
// Purpose: Wrap Admin-only fake and controlled real Ops alert delivery APIs.
import { apiRequest } from "@/api/client";
import type {
  OpsAlertDeliveryAdapterContractResponse,
  OpsAlertDeliveryFakeSendRequest,
  OpsAlertDeliveryPreviewRequest,
  OpsAlertDeliveryRealPreviewRequest,
  OpsAlertDeliveryRealSendRequest,
  OpsAlertDeliveryResponse,
} from "@/api/types";

export const opsAlertDeliveriesApi = {
  // 读取真实 alert delivery adapter 合同和 fake parity；不发送外部通知。
  getAdapterContract(): Promise<OpsAlertDeliveryAdapterContractResponse> {
    return apiRequest<OpsAlertDeliveryAdapterContractResponse>({
      url: "/api/v1/ops/alert-deliveries/adapter-contract",
      method: "GET",
    });
  },

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

  // 预览 Phase 7 Slack webhook pilot gates，不解析 secret、不发送外部通知。
  previewRealSend(payload: OpsAlertDeliveryRealPreviewRequest): Promise<OpsAlertDeliveryResponse> {
    return apiRequest<OpsAlertDeliveryResponse>({
      url: "/api/v1/ops/alert-deliveries/real-send/preview",
      method: "POST",
      data: payload,
    });
  },

  // 执行 Phase 7 Slack webhook pilot；只有后端 gates 全部通过才可能调用 provider。
  realSend(payload: OpsAlertDeliveryRealSendRequest): Promise<OpsAlertDeliveryResponse> {
    return apiRequest<OpsAlertDeliveryResponse>({
      url: "/api/v1/ops/alert-deliveries/real-send",
      method: "POST",
      data: payload,
    });
  },
};
