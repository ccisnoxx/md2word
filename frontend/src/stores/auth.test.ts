import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { authApi } from "@/api/auth";
import { useAuthStore } from "@/stores/auth";
import { clearStoredToken } from "@/utils/authStorage";

vi.mock("@/api/auth", () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
  },
}));

describe("auth store permissions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    clearStoredToken();
    vi.clearAllMocks();
  });

  it("derives admin permissions when login response has only the legacy role field", async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: "token_admin",
      token_type: "bearer",
      expires_in: 3600,
      role: "admin",
      user_id: "user_admin",
      username: "admin",
      tenant_id: "tenant_default",
      company_id: "company_default",
    });

    const auth = useAuthStore();
    await auth.login({ username: "admin", password: "secret" });

    expect(auth.hasRole("admin")).toBe(true);
    expect(auth.hasPermission("document_jobs:read")).toBe(true);
    expect(auth.hasPermission("ops:read")).toBe(true);
  });

  it("keeps operator out of admin-only permissions", async () => {
    vi.mocked(authApi.me).mockResolvedValue({
      id: "user_operator",
      username: "operator",
      role: "operator",
      roles: ["operator"],
      permissions: ["document_jobs:read", "term_proposals:read"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Operator",
    });

    const auth = useAuthStore();
    auth.token = "token_operator";
    await auth.loadCurrentUser();

    expect(auth.hasPermission("document_jobs:read")).toBe(true);
    expect(auth.hasPermission("settings:read")).toBe(false);
  });
});
