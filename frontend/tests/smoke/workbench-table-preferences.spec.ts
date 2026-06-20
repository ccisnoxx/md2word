// File: frontend/tests/smoke/workbench-table-preferences.spec.ts
// Purpose: Browser smoke coverage for local-only table preferences on operations workbenches.
import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";
const ISO_NOW = "2026-06-20T04:00:00Z";

const availableActions = {
  download: { enabled: true, disabled_reason: null, retryable: false },
  retry: { enabled: true, disabled_reason: null, retryable: true },
  cancel: { enabled: false, disabled_reason: "只有处理中任务允许取消。", retryable: false },
  archive: { enabled: true, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
  delete: { enabled: true, disabled_reason: null, retryable: false },
};

function makeJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "docjob_table_pref",
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_operator",
    source_file_id: "file_source_table_pref",
    source_job_id: null,
    mode: "en2zh_pdf_to_word",
    document_language: "en",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    template_version_id: "template_default",
    term_version_id: null,
    result_file_id: "file_result_table_pref",
    mineru_raw_result_file_id: null,
    document_ir_file_id: "file_ir_table_pref",
    image_asset_file_ids: [],
    debug_full_text_enabled: true,
    mineru_batch_id: "batch_table_pref",
    mineru_data_id: "docjob_table_pref",
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
    translation_qa_reviewed_by: "reviewer-a",
    translation_qa_reviewed_at: "2026-06-20T03:50:00Z",
    request_snapshot: { source_file: { original_filename: "table-pref-source.pdf" } },
    available_actions: availableActions,
    created_at: "2026-06-20T03:35:00Z",
    updated_at: "2026-06-20T03:50:00Z",
    ...overrides,
  };
}

const jobsItem = makeJob();
const qaItem = makeJob({
  id: "docjob_table_pref_qa",
  request_snapshot: { source_file: { original_filename: "table-pref-qa.pdf" } },
});
const incidentItem = {
  job: makeJob({
    id: "docjob_table_pref_incident",
    status: "failed",
    stage: "failed",
    failed_stage: "rendering",
    error_code: "worker_timeout",
    error_message: "worker timeout while rendering",
    result_file_id: null,
    request_snapshot: { source_file: { original_filename: "table-pref-incident.pdf" } },
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
};

type ApiControls = {
  documentJobQueries: string[];
  incidentQueries: string[];
};

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
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

async function setupApi(page: Page): Promise<ApiControls> {
  const controls: ApiControls = {
    documentJobQueries: [],
    incidentQueries: [],
  };

  await page.addInitScript((tokenKey) => {
    window.localStorage.setItem(tokenKey, "smoke-token");
  }, TOKEN_STORAGE_KEY);

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      id: "user_operator",
      username: "operator",
      role: "operator",
      roles: ["operator"],
      permissions: ["document_jobs:read", "document_jobs:create", "document_jobs:retry", "translation_qa:read"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Smoke Operator",
    });
  });

  await page.route(/\/api\/v1\/saved-views(?:\/.*)?(?:\?.*)?$/, async (route) => {
    if (route.request().method() === "GET") {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (route.request().method() === "DELETE") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    await fulfillJson(route, {
      view_id: "savedview_table_pref",
      tenant_id: "tenant_default",
      company_id: "company_default",
      owner_user_id: "user_operator",
      page_key: "jobs",
      name: "表格偏好 smoke",
      filters: {},
      sort: "updated_at_desc",
      is_default: false,
      position: 0,
      created_at: ISO_NOW,
      updated_at: ISO_NOW,
    });
  });

  await page.route(/\/api\/v1\/document-jobs(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname !== "/api/v1/document-jobs") {
      await route.fallback();
      return;
    }
    controls.documentJobQueries.push(url.search);
    const pageSize = Number(url.searchParams.get("page_size") || 20);
    const isQaQueue = url.searchParams.has("translation_qa_status");
    await fulfillJson(route, documentJobsResponse([isQaQueue ? qaItem : jobsItem], pageSize));
  });

  await page.route(/\/api\/v1\/document-job-incidents(?:\/.*)?(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === "GET" && url.pathname === "/api/v1/document-job-incidents") {
      controls.incidentQueries.push(url.search);
      const pageSize = Number(url.searchParams.get("page_size") || 20);
      await fulfillJson(route, {
        items: [incidentItem],
        page: 1,
        page_size: pageSize,
        total: 1,
        summary: {
          total: 1,
          failed: 1,
          blocked: 0,
          stalled: 0,
          retryable: 1,
          non_retryable: 0,
          by_status: { failed: 1 },
          by_failure_type: { worker_or_dispatch_failed: 1 },
        },
      });
      return;
    }
    await route.fallback();
  });

  return controls;
}

async function openSettingsWithKeyboard(page: Page) {
  const button = page.getByRole("button", { name: "表格设置" });
  await button.focus();
  await expect(button).toBeFocused();
  await page.keyboard.press("Enter");
  const panel = page.getByLabel("表格设置面板");
  await expect(panel).toBeVisible();
  return panel;
}

async function choosePageSize(page: Page, panel: Locator, label: string): Promise<void> {
  await panel.locator(".el-select").click();
  await page.getByRole("option", { name: label }).click();
}

