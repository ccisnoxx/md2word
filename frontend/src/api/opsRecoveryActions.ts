// File: frontend/src/api/opsRecoveryActions.ts
// Purpose: Wrap Admin-only read-only operations recovery action registry APIs.
import { apiRequest } from "@/api/client";
import type {
  OpsRecoveryActionPreviewRequest,
  OpsRecoveryActionPreviewResponse,
  OpsRecoveryActionRegistryResponse,
} from "@/api/types";

export const opsRecoveryActionsApi = {
  // 读取 Admin-only recovery action registry，不执行任何恢复动作。
  list(): Promise<OpsRecoveryActionRegistryResponse> {
    return apiRequest<OpsRecoveryActionRegistryResponse>({
      url: "/api/v1/ops/recovery-actions",
      method: "GET",
    });
  },

  // 预览单个 action/target eligibility，不调度、不通知、不删除。
  preview(payload: OpsRecoveryActionPreviewRequest): Promise<OpsRecoveryActionPreviewResponse> {
    return apiRequest<OpsRecoveryActionPreviewResponse>({
      url: "/api/v1/ops/recovery-actions/preview",
      method: "POST",
      data: payload,
    });
  },
};
