// File: frontend/tests/smoke/incident-triage.spec.ts
// Purpose: Browser smoke coverage for the lightweight incident triage workbench.
import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_STORAGE_KEY = "md2word.frontend.access_token";
const ISO_NOW = "2026-06-20T04:00:00Z";

const retryableActions = {
  download: { enabled: false, disabled_reason: "任务尚未生成可下载结果。", retryable: false },
  retry: { enabled: true, disabled_reason: null, retryable: true },
  cancel: { enabled: false, disabled_reason: "只有 pending、queued、running 任务允许取消。", retryable: false },
  archive: { enabled: true, disabled_reason: null, retryable: false },
  unarchive: { enabled: false, disabled_reason: "任务未归档。", retryable: false },
  clone: { enabled: true, disabled_reason: null, retryable: false },
  delete: { enabled: true, disabled_reason: null, retryable: false },
};

const nonRetryableActions = {
  ...retryableActions,
  retry: { enabled: false, disabled_reason: "QA 证据不足，需先检查产物。", retryable: false },
};

function makeJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "docjob_incident_retry",
    tenant_id: "tenant_default",
    company_id: "company_default",
    created_by: "user_operator",
    source_file_id: "file_retry_source",
    source_job_id: null,
    mode: "direct_pdf_to_word",
    document_language: "auto",
    status: "failed",
    stage: "failed",
    progress: 62,
    template_version_id: "template_default",
    term_version_id: null,
    result_file_id: null,
    mineru_raw_result_file_id: null,
    document_ir_file_id: null,
    image_asset_file_ids: [],
    debug_full_text_enabled: false,
    mineru_batch_id: "batch_retry",
    mineru_data_id: "docjob_incident_retry",
    failed_stage: "rendering",
    error_code: "worker_timeout",
    error_message: "worker timeout while rendering",
    retry_count: 1,
    timeout_at: null,
    started_at: "2026-06-20T03:45:00Z",
    completed_at: null,
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
      source_file: { original_filename: "retry-source.pdf" },
    },
    available_actions: retryableActions,
    created_at: "2026-06-20T03:40:00Z",
    updated_at: "2026-06-20T03:50:00Z",
    ...overrides,
  };
}

function makeIncidentItem(overrides: Record<string, unknown> = {}) {
  return {
    job: makeJob(),
    failure_type: "worker_or_dispatch_failed",
    priority: 1,
    is_incident: true,
    retryable: true,
    retry_disabled_reason: null,
    stalled: false,
    stalled_minutes: null,
    blocked: false,
    suggested_action: "可直接重试",
    evidence_summary: ["failed_stage=rendering", "error_code=worker_timeout", "worker timeout while rendering"],
    ...overrides,
  };
}

const retryIncident = makeIncidentItem();

const blockedIncident = makeIncidentItem({
  job: makeJob({
    id: "docjob_incident_blocked",
    source_file_id: "file_blocked_source",
    mode: "en2zh_pdf_to_word",
    document_language: "en",
    status: "succeeded",
    stage: "completed",
    progress: 100,
    result_file_id: "file_blocked_result",
    document_ir_file_id: null,
    mineru_batch_id: "batch_blocked",
    mineru_data_id: "docjob_incident_blocked",
    failed_stage: null,
    error_code: null,
    error_message: null,
    retry_count: 0,
    translation_qa_status: "blocked",
    translation_qa_issue_type: "artifact_missing",
    translation_qa_note: "debug archive missing",
    request_snapshot: {
      source_file: { original_filename: "blocked-source.pdf" },
    },
    available_actions: nonRetryableActions,
    completed_at: "2026-06-20T03:30:00Z",
    updated_at: "2026-06-20T03:32:00Z",
  }),
  failure_type: "artifact_missing",
  priority: 0,
  retryable: false,
  retry_disabled_reason: "QA 证据不足，需先检查产物。",
  blocked: true,
  suggested_action: "缺少产物，先打开详情检查",
  evidence_summary: ["translation_qa_status=blocked", "artifact_missing", "debug archive missing"],
});

const incidentItems = [blockedIncident, retryIncident];

type IncidentApiControls = {
  listRequests: string[];
  retryRequests: string[];
  bulkRetryBodies: Array<Record<string, unknown>>;
  bulkRefreshBodies: Array<Record<string, unknown>>;
};

