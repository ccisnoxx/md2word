// 文件：frontend/tests/smoke/accessibility-responsive-gate.spec.ts
// 用途：守护核心工作台页面的响应式、覆盖层、可访问性和状态完整性合同。
import { expect, test, type Page, type Route } from "@playwright/test";

import {
  activateSkipLink,
  expectNoPageHorizontalOverflow,
  WORKBENCH_VIEWPORTS,
} from "./support/accessibility";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";

type ResponseMode = "success" | "empty" | "error" | "delayed-empty";
type AccessMode = "operator" | "no_access";

const operatorPermissions = ["document_jobs:read", "document_jobs:create", "document_jobs:retry", "translation_qa:read"];

function makeJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "docjob_gate_001",
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_operator",
    source_file_id: "file_source_gate",
    source_job_id: null,
    mode: "en2zh_pdf_to_word",
    document_language: "en",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    template_version_id: "template_default",
    term_version_id: null,
    result_file_id: "file_result_gate",
    mineru_raw_result_file_id: null,
    document_ir_file_id: "file_ir_gate",
    image_asset_file_ids: [],
    debug_full_text_enabled: true,
    mineru_batch_id: "batch_gate",
    mineru_data_id: "docjob_gate_001",
    failed_stage: null,
    error_code: null,
    error_message: null,
    retry_count: 0,
    timeout_at: null,
    started_at: "2026-06-20T03:40:00Z",
    completed_at: "2026-06-20T03:45:00Z",
    canceled_at: null,
    archived_at: null,
    archived_by: null,
    deleted_at: null,
    deleted_by: null,
    delete_reason: null,
    translation_qa_status: "unreviewed",
    translation_qa_issue_type: null,
    translation_qa_note: null,
    translation_qa_reviewed_by: null,
    translation_qa_reviewed_at: null,
    request_snapshot: {
      source_file: { original_filename: "gate-source.pdf" },
    },
    available_actions: {
      download: { enabled: true, disabled_reason: null, retryable: false },
      retry: { enabled: true, disabled_reason: null, retryable: true },
      cancel: { enabled: false, disabled_reason: "只有处理中任务允许取消。", retryable: false },
      archive: { enabled: true, disabled_reason: null, retryable: false },
      unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
      clone: { enabled: true, disabled_reason: null, retryable: false },
      delete: { enabled: false, disabled_reason: "只有 admin 可以删除文档任务。", retryable: false },
    },
    created_at: "2026-06-20T03:35:00Z",
    updated_at: "2026-06-20T03:50:00Z",
    ...overrides,
  };
}

function documentJobsResponse(items: unknown[], pageSize: number) {
  return {
    items,
    page: 1,
    page_size: pageSize,
    total: items.length,
    summary: { pending: 0, queued: 0, running: 0, succeeded: items.length, failed: 0, canceled: 0 },
    filtered_summary: { pending: 0, queued: 0, running: 0, succeeded: items.length, failed: 0, canceled: 0 },
    translation_qa_summary: { unreviewed: items.length, approved: 0, needs_fix: 0, blocked: 0 },
  };
}

function incidentsResponse(items: unknown[], pageSize: number) {
  return {
    items,
    page: 1,
    page_size: pageSize,
    total: items.length,
    summary: {
      total: items.length,
      failed: items.length,
      blocked: 0,
      stalled: 0,
      retryable: items.length,
      non_retryable: 0,
      by_status: items.length ? { failed: items.length } : {},
      by_failure_type: items.length ? { worker_or_dispatch_failed: items.length } : {},
    },
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function waitForLoadingTick(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 250));
}

async function setupGateApi(
  page: Page,
  options: {
    access?: AccessMode;
    jobsMode?: ResponseMode;
    qaMode?: ResponseMode;
    incidentsMode?: ResponseMode;
  } = {},
): Promise<void> {
  const {
    access = "operator",
    jobsMode = "success",
    qaMode = "success",
    incidentsMode = "success",
  } = options;

  await page.addInitScript((tokenKey) => {
    window.localStorage.setItem(tokenKey, "smoke-token");
  }, TOKEN_STORAGE_KEY);

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      id: access === "operator" ? "user_operator" : "user_guest",
      username: access === "operator" ? "operator" : "guest",
      role: access === "operator" ? "operator" : "guest",
      roles: [access === "operator" ? "operator" : "guest"],
      permissions: access === "operator" ? operatorPermissions : [],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: access === "operator" ? "Smoke Operator" : "Smoke Guest",
    });
  });

  await page.route(/\/api\/v1\/saved-views(?:\/.*)?(?:\?.*)?$/, async (route) => {
    await fulfillJson(route, { items: [] });
  });

  await page.route(/\/api\/v1\/document-jobs(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== "/api/v1/document-jobs") {
      await route.fallback();
      return;
    }
    const pageSize = Number(url.searchParams.get("page_size") || 20);
    const mode = url.searchParams.has("translation_qa_status") ? qaMode : jobsMode;
    if (mode === "error") {
      await fulfillJson(route, { detail: url.searchParams.has("translation_qa_status") ? "翻译 QA 队列暂不可用。" : "任务列表暂不可用。" }, 503);
      return;
    }
    if (mode === "delayed-empty") {
      await waitForLoadingTick();
      await fulfillJson(route, documentJobsResponse([], pageSize));
      return;
    }
    if (mode === "empty") {
      await fulfillJson(route, documentJobsResponse([], pageSize));
      return;
    }
    const item = url.searchParams.has("translation_qa_status")
      ? makeJob({ id: "docjob_gate_qa", request_snapshot: { source_file: { original_filename: "gate-qa.pdf" } } })
      : makeJob();
    await fulfillJson(route, documentJobsResponse([item], pageSize));
  });

  await page.route(/\/api\/v1\/document-job-incidents(?:\/.*)?(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "GET" && url.pathname === "/api/v1/document-job-incidents") {
      const pageSize = Number(url.searchParams.get("page_size") || 20);
      if (incidentsMode === "error") {
        await fulfillJson(route, { detail: "异常队列暂不可用。" }, 503);
        return;
      }
      if (incidentsMode === "delayed-empty") {
        await waitForLoadingTick();
        await fulfillJson(route, incidentsResponse([], pageSize));
        return;
      }
      if (incidentsMode === "empty") {
        await fulfillJson(route, incidentsResponse([], pageSize));
        return;
      }
      await fulfillJson(route, incidentsResponse([{
        job: makeJob({
          id: "docjob_gate_incident",
          status: "failed",
          stage: "failed",
          failed_stage: "rendering",
          error_code: "worker_timeout",
          error_message: "worker timeout while rendering",
          result_file_id: null,
          request_snapshot: { source_file: { original_filename: "gate-incident.pdf" } },
        }),
        failure_type: "worker_or_dispatch_failed",
        priority: 1,
        is_incident: true,
        retryable: true,
        retry_disabled_reason: null,
        stalled: false,
        stalled_minutes: null,
        blocked: false,
        suggested_action: "可直接重试",
        evidence_summary: ["failed_stage=rendering", "error_code=worker_timeout"],
      }], pageSize));
      return;
    }
    await route.fallback();
  });
}

