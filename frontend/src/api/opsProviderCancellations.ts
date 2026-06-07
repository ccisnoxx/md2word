// File: frontend/src/api/opsProviderCancellations.ts
// Purpose: Wrap Admin-only fake provider cancellation preview and audit APIs.
import { apiRequest } from "@/api/client";
import type {
  OpsProviderCancellationFakeRequest,
  OpsProviderCancellationPreviewRequest,
  OpsProviderCancellationResponse,
  OpsProviderCancellationSemanticsResponse,
} from "@/api/types";

export const opsProviderCancellationsApi = {
  // 读取 MinerU provider cancellation 语义核查结论，不调用 provider。
  getSemanticsVerification(): Promise<OpsProviderCancellationSemanticsResponse> {
    return apiRequest<OpsProviderCancellationSemanticsResponse>({
      url: "/api/v1/ops/provider-cancellations/semantics-verification",
      method: "GET",
    });
  },

  // 预览精确 provider cancellation 目标，不调用 MinerU 或写审计。
  preview(payload: OpsProviderCancellationPreviewRequest): Promise<OpsProviderCancellationResponse> {
    return apiRequest<OpsProviderCancellationResponse>({
      url: "/api/v1/ops/provider-cancellations/preview",
      method: "POST",
      data: payload,
    });
  },

  // 执行 provider fake-cancel，只写审计，不调用真实 provider 或修改本地任务状态。
  fakeCancel(payload: OpsProviderCancellationFakeRequest): Promise<OpsProviderCancellationResponse> {
    return apiRequest<OpsProviderCancellationResponse>({
      url: "/api/v1/ops/provider-cancellations/fake-cancel",
      method: "POST",
      data: payload,
    });
  },
};
