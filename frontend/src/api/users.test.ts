import { beforeEach, describe, expect, it, vi } from "vitest";

import type { InternalUserListResponse } from "@/api/types";
import { apiRequest } from "@/api/client";
import { internalUsersApi } from "@/api/users";

vi.mock("@/api/client", () => ({
  apiRequest: vi.fn(),
}));

const emptyUserList: InternalUserListResponse = {
  items: [],
  total: 0,
};

describe("internal users API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiRequest).mockResolvedValue(emptyUserList);
  });

  it("omits empty list filters so backend enum validation accepts the request", async () => {
    await internalUsersApi.list({
      keyword: "  ",
      role: undefined,
      status: undefined,
    });

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/users",
      method: "GET",
      params: {},
    });
  });

  it("trims keyword while keeping selected role and status filters", async () => {
    await internalUsersApi.list({
      keyword: "  admin  ",
      role: "admin",
      status: "active",
    });

    expect(apiRequest).toHaveBeenCalledWith({
      url: "/api/v1/users",
      method: "GET",
      params: {
        keyword: "admin",
        role: "admin",
        status: "active",
      },
    });
  });
});