function summaryFor(items: Array<Record<string, unknown>>) {
  return {
    total: items.length,
    failed: items.filter((item) => (item.job as Record<string, unknown>).status === "failed").length,
    blocked: items.filter((item) => item.blocked).length,
    stalled: items.filter((item) => item.stalled).length,
    retryable: items.filter((item) => item.retryable).length,
    non_retryable: items.filter((item) => !item.retryable && (item.job as Record<string, unknown>).status === "failed").length,
    by_status: {
      failed: 1,
      succeeded: 1,
    },
    by_failure_type: {
      conversion_failed: 0,
      translation_failed: 0,
      qa_unavailable: 0,
      artifact_missing: 1,
      timeout_or_stalled: 0,
      worker_or_dispatch_failed: 1,
      unknown: 0,
    },
  };
}

function listResponse(items = incidentItems) {
  return {
    items,
    page: 1,
    page_size: 20,
    total: items.length,
    summary: summaryFor(items),
  };
}

function incidentById(jobId: string) {
  return incidentItems.find((item) => (item.job as Record<string, unknown>).id === jobId) || retryIncident;
}

function diagnosticResponse(jobId: string) {
  const item = incidentById(jobId);
  const job = item.job as Record<string, unknown>;
  return {
    item,
    evidence_links: [
      {
        kind: "detail",
        title: "任务详情",
        target: `/jobs/${job.id}`,
        available: true,
        helper: "查看完整状态、事件和文件。",
      },
      {
        kind: "events",
        title: "事件时间线",
        target: `/jobs/${job.id}`,
        available: true,
        helper: "详情页事件区展示完整事件。",
      },
      {
        kind: "files",
        title: "任务文件",
        target: `/jobs/${job.id}`,
        available: true,
        helper: "详情页文件区展示已登记产物。",
      },
    ],
    recent_events: [
      {
        id: `event_${job.id}`,
        stage: job.failed_stage || job.stage,
        level: job.status === "failed" ? "error" : "warning",
        event_type: job.status === "failed" ? "document_job.failed" : "translation_qa.blocked",
        message: job.error_message || "debug archive missing",
        duration_ms: 1200,
        trace_id: "trace_incident_smoke",
        created_at: ISO_NOW,
      },
    ],
    files: [
      {
        file_id: job.source_file_id,
        file_type: "source_pdf",
        original_filename: (job.request_snapshot as { source_file: { original_filename: string } }).source_file.original_filename,
        storage_provider: "local_file",
        status: "uploaded",
        size_bytes: 1024,
        expires_at: null,
        created_at: ISO_NOW,
        updated_at: ISO_NOW,
      },
    ],
  };
}

function bulkResponse(action: "retry" | "refresh", jobIds: string[]) {
  const items = jobIds.map((jobId) => {
    const item = incidentById(jobId);
    if (action === "retry" && !item.retryable) {
      return {
        job_id: jobId,
        ok: false,
        skipped: true,
        status_code: 409,
        error_code: "not_retryable",
        detail: "QA 证据不足，需先检查产物。",
        item,
      };
    }
    return {
      job_id: jobId,
      ok: true,
      skipped: false,
      status_code: 200,
      error_code: null,
      detail: null,
      item,
    };
  });
  return {
    action,
    total: items.length,
    succeeded: items.filter((item) => item.ok).length,
    failed: items.filter((item) => !item.ok && !item.skipped).length,
    skipped: items.filter((item) => item.skipped).length,
    items,
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function setupIncidentApi(page: Page): Promise<IncidentApiControls> {
  const controls: IncidentApiControls = {
    listRequests: [],
    retryRequests: [],
    bulkRetryBodies: [],
    bulkRefreshBodies: [],
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
      permissions: ["document_jobs:read", "document_jobs:retry"],
      tenant_id: "tenant_default",
      company_id: "company_default",
      display_name: "Smoke Operator",
    });
  });

  await page.route(/\/api\/v1\/document-job-incidents(?:\/.*)?(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    if (method === "GET" && url.pathname === "/api/v1/document-job-incidents") {
      controls.listRequests.push(url.search);
      await fulfillJson(route, listResponse());
      return;
    }
    if (method === "GET" && url.pathname.endsWith("/diagnostics")) {
      const jobId = url.pathname.split("/").at(-2) || "docjob_incident_retry";
      await fulfillJson(route, diagnosticResponse(jobId));
      return;
    }
    if (method === "POST" && url.pathname === "/api/v1/document-job-incidents/bulk-retry") {
      const payload = route.request().postDataJSON() as { job_ids?: string[] };
      controls.bulkRetryBodies.push(payload);
      await fulfillJson(route, bulkResponse("retry", payload.job_ids || []));
      return;
    }
    if (method === "POST" && url.pathname === "/api/v1/document-job-incidents/bulk-refresh") {
      const payload = route.request().postDataJSON() as { job_ids?: string[] };
      controls.bulkRefreshBodies.push(payload);
      await fulfillJson(route, bulkResponse("refresh", payload.job_ids || []));
      return;
    }
    await route.fallback();
  });

  await page.route("**/api/v1/document-jobs/*/retry", async (route) => {
    const jobId = new URL(route.request().url()).pathname.split("/").at(-2) || "";
    controls.retryRequests.push(jobId);
    await fulfillJson(route, {
      job_id: jobId,
      status: "queued",
      stage: "uploaded",
      retry_count: 2,
      updated_at: ISO_NOW,
    });
  });

  return controls;
}

