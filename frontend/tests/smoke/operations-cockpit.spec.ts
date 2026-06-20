// File: frontend/tests/smoke/operations-cockpit.spec.ts
// Purpose: Browser smoke coverage for the personal operations cockpit landing page.
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";
const ISO_NOW = "2026-06-20T04:00:00Z";

const actionStates = {
  download: { enabled: false, disabled_reason: null, retryable: false },
  retry: { enabled: false, disabled_reason: null, retryable: false },
  cancel: { enabled: false, disabled_reason: null, retryable: false },
  archive: { enabled: false, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: null, retryable: false },
  clone: { enabled: false, disabled_reason: null, retryable: false },
  delete: { enabled: false, disabled_reason: null, retryable: false },
};

function makeJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "docjob_cockpit_base",
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_operator",
    source_file_id: "file_cockpit_source",
    source_job_id: null,
    mode: "en2zh_pdf_to_word",
    document_language: "en",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    template_version_id: "template_default",
    term_version_id: null,
    result_file_id: "file_result",
    mineru_raw_result_file_id: null,
    document_ir_file_id: "file_ir",
    image_asset_file_ids: [],
    debug_full_text_enabled: false,
    mineru_batch_id: null,
    mineru_data_id: null,
    failed_stage: null,
    error_code: null,
    error_message: null,
    retry_count: 0,
    timeout_at: null,
    started_at: "2026-06-20T03:00:00Z",
    completed_at: "2026-06-20T03:01:00Z",
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
    request_snapshot: { source_file: { original_filename: "cockpit-source.pdf" } },
    available_actions: actionStates,
    created_at: "2026-06-20T03:00:00Z",
    updated_at: "2026-06-20T03:01:00Z",
    ...overrides,
  };
}

const failedJob = makeJob({
  id: "docjob_cockpit_failed",
  source_file_id: "file_failed",
  status: "failed",
  stage: "failed",
  failed_stage: "rendering",
  error_code: "render_failed",
  error_message: "render failed",
  result_file_id: null,
  request_snapshot: { source_file: { original_filename: "failed-cockpit.pdf" } },
  updated_at: "2026-06-20T03:30:00Z",
});

const activeJob = makeJob({
  id: "docjob_cockpit_active",
  source_file_id: "file_active",
  status: "running",
  stage: "rendering",
  progress: 72,
  completed_at: null,
  result_file_id: null,
  request_snapshot: { source_file: { original_filename: "active-cockpit.pdf" } },
  updated_at: "2026-06-20T03:40:00Z",
});

const qaBlockedJob = makeJob({
  id: "docjob_cockpit_qa_blocked",
  source_file_id: "file_qa_blocked",
  translation_qa_status: "blocked",
  translation_qa_issue_type: "artifact_missing",
  translation_qa_note: "debug archive missing",
  request_snapshot: { source_file: { original_filename: "qa-blocked-cockpit.pdf" } },
  updated_at: "2026-06-20T03:45:00Z",
});

const qaUnreviewedJob = makeJob({
  id: "docjob_cockpit_qa_unreviewed",
  source_file_id: "file_qa_unreviewed",
  translation_qa_status: "unreviewed",
  request_snapshot: { source_file: { original_filename: "qa-unreviewed-cockpit.pdf" } },
  updated_at: "2026-06-20T03:50:00Z",
});