test("shell accessibility gate preserves skip link and overlay focus return", async ({ page }) => {
  await setupGateApi(page);

  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
  await expect(page.getByRole("heading", { name: "任务列表" })).toBeVisible();
  await activateSkipLink(page);

  const commandButton = page.getByRole("button", { name: "打开命令面板" });
  await commandButton.focus();
  await expect(commandButton).toBeFocused();
  await page.keyboard.press("Control+K");
  await expect(page.getByRole("heading", { name: "命令面板" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(commandButton).toBeFocused();

  const passwordButton = page.getByRole("button", { name: "修改密码" });
  await passwordButton.click();
  await expect(page.getByRole("heading", { name: "修改密码" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(passwordButton).toBeFocused();
  await expect(page.getByRole("button", { name: /打开用户菜单/ })).toBeHidden();

  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
  const pageTitle = page.locator(".topbar-page");
  await expect(pageTitle).toHaveText("任务工作台");
  const pageTitleBox = await pageTitle.boundingBox();
  expect(pageTitleBox?.width || 0).toBeGreaterThanOrEqual(72);

  const navButton = page.getByRole("button", { name: "打开导航" });
  await navButton.click();
  await expect(page.locator(".app-mobile-drawer")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".app-mobile-drawer")).toBeHidden();
  await expect(navButton).toBeFocused();

  const userMenuButton = page.getByRole("button", { name: /打开用户菜单/ });
  await userMenuButton.click();
  await page.getByRole("menuitem", { name: "修改密码" }).click();
  await expect(page.getByRole("heading", { name: "修改密码" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(userMenuButton).toBeFocused();

  await userMenuButton.click();
  await page.getByRole("menuitem", { name: "退出" }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test("core workbench routes stay overflow-safe across the unified gate viewports", async ({ page }) => {
  await setupGateApi(page, {
    jobsMode: "empty",
    qaMode: "empty",
    incidentsMode: "empty",
  });

  const routes = [
    { path: "/jobs?sort=created_at_desc&include_archived=false&page=1", heading: "任务列表", empty: "还没有任务" },
    { path: "/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1", heading: "翻译 QA 队列", empty: "当前筛选暂无 QA 任务" },
    { path: "/incidents?page=1&sort=priority", heading: "异常处理", empty: "异常队列为空" },
  ] as const;

  for (const viewport of WORKBENCH_VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    for (const route of routes) {
      await page.goto(route.path);
      await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
      await expect(page.getByText(route.empty)).toBeVisible();
      await expectNoPageHorizontalOverflow(page);
    }
  }
});

test("core workbench routes expose loading, error, and permission gates explicitly", async ({ page }) => {
  await setupGateApi(page, {
    jobsMode: "delayed-empty",
    qaMode: "delayed-empty",
    incidentsMode: "delayed-empty",
  });

  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
  await expect(page.locator(".jobs-table-card .el-loading-mask")).toBeVisible();
  await expect(page.getByText("还没有任务")).toBeVisible();

  await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1");
  await expect(page.locator(".queue-panel .el-loading-mask")).toBeVisible();
  await expect(page.getByText("当前筛选暂无 QA 任务")).toBeVisible();

  await page.goto("/incidents?page=1&sort=priority");
  await expect(page.locator(".incident-table-wrap .el-loading-mask")).toBeVisible();
  await expect(page.getByText("异常队列为空")).toBeVisible();

  await setupGateApi(page, {
    jobsMode: "error",
    qaMode: "error",
    incidentsMode: "error",
  });

  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=1");
  await expect(page.getByText("任务列表暂不可用。")).toBeVisible();
  await expect(page.getByText("后端服务或依赖暂不可用，请稍后重试；若持续发生，请带追踪 ID 联系技术运营。")).toBeVisible();

  await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1");
  await expect(page.getByText("翻译 QA 队列暂不可用。")).toBeVisible();

  await page.goto("/incidents?page=1&sort=priority");
  await expect(page.getByText("异常队列暂不可用。")).toBeVisible();

  await setupGateApi(page, { access: "operator" });
  await page.goto("/settings/templates");
  await expect(page).toHaveURL(/\/forbidden/);
  await expect(page.getByRole("heading", { name: "当前账号没有访问权限" })).toBeVisible();
  await expect(page.getByText("admin")).toBeVisible();
});