async function toggleColumn(panel: Locator, label: string): Promise<void> {
  await panel.locator(".el-checkbox", { hasText: label }).click();
}

async function chooseDensity(panel: Locator, label: string): Promise<void> {
  await panel.locator(".el-radio-button", { hasText: label }).click();
}

async function expectNoPageHorizontalOverflow(page: Page): Promise<void> {
  const sizes = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    document: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(sizes.body, `body width ${sizes.body} exceeds viewport ${sizes.viewport}`).toBeLessThanOrEqual(sizes.viewport + 1);
  expect(sizes.document, `document width ${sizes.document} exceeds viewport ${sizes.viewport}`).toBeLessThanOrEqual(sizes.viewport + 1);
}

async function expectPanelInsideViewport(page: Page): Promise<void> {
  const box = await page.getByLabel("表格设置面板").boundingBox();
  const viewport = page.viewportSize();
  expect(box, "settings panel should have a rendered box").not.toBeNull();
  expect(viewport, "viewport should be available").not.toBeNull();
  if (!box || !viewport) {
    return;
  }
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1);
}

test("desktop workbench table preferences stay local to each page", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const controls = await setupApi(page);

  await page.goto("/jobs?sort=created_at_desc&include_archived=false&page=2");
  await expect(page.getByRole("heading", { name: "任务列表" })).toBeVisible();
  await expectNoPageHorizontalOverflow(page);
  let panel = await openSettingsWithKeyboard(page);
  await expect(panel.getByRole("checkbox", { name: /任务 \/ 异常/ })).toBeDisabled();
  await toggleColumn(panel, "QA");
  await expect(page.locator(".jobs-table-card .el-table__header-wrapper").getByText("QA", { exact: true })).toHaveCount(0);
  await chooseDensity(panel, "紧凑");
  await expect(page.locator(".jobs-table-card .table.is-compact-density")).toBeVisible();
  await choosePageSize(page, panel, "50 条/页");
  await expect.poll(() => controls.documentJobQueries.some((query) => query.includes("page_size=50"))).toBe(true);
  expect(page.url()).toContain("page=1");
  expect(page.url()).not.toContain("page_size");
  await expectNoPageHorizontalOverflow(page);
  await expect
    .poll(() => page.evaluate(() => window.localStorage.getItem("md2word.workbench.jobs.table")))
    .toContain('"pageSize":50');

  await page.goto("/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=2");
  await expect(page.getByRole("heading", { name: "翻译 QA 队列" })).toBeVisible();
  await expectNoPageHorizontalOverflow(page);
  panel = await openSettingsWithKeyboard(page);
  await expect(panel.getByRole("checkbox", { name: /QA 状态/ })).toBeDisabled();
  await toggleColumn(panel, "证据");
  await expect(page.locator(".queue-table .el-table__header-wrapper").getByText("证据", { exact: true })).toHaveCount(0);
  await choosePageSize(page, panel, "100 条/页");
  await expect.poll(() => controls.documentJobQueries.some((query) => query.includes("page_size=100"))).toBe(true);
  expect(page.url()).toContain("page=1");
  expect(page.url()).not.toContain("page_size");
  await expectNoPageHorizontalOverflow(page);

  await page.goto("/incidents?page=2&sort=priority");
  await expect(page.getByRole("heading", { name: "异常处理" })).toBeVisible();
  await expectNoPageHorizontalOverflow(page);
  panel = await openSettingsWithKeyboard(page);
  await expect(panel.getByRole("checkbox", { name: /状态/ })).toBeDisabled();
  await toggleColumn(panel, "重试");
  await expect(page.locator(".incident-table .el-table__header-wrapper").getByText("重试", { exact: true })).toHaveCount(0);
  await choosePageSize(page, panel, "50 条/页");
  await expect.poll(() => controls.incidentQueries.some((query) => query.includes("page_size=50"))).toBe(true);
  expect(page.url()).toContain("page=1");
  expect(page.url()).not.toContain("page_size");
  await expectNoPageHorizontalOverflow(page);
});

test("table settings controls fit and remain keyboard reachable on mobile and tablet", async ({ page }) => {
  await setupApi(page);

  for (const viewport of [
    { width: 375, height: 812 },
    { width: 768, height: 1024 },
  ]) {
    await page.setViewportSize(viewport);
    for (const route of [
      "/jobs?sort=created_at_desc&include_archived=false&page=1",
      "/translation-qa?translation_qa_status=all&sort=updated_at_desc&include_archived=false&page=1",
      "/incidents?page=1&sort=priority",
    ]) {
      await page.goto(route);
      await expectNoPageHorizontalOverflow(page);
      const panel = await openSettingsWithKeyboard(page);
      await expect(panel.getByText("标准")).toBeVisible();
      await expect(panel.getByText("紧凑")).toBeVisible();
      await expect(panel.getByText("恢复默认")).toBeVisible();
      await expectPanelInsideViewport(page);
      await panel.getByRole("button", { name: "关闭" }).click();
      await expect(page.getByLabel("表格设置面板")).toBeHidden();
    }
  }
});