const incidentItem = {
  job: makeJob({
    id: "docjob_cockpit_incident",
    source_file_id: "file_incident",
    status: "failed",
    stage: "failed",
    failed_stage: "rendering",
    error_code: "worker_timeout",
    error_message: "worker timeout",
    result_file_id: null,
    request_snapshot: { source_file: { original_filename: "incident-cockpit.pdf" } },
    updated_at: "2026-06-20T03:55:00Z",
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
  evidence_summary: ["worker timeout"],
};

const listSummary = {
  pending: 0,
  queued: 1,
  running: 1,
  succeeded: 3,
  failed: 2,
  canceled: 0,
};

const qaSummary = {
  unreviewed: 5,
  approved: 2,
  needs_fix: 4,
  blocked: 3,
};

type MockOptions = {
  savedViewErrorPage?: string;
};

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function documentJobsResponse(items: unknown[], total = items.length) {
  return {
    items,
    page: 1,
    page_size: 20,
    total,
    summary: listSummary,
    filtered_summary: listSummary,
    translation_qa_summary: qaSummary,
  };
}

async function setupCockpitApi(page: Page, options: MockOptions = {}): Promise<void> {
  await page.addInitScript((tokenKey) => {
    window.localStorage.setItem(tokenKey, "smoke-token");
  }, TOKEN_STORAGE_KEY);

  await page.route("**/api/v1/auth/me", async (route) => {
    await fulfillJson(route, {
      id: "user_operator",
      username: "operator",
      role: "operator",
      roles: ["operator"],
      permissions: ["document_jobs:read", "document_jobs:create", "translation_qa:read"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Smoke Operator",
    });
  });

  await page.route(/\/api\/v1\/saved-views(?:\?.*)?$/, async (route) => {
    const pageKey = new URL(route.request().url()).searchParams.get("page_key") || "jobs";
    if (options.savedViewErrorPage === pageKey) {
      await fulfillJson(route, { detail: "saved view smoke failure", code: "smoke_saved_view_error" }, 503);
      return;
    }
    const defaults: Record<string, unknown[]> = {
      jobs: [
        {
          view_id: "savedview_jobs_failed",
          tenant_id: "tenant_default",
          company_id: "company_default",
          owner_user_id: "user_operator",
          page_key: "jobs",
          name: "My failed jobs",
          filters: { status: "failed" },
          sort: "updated_at_desc",
          is_default: true,
          position: 0,
          created_at: ISO_NOW,
          updated_at: ISO_NOW,
        },
      ],
      translation_qa: [
        {
          view_id: "savedview_qa_blocked",
          tenant_id: "tenant_default",
          company_id: "company_default",
          owner_user_id: "user_operator",
          page_key: "translation_qa",
          name: "My blocked QA",
          filters: { translation_qa_status: "blocked" },
          sort: "updated_at_desc",
          is_default: true,
          position: 0,
          created_at: ISO_NOW,
          updated_at: ISO_NOW,
        },
      ],
      incidents: [],
    };
    await fulfillJson(route, { items: defaults[pageKey] || [] });
  });

  await page.route(/\/api\/v1\/document-jobs(?:\?.*)?$/, async (route) => {
    const params = new URL(route.request().url()).searchParams;
    if (params.get("status") === "failed") {
      await fulfillJson(route, documentJobsResponse([failedJob], 2));
      return;
    }
    if (params.get("status_group") === "active") {
      await fulfillJson(route, documentJobsResponse([activeJob], 2));
      return;
    }
    const qaStatus = params.get("translation_qa_status");
    if (qaStatus === "blocked") {
      await fulfillJson(route, documentJobsResponse([qaBlockedJob], 3));
      return;
    }
    if (qaStatus === "all") {
      await fulfillJson(route, documentJobsResponse([qaBlockedJob, qaUnreviewedJob], 7));
      return;
    }
    await fulfillJson(route, documentJobsResponse([], 0));
  });

  await page.route(/\/api\/v1\/document-job-incidents(?:\?.*)?$/, async (route) => {
    await fulfillJson(route, {
      items: [incidentItem],
      page: 1,
      page_size: 20,
      total: 1,
      summary: {
        total: 1,
        failed: 1,
        blocked: 0,
        stalled: 2,
        retryable: 3,
        non_retryable: 0,
        by_status: { failed: 1 },
        by_failure_type: {
          conversion_failed: 0,
          translation_failed: 0,
          qa_unavailable: 0,
          artifact_missing: 0,
          timeout_or_stalled: 0,
          worker_or_dispatch_failed: 1,
          unknown: 0,
        },
      },
    });
  });
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => ({
    documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    bodyOverflow: document.body.scrollWidth - document.documentElement.clientWidth,
  }));
  expect(overflow.documentOverflow).toBeLessThanOrEqual(1);
  expect(overflow.bodyOverflow).toBeLessThanOrEqual(1);
}

test("operator lands on the desktop cockpit and can follow generated queue links", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 920 });
  await setupCockpitApi(page);

  await page.goto("/");

  await expect(page).toHaveURL(/\/cockpit$/);
  await expect(page.getByRole("heading", { name: "今日工作" })).toBeVisible();
  await expect(page.getByRole("link", { name: /可重试异常/ })).toContainText("3");
  await expect(page.getByRole("link", { name: /QA 阻塞/ })).toContainText("3");
  await expect(page.getByRole("link", { name: /My blocked QA/ })).toHaveAttribute(
    "href",
    /translation-qa\?translation_qa_status=blocked&sort=updated_at_desc&include_archived=false&page=1/,
  );
  await expect(page.getByText("incident-cockpit.pdf")).toBeVisible();

  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: /QA 阻塞/ }).click();
  await expect(page).toHaveURL(/\/translation-qa\?translation_qa_status=blocked/);
});

test("cockpit shows partial saved-view errors without blocking queues", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 920 });
  await setupCockpitApi(page, { savedViewErrorPage: "incidents" });

  await page.goto("/cockpit");

  await expect(page.getByText(/异常处理 保存视图加载失败/)).toBeVisible();
  await expect(page.getByRole("link", { name: /Retryable failures/ })).toBeVisible();
  await expect(page.getByText("incident-cockpit.pdf")).toBeVisible();
  await expect(page.getByRole("link", { name: /失败任务/ })).toContainText("2");
});

test("cockpit preserves dense mobile ordering without document overflow", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 844 });
  await setupCockpitApi(page);

  await page.goto("/cockpit");

  await expect(page.getByRole("button", { name: "打开导航" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "今日工作" })).toBeVisible();
  await expect(page.getByText("My blocked QA")).toBeVisible();
  await expect(page.getByText("incident-cockpit.pdf")).toBeVisible();

  const positions = await page.evaluate(() => {
    const priority = document.querySelector(".priority-strip")?.getBoundingClientRect().top ?? 0;
    const savedViews = document.querySelector("[aria-label='保存视图入口']")?.getBoundingClientRect().top ?? 0;
    const preview = document.querySelector("[aria-label='下一步工作']")?.getBoundingClientRect().top ?? 0;
    return { priority, savedViews, preview };
  });
  expect(positions.priority).toBeLessThan(positions.savedViews);
  expect(positions.savedViews).toBeLessThan(positions.preview);
  await expectNoHorizontalOverflow(page);
});