function mainRows(page: Page) {
  return page.locator(".incident-table .el-table__body-wrapper tbody tr");
}

async function selectIncidentRow(page: Page, filename: string): Promise<void> {
  const row = mainRows(page).filter({ hasText: filename }).first();
  await row.locator(".el-checkbox__input").click();
}

test("operator can triage incidents from the desktop queue and diagnostic drawer", async ({ page }) => {
  const controls = await setupIncidentApi(page);

  await page.goto("/incidents");

  await expect(page.getByRole("heading", { name: "异常处理" })).toBeVisible();
  await expect(page.getByLabel("快捷键提示").first()).toContainText("⌘/Ctrl Enter");
  await expect(mainRows(page).nth(0)).toContainText("blocked-source.pdf");
  await expect(mainRows(page).nth(1)).toContainText("retry-source.pdf");

  await page.getByPlaceholder("搜索任务/文件/错误").fill("retry-source");
  await page.getByRole("button", { name: "搜索" }).click();
  await expect(page).toHaveURL(/q=retry-source/);
  await expect.poll(() => controls.listRequests.some((query) => query.includes("q=retry-source"))).toBe(true);

  await page.getByRole("button", { name: "可直接重试" }).click();
  await expect(page).toHaveURL(/retryable=true/);
  await expect.poll(() => controls.listRequests.some((query) => query.includes("retryable=true"))).toBe(true);

  await page.getByRole("button", { name: "retry-source.pdf" }).click();
  await expect(page).toHaveURL(/incident_job_id=docjob_incident_retry/);
  await expect(page.getByRole("heading", { name: "docjob_incident_retry" })).toBeVisible();
  await expect(page.getByText("worker timeout while rendering").first()).toBeVisible();
  await expect(page.getByText("事件时间线")).toBeVisible();

  await page.keyboard.press("Control+Enter");
  await expect.poll(() => controls.retryRequests).toEqual(["docjob_incident_retry"]);

  await page.keyboard.press("Escape");
  await expect(page).not.toHaveURL(/incident_job_id=/);
});

test("operator sees batch refresh, retry confirmation, and expandable failure details", async ({ page }) => {
  const controls = await setupIncidentApi(page);

  await page.goto("/incidents");
  await selectIncidentRow(page, "retry-source.pdf");
  await page.getByRole("button", { name: "批量刷新" }).click();
  await expect(page.locator(".batch-result-strip").getByText("批量刷新完成", { exact: true })).toBeVisible();
  await expect.poll(() => controls.bulkRefreshBodies).toHaveLength(1);

  await page.getByRole("button", { name: "关闭" }).click();
  await selectIncidentRow(page, "blocked-source.pdf");
  await selectIncidentRow(page, "retry-source.pdf");
  await expect(page.getByText("已选 2 个异常")).toBeVisible();

  await page.getByRole("button", { name: "批量重试" }).click();
  await expect(page.getByText("确认批量重试")).toBeVisible();
  await expect(page.getByText("可重试 1 个，不可重试 1 个")).toBeVisible();
  await page.getByRole("button", { name: "执行重试" }).click();

  await expect(page.locator(".batch-result-strip").getByText("批量重试完成", { exact: true })).toBeVisible();
  await expect(page.getByText("成功 1 · 失败 0 · 跳过 1")).toBeVisible();
  await expect(page.locator(".batch-result-strip").getByText("docjob_incident_blocked")).toBeVisible();
  await expect(page.locator(".batch-result-strip").getByText("not_retryable")).toBeVisible();
  await expect.poll(() => controls.bulkRetryBodies).toHaveLength(1);
});

test("incident triage page remains usable on a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setupIncidentApi(page);

  await page.goto("/incidents?incident_job_id=docjob_incident_blocked");

  await expect(page.getByRole("button", { name: "打开导航" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "异常处理" })).toBeVisible();
  await expect(page.getByText("停滞/超时")).toBeVisible();
  await expect(page.getByText("blocked-source.pdf").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "docjob_incident_blocked" })).toBeVisible();

  await page.getByRole("button", { name: "关闭" }).click();
  await expect(page.getByRole("heading", { name: "docjob_incident_blocked" })).toBeHidden();
  await page.getByRole("button", { name: "打开导航" }).click();
  await expect(page.locator(".app-mobile-drawer").getByText("异常处理")).toBeVisible();
});
