// frontend/src/api/mineruConfig.test.ts: 验证 MinerU 配置 API 的请求合同。
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api/client";
import { mineruConfigApi } from "@/api/mineruConfig";
import type { MinerUConfigResponse } from "@/api/types";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
}));

const response: MinerUConfigResponse = {
  api_token_configured: true,
  source: "runtime_config",
  updated_at: "2026-07-10T00:00:00Z",
  updated_by: "admin-1",
};

describe("MinerU config API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiRequest).mockResolvedValue(response);
  });

  it("读取不含密钥内容的配置状态", async () => {
    await mineruConfigApi.get();

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/mineru-config",
      method: "GET",
    });
  });

  it("只提交新的非空密钥", async () => {
    await mineruConfigApi.update({ api_token: "new-token" });

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/mineru-config",
      method: "PUT",
      data: { api_token: "new-token" },
    });
  });
});
