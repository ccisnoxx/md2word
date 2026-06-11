import { describe, expect, it } from "vitest";

import { normalizeApiErrorBody } from "@/utils/errors";

describe("API error normalization", () => {
  it("uses request_id as the displayed trace id when present", () => {
    const error = normalizeApiErrorBody(403, {
      detail: "当前角色无权限执行该操作。",
      error_code: "role_forbidden",
      request_id: "req_frontend_001",
      error: {
        code: "role_forbidden",
        message: "当前角色无权限执行该操作。",
        status_code: 403,
        request_id: "req_frontend_001",
      },
    });

    expect(error.status).toBe(403);
    expect(error.code).toBe("role_forbidden");
    expect(error.message).toBe("当前角色无权限执行该操作。");
    expect(error.traceId).toBe("req_frontend_001");
  });
});
