// File: frontend/src/api/opsS3Deletions.ts
// Purpose: Wrap Admin-only S3 delete LocalStack/fake parity contract API.
import { apiRequest } from "@/api/client";
import type { OpsS3DeleteAdapterContractResponse } from "@/api/types";

export const opsS3DeletionsApi = {
  // 读取 S3 delete LocalStack/fake parity 合同；不执行真实或 LocalStack 删除。
  getAdapterContract(): Promise<OpsS3DeleteAdapterContractResponse> {
    return apiRequest<OpsS3DeleteAdapterContractResponse>({
      url: "/api/v1/ops/s3-deletions/adapter-contract",
      method: "GET",
    });
  },
};
