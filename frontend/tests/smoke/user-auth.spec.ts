// File: frontend/tests/smoke/user-auth.spec.ts
// Purpose: Browser smoke coverage for internal user/auth UX hardening.
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";

type MockRole = "admin" | "operator";

const operatorPermissions = [
  "document_jobs:read",
  "document_jobs:create",
  "document_jobs:download",
  "document_jobs:retry",
  "document_jobs:cancel",
  "document_jobs:archive",
  "document_jobs:clone",
  "translation_qa:read",
  "translation_qa:write",
  "term_proposals:read",
  "term_proposals:create",
];

const adminPermissions = [
  ...operatorPermissions,
  "settings:read",
  "settings:write",
  "system:read",
  "ops:read",
  "ops:write",
  "audit:read",
  "users:manage",
  "files:retention",
  "term_proposals:review",
];

const managedUsers = [
  {
    id: "user_admin",
    username: "admin",
    normalized_username: "admin",
    role: "admin",
    tenant_id: "tenant_default",
    company_id: "company_default",
    department_id: "default_department",
    status: "active",
    display_name: "Admin",
    created_at: "2026-06-21T00:00:00Z",
    updated_at: "2026-06-21T00:00:00Z",
    created_by: null,
    updated_by: null,
  },
  {
    id: "user_operator",
    username: "operator",
    normalized_username: "operator",
    role: "operator",
    tenant_id: "tenant_default",
    company_id: "company_default",
    department_id: "default_department",
    status: "active",
    display_name: "Operator",
    created_at: "2026-06-21T00:00:00Z",
    updated_at: "2026-06-21T00:00:00Z",
    created_by: "user_admin",
    updated_by: "user_admin",
  },
];

async function setupAuthApi(page: Page, role: MockRole): Promise<{ patchPayloads: unknown[]; passwordPayloads: unknown[] }> {
  const patchPayloads: unknown[] = [];
  const passwordPayloads: unknown[] = [];

  await page.addInitScript(
    ({ tokenKey }) => {
      window.localStorage.setItem(tokenKey, "smoke-token");
    },
    { tokenKey: TOKEN_STORAGE_KEY },
  );

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, mockUser(role));
  });

  await page.route("**/api/v1/auth/change-password", async (route) => {
    passwordPayloads.push(route.request().postDataJSON());
    await fulfillJson(route, mockUser(role));
  });

  await page.route("**/api/v1/users", async (route) => {
    await fulfillJson(route, { items: managedUsers, total: managedUsers.length });
  });

  await page.route(/\/api\/v1\/users\/([^/]+)$/, async (route) => {
    patchPayloads.push(route.request().postDataJSON());
    const userId = route.request().url().split("/").pop();
    const user = managedUsers.find((candidate) => candidate.id === userId) ?? managedUsers[1];
    await fulfillJson(route, {
      ...user,
      ...route.request().postDataJSON(),
      updated_at: "2026-06-21T00:05:00Z",
      updated_by: "user_admin",
    });
  });

  await page.route("**/api/v1/document-jobs?**", async (route) => {
    await fulfillJson(route, {
      items: [],
      total: 0,
      page: 1,
      page_size: 8,
      summary: {},
      filtered_summary: {},
      translation_qa_summary: {},
    });
  });

  await page.route("**/api/v1/document-job-incidents?**", async (route) => {
    await fulfillJson(route, {
      items: [],
      total: 0,
      page: 1,
      page_size: 6,
      summary: {
        total: 0,
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
        retryable: 0,
        blocked: 0,
        stalled: 0,
      },
    });
  });

  await page.route("**/api/v1/saved-views?**", async (route) => {
    await fulfillJson(route, { items: [] });
  });

  return { patchPayloads, passwordPayloads };
}

test("password change redirects to login with a visible success notice", async ({ page }) => {
  const controls = await setupAuthApi(page, "operator");

  await page.goto("/forbidden");
  await page.getByRole("button", { name: "修改密码" }).click();
  await page.getByLabel("当前密码").fill("old-pass");
  await page.getByRole("textbox", { name: "新密码", exact: true }).fill("new-pass");
  await page.getByRole("textbox", { name: "确认新密码" }).fill("new-pass");
  await page.getByRole("button", { name: "确认修改" }).click();

  await expect.poll(() => controls.passwordPayloads.length).toBe(1);
  expect(controls.passwordPayloads[0]).toEqual({
    current_password: "old-pass",
    new_password: "new-pass",
  });
  await expect(page).toHaveURL(/\/login\?auth=password_changed/);
  await expect(page.getByText("密码已修改，请使用新密码重新登录。")).toBeVisible();
});

test("admin sees confirmation before disabling a managed user", async ({ page }) => {
  const controls = await setupAuthApi(page, "admin");

  await page.goto("/system-status/users");
  await expect(page.getByRole("heading", { name: "用户管理" })).toBeVisible();
  await page.getByRole("row", { name: /operator/ }).getByRole("button", { name: "停用" }).click();
  await expect(page.getByText("停用 operator 后，该账号无法登录，已有 token 会立即失效。")).toBeVisible();
  await page.getByRole("button", { name: "取消" }).click();
  await expect.poll(() => controls.patchPayloads.length).toBe(0);

  await page.getByRole("row", { name: /operator/ }).getByRole("button", { name: "停用" }).click();
  await page.getByRole("button", { name: "确认停用" }).click();

  await expect.poll(() => controls.patchPayloads.length).toBe(1);
  expect(controls.patchPayloads[0]).toEqual({ status: "disabled" });
  await expect(page.getByText("用户已停用。")).toBeVisible();
});

test("forbidden page returns operators to their default accessible route", async ({ page }) => {
  await setupAuthApi(page, "operator");

  await page.goto("/system-status/users");
  await expect(page).toHaveURL(/\/forbidden/);
  await expect(page.getByRole("heading", { name: "当前账号没有访问权限" })).toBeVisible();
  await expect(page.getByText("admin")).toBeVisible();
  await page.getByRole("button", { name: "返回可访问页面" }).click();

  await expect(page).toHaveURL(/\/cockpit/);
});

function mockUser(role: MockRole) {
  const permissions = role === "admin" ? adminPermissions : operatorPermissions;
  return {
    id: role === "admin" ? "user_admin" : "user_operator",
    username: role,
    role,
    roles: [role],
    permissions,
    tenant_id: "tenant_default",
    company_id: "company_default",
    department_id: "default_department",
    display_name: role === "admin" ? "Admin" : "Operator",
  };
}

async function fulfillJson(route: Route, payload: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}
